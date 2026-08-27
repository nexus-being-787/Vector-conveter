"""
VectorForge — Quality Metrics Module
Stage 9: Compare rasterized SVG against original to compute quality scores.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    ssim: float           # 0–1, higher is better
    psnr: float           # dB, higher is better (inf = perfect)
    edge_similarity: float  # 0–1
    pixel_coverage: float   # fraction of pixels correctly classified
    reconstruction_score: float  # composite 0–100
    path_count: int
    color_count: int
    original_bytes: int
    svg_bytes: int
    compression_ratio: float  # original / svg
    processing_time_ms: float


class QualityEvaluator:
    """
    Rasterizes the generated SVG and compares it to the original image.
    Uses cairosvg for rasterization.
    """

    def evaluate(
        self,
        original_bgr: np.ndarray,
        svg_string: str,
        path_count: int,
        color_count: int,
        original_file_bytes: int,
        processing_time_ms: float,
    ) -> QualityReport:
        """
        Compute all quality metrics.

        Args:
            original_bgr:       Original image in BGR uint8.
            svg_string:         Generated SVG as string.
            path_count:         Number of SVG paths.
            color_count:        Number of distinct colors used.
            original_file_bytes: Size of the original raster file in bytes.
            processing_time_ms: Total pipeline processing time.

        Returns:
            QualityReport
        """
        h, w = original_bgr.shape[:2]
        svg_bytes = len(svg_string.encode("utf-8"))

        # Rasterize SVG
        rasterized = self._rasterize_svg(svg_string, w, h)

        ssim_val = psnr_val = edge_sim = pixel_cov = 0.0

        if rasterized is not None:
            ssim_val = self._compute_ssim(original_bgr, rasterized)
            psnr_val = self._compute_psnr(original_bgr, rasterized)
            edge_sim = self._compute_edge_similarity(original_bgr, rasterized)
            pixel_cov = self._compute_pixel_coverage(original_bgr, rasterized)

        # Composite reconstruction score (0–100)
        reconstruction_score = (
            ssim_val * 40
            + min(psnr_val, 40) / 40 * 30
            + edge_sim * 20
            + pixel_cov * 10
        )

        compression_ratio = original_file_bytes / max(svg_bytes, 1)

        return QualityReport(
            ssim=round(ssim_val, 4),
            psnr=round(psnr_val, 2),
            edge_similarity=round(edge_sim, 4),
            pixel_coverage=round(pixel_cov, 4),
            reconstruction_score=round(reconstruction_score, 2),
            path_count=path_count,
            color_count=color_count,
            original_bytes=original_file_bytes,
            svg_bytes=svg_bytes,
            compression_ratio=round(compression_ratio, 2),
            processing_time_ms=round(processing_time_ms, 1),
        )

    # ------------------------------------------------------------------ #
    # SVG rasterisation                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rasterize_svg(
        svg_string: str, width: int, height: int
    ) -> Optional[np.ndarray]:
        """Render SVG to a numpy array using cairosvg."""
        try:
            import cairosvg
            png_bytes = cairosvg.svg2png(
                bytestring=svg_string.encode("utf-8"),
                output_width=width,
                output_height=height,
            )
            arr = np.frombuffer(png_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
        except Exception as exc:
            logger.warning("SVG rasterization failed: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    # Metric computations                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_ssim(img_a: np.ndarray, img_b: np.ndarray) -> float:
        """
        Structural Similarity Index (SSIM) between two BGR images.
        Pure NumPy implementation (no scikit-image dep at runtime eval).
        """
        a = img_a.astype(np.float64)
        b = img_b.astype(np.float64)

        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2

        mu_a = cv2.GaussianBlur(a, (11, 11), 1.5)
        mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)

        mu_a2 = mu_a ** 2
        mu_b2 = mu_b ** 2
        mu_ab = mu_a * mu_b

        sigma_a2 = cv2.GaussianBlur(a ** 2, (11, 11), 1.5) - mu_a2
        sigma_b2 = cv2.GaussianBlur(b ** 2, (11, 11), 1.5) - mu_b2
        sigma_ab = cv2.GaussianBlur(a * b, (11, 11), 1.5) - mu_ab

        ssim_map = (
            (2 * mu_ab + C1) * (2 * sigma_ab + C2)
        ) / (
            (mu_a2 + mu_b2 + C1) * (sigma_a2 + sigma_b2 + C2)
        )
        return float(np.mean(ssim_map))

    @staticmethod
    def _compute_psnr(img_a: np.ndarray, img_b: np.ndarray) -> float:
        mse = float(np.mean((img_a.astype(np.float64) - img_b.astype(np.float64)) ** 2))
        if mse < 1e-10:
            return 100.0
        return float(10 * np.log10(255.0 ** 2 / mse))

    @staticmethod
    def _compute_edge_similarity(img_a: np.ndarray, img_b: np.ndarray) -> float:
        """Fraction of edge pixels that match between original and reconstruction."""
        def edges(img: np.ndarray) -> np.ndarray:
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            return cv2.Canny(g, 50, 150)

        ea = edges(img_a).astype(bool)
        eb = edges(img_b).astype(bool)
        intersection = np.sum(ea & eb)
        union = np.sum(ea | eb)
        return float(intersection / union) if union > 0 else 1.0

    @staticmethod
    def _compute_pixel_coverage(img_a: np.ndarray, img_b: np.ndarray) -> float:
        """Fraction of pixels within tolerance 30 (per channel L∞)."""
        diff = np.abs(img_a.astype(np.int32) - img_b.astype(np.int32))
        max_diff_per_pixel = diff.max(axis=2)
        return float(np.mean(max_diff_per_pixel <= 30))
