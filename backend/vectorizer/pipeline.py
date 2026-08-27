"""
VectorForge — Main Pipeline Orchestrator
Coordinates all stages from preprocessed image to final SVG.

Yields progress events so the API can stream them via SSE.
Supports future AI model swap-in via ImageUnderstandingModel ABC.
"""

from __future__ import annotations

import abc
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Dict, Generator, List, Optional

import cv2
import numpy as np

from backend.preprocessing.image_prep import PreparedImage
from backend.analysis.image_analysis import AnalysisResult, ImageAnalyzer
from backend.color.quantizer import ColorQuantizer, QuantizedImage
from backend.segmentation.segmenter import Segmenter, SegmentationResult
from backend.contours.extractor import ContourExtractor, ContoursResult
from backend.curves.bezier import BezierFitter, FittedPath
from backend.svg.generator import SVGGenerator, SVGDocument, SVGRegionGroup
from backend.optimization.optimizer import SVGOptimizer, OptimizationReport
from backend.evaluation.metrics import QualityEvaluator, QualityReport

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# AI model interface (extensible)
# ─────────────────────────────────────────────────────────────────────────────

class ImageUnderstandingModel(abc.ABC):
    """
    Abstract base class for AI image understanding models.
    Future models (SAM, CLIP, human parser) implement this interface.
    """

    @abc.abstractmethod
    def analyze(self, image: np.ndarray) -> Dict:
        """Return semantic analysis dict (regions, labels, masks, etc.)."""

    @property
    def model_name(self) -> str:
        return self.__class__.__name__


class ClassicalCVModel(ImageUnderstandingModel):
    """Default: pure classical computer vision, no AI models."""

    def analyze(self, image: np.ndarray) -> Dict:
        return {"method": "classical_cv", "segmentation": None}


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────

class VectorizationMode(str, Enum):
    AUTO = "auto"
    ICON = "icon"
    LOGO = "logo"
    ILLUSTRATION = "illustration"
    PORTRAIT = "portrait"
    PHOTOGRAPH = "photograph"


class BackgroundHandling(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"
    TRANSPARENT = "transparent"
    SIMPLIFY = "simplify"


@dataclass
class PipelineConfig:
    num_colors: int = 32           # palette size
    detail_level: int = 5          # 1–10
    mode: VectorizationMode = VectorizationMode.AUTO
    background_handling: BackgroundHandling = BackgroundHandling.KEEP
    use_watershed: bool = False
    add_metadata: bool = True
    # Auto-select colors based on image content
    auto_colors: bool = False


# ─────────────────────────────────────────────────────────────────────────────
# Progress event
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProgressEvent:
    stage: str
    percent: int    # 0–100
    message: str
    data: Optional[Dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    svg_document: SVGDocument
    optimized_svg: str
    optimization_report: OptimizationReport
    quality_report: Optional[QualityReport]
    analysis: AnalysisResult
    config: PipelineConfig
    total_time_ms: float


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

class VectorizationPipeline:
    """
    Orchestrates the full raster → SVG pipeline.

    Usage:
        pipeline = VectorizationPipeline(config)
        for event in pipeline.run_with_progress(prepared_image, original_bytes):
            print(event)
        result = pipeline.last_result
    """

    STAGES = [
        ("analysis",        10,  "Analyzing image…"),
        ("quantization",    25,  "Quantizing colors…"),
        ("segmentation",    40,  "Segmenting regions…"),
        ("contours",        55,  "Extracting contours…"),
        ("bezier",          70,  "Fitting Bézier curves…"),
        ("svg_generation",  82,  "Generating SVG…"),
        ("optimization",    90,  "Optimizing SVG…"),
        ("evaluation",      98,  "Computing quality metrics…"),
        ("done",           100,  "Complete!"),
    ]

    def __init__(
        self,
        config: Optional[PipelineConfig] = None,
        understanding_model: Optional[ImageUnderstandingModel] = None,
    ) -> None:
        self.config = config or PipelineConfig()
        self.model = understanding_model or ClassicalCVModel()
        self.last_result: Optional[PipelineResult] = None

    def run_with_progress(
        self,
        prepared: PreparedImage,
        original_file_bytes: int,
    ) -> Generator[ProgressEvent, None, None]:
        """
        Run the pipeline, yielding ProgressEvent at each stage.
        After the generator is exhausted, self.last_result contains the result.
        """
        t_start = time.perf_counter()
        cfg = self.config

        # ── Stage: Analysis ────────────────────────────────────────────
        yield ProgressEvent("analysis", 5, "Analyzing image content…")
        analyzer = ImageAnalyzer()
        analysis = analyzer.analyze(prepared)

        # Override mode from analysis if AUTO
        if cfg.mode == VectorizationMode.AUTO:
            cfg.mode = VectorizationMode(analysis.classification.value.lower()
                                          if analysis.classification.value.lower()
                                          in VectorizationMode._value2member_map_
                                          else "photograph")

        # Auto-select colors
        if cfg.auto_colors:
            cfg.num_colors = analysis.recommended_colors

        yield ProgressEvent(
            "analysis", 10, f"Image classified as {analysis.classification.value}",
            data={"classification": analysis.classification.value,
                  "recommended_colors": analysis.recommended_colors}
        )

        # ── Stage: Background removal (portrait) ──────────────────────
        bgr = prepared.array.copy()
        alpha = prepared.alpha_channel

        if cfg.background_handling == BackgroundHandling.REMOVE:
            bgr, alpha = self._remove_background(bgr)

        # ── Stage: Color Quantization ─────────────────────────────────
        yield ProgressEvent("quantization", 15, f"Quantizing to {cfg.num_colors} colors…")
        quantizer = ColorQuantizer(num_colors=cfg.num_colors)
        quantized = quantizer.quantize(bgr)
        yield ProgressEvent("quantization", 25,
                            f"Palette built: {cfg.num_colors} colors",
                            data={"palette": quantized.palette_hex})

        # ── Stage: Segmentation ───────────────────────────────────────
        yield ProgressEvent("segmentation", 30, "Segmenting color regions…")
        segmenter = Segmenter(use_watershed=cfg.use_watershed)
        segmentation = segmenter.segment(quantized)
        yield ProgressEvent("segmentation", 40,
                            f"Found {segmentation.total_regions} regions",
                            data={"region_count": segmentation.total_regions})

        # ── Stage: Contour Extraction ─────────────────────────────────
        yield ProgressEvent("contours", 45, "Extracting contours…")
        extractor = ContourExtractor()
        contours_result = extractor.extract(segmentation)
        total_contours = sum(
            len(rc.outer_contours) + len(rc.hole_contours)
            for rc in contours_result.region_contours
        )
        yield ProgressEvent("contours", 55,
                            f"Extracted {total_contours} contours",
                            data={"contour_count": total_contours})

        # ── Stage: Bézier Fitting ─────────────────────────────────────
        yield ProgressEvent("bezier", 58, "Fitting Bézier curves…")
        fitter = BezierFitter(detail_level=cfg.detail_level)

        region_groups: List[SVGRegionGroup] = []
        for rc in contours_result.region_contours:
            paths: List[FittedPath] = []
            for contour in rc.outer_contours + rc.hole_contours:
                fitted = fitter.fit_contour(contour)
                if fitted:
                    paths.append(fitted)
            if paths:
                region_groups.append(SVGRegionGroup(region=rc.region, paths=paths))

        yield ProgressEvent("bezier", 70,
                            f"Fitted {sum(len(g.paths) for g in region_groups)} paths")

        # ── Stage: SVG Generation ─────────────────────────────────────
        yield ProgressEvent("svg_generation", 72, "Assembling SVG document…")
        w, h = prepared.processed_size
        generator = SVGGenerator(
            decimal_places=2,
            add_metadata=cfg.add_metadata,
            source_classification=analysis.classification.value,
        )
        svg_doc = generator.generate(
            region_groups=region_groups,
            image_width=w,
            image_height=h,
            alpha_mask=alpha,
        )
        yield ProgressEvent("svg_generation", 82,
                            f"SVG: {svg_doc.path_count} paths, {svg_doc.color_count} colors",
                            data={"path_count": svg_doc.path_count,
                                  "color_count": svg_doc.color_count,
                                  "svg_bytes": svg_doc.byte_size})

        # ── Stage: Optimization ───────────────────────────────────────
        yield ProgressEvent("optimization", 85, "Optimizing SVG…")
        optimizer = SVGOptimizer()
        optimized_svg, opt_report = optimizer.optimize(svg_doc.svg_string)
        yield ProgressEvent("optimization", 90,
                            f"Reduced {opt_report.size_reduction_pct:.1f}%")

        # ── Stage: Evaluation ─────────────────────────────────────────
        yield ProgressEvent("evaluation", 93, "Computing quality metrics…")
        evaluator = QualityEvaluator()
        t_elapsed = (time.perf_counter() - t_start) * 1000
        try:
            quality = evaluator.evaluate(
                original_bgr=bgr,
                svg_string=optimized_svg,
                path_count=svg_doc.path_count,
                color_count=svg_doc.color_count,
                original_file_bytes=original_file_bytes,
                processing_time_ms=t_elapsed,
            )
        except Exception as exc:
            logger.warning("Quality evaluation failed: %s", exc)
            quality = None

        total_ms = (time.perf_counter() - t_start) * 1000

        self.last_result = PipelineResult(
            svg_document=svg_doc,
            optimized_svg=optimized_svg,
            optimization_report=opt_report,
            quality_report=quality,
            analysis=analysis,
            config=cfg,
            total_time_ms=total_ms,
        )

        yield ProgressEvent("done", 100, "Vectorization complete!",
                            data={"total_ms": round(total_ms, 1)})

    # ------------------------------------------------------------------ #
    # Background removal                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _remove_background(bgr: np.ndarray):
        """
        Use rembg to remove the background.
        Falls back gracefully if rembg is unavailable.
        """
        try:
            from rembg import remove
            from PIL import Image
            import io

            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            pil_in = Image.fromarray(rgb)
            buf = io.BytesIO()
            pil_in.save(buf, format="PNG")
            result_bytes = remove(buf.getvalue())
            result_pil = Image.open(io.BytesIO(result_bytes)).convert("RGBA")

            arr = np.array(result_pil)
            rgb_out = arr[:, :, :3]
            alpha_out = arr[:, :, 3]
            bgr_out = cv2.cvtColor(rgb_out, cv2.COLOR_RGB2BGR)
            return bgr_out, alpha_out

        except ImportError:
            logger.warning("rembg not available, background removal skipped.")
            return bgr, None
        except Exception as exc:
            logger.warning("Background removal failed: %s", exc)
            return bgr, None
