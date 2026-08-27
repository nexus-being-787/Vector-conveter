"""
VectorForge — Image Analysis Module
Stage 2: Compute complexity metrics and classify the image type.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple

import cv2
import numpy as np
from sklearn.cluster import MiniBatchKMeans

from backend.preprocessing.image_prep import PreparedImage

logger = logging.getLogger(__name__)


class ImageClass(str, Enum):
    ICON = "ICON"
    LOGO = "LOGO"
    FLAT_GRAPHIC = "FLAT_GRAPHIC"
    ILLUSTRATION = "ILLUSTRATION"
    PORTRAIT = "PORTRAIT"
    PHOTOGRAPH = "PHOTOGRAPH"
    COMPLEX = "COMPLEX"


@dataclass
class AnalysisResult:
    width: int
    height: int
    aspect_ratio: float
    dominant_color_count: int
    color_entropy: float          # bits, 0–8
    edge_density: float           # 0–1 fraction of edge pixels
    image_complexity: float       # 0–1 composite score
    transparency_percentage: float
    estimated_vector_complexity: str  # "LOW" | "MEDIUM" | "HIGH" | "VERY HIGH"
    classification: ImageClass
    dominant_colors: List[Tuple[int, int, int]]  # top palette RGB tuples
    recommended_colors: int
    recommended_detail: int       # 1–10


class ImageAnalyzer:
    """Analyzes a PreparedImage and produces an AnalysisResult."""

    def analyze(self, prepared: PreparedImage) -> AnalysisResult:
        bgr = prepared.array
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        h, w = bgr.shape[:2]

        # ── Metrics ────────────────────────────────────────────────────────
        color_entropy = self._color_entropy(rgb)
        edge_density = self._edge_density(gray)
        transparency_pct = self._transparency_pct(prepared)
        dominant_colors, dominant_count = self._dominant_colors(rgb)
        complexity = self._complexity_score(
            color_entropy, edge_density, dominant_count, h, w
        )
        vector_complexity = self._vector_complexity_label(complexity, dominant_count)
        classification = self._classify(
            color_entropy, edge_density, dominant_count, complexity,
            transparency_pct, h, w, prepared
        )
        rec_colors, rec_detail = self._recommendations(classification, complexity)

        return AnalysisResult(
            width=w,
            height=h,
            aspect_ratio=round(w / h, 3),
            dominant_color_count=dominant_count,
            color_entropy=round(color_entropy, 3),
            edge_density=round(edge_density, 4),
            image_complexity=round(complexity, 3),
            transparency_percentage=round(transparency_pct, 2),
            estimated_vector_complexity=vector_complexity,
            classification=classification,
            dominant_colors=dominant_colors,
            recommended_colors=rec_colors,
            recommended_detail=rec_detail,
        )

    # ------------------------------------------------------------------ #
    # Private: metric calculations                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _color_entropy(rgb: np.ndarray) -> float:
        """Shannon entropy across the RGB histogram (in bits, 0–8)."""
        pixels = rgb.reshape(-1, 3)
        # Quantize to 6-bit per channel for tractable histogram
        quantized = (pixels >> 2).astype(np.uint64)
        keys = quantized[:, 0] * (64 * 64) + quantized[:, 1] * 64 + quantized[:, 2]
        counts = np.bincount(keys, minlength=64**3)
        counts = counts[counts > 0]
        probs = counts / counts.sum()
        entropy = -np.sum(probs * np.log2(probs))
        return float(entropy)

    @staticmethod
    def _edge_density(gray: np.ndarray) -> float:
        """Fraction of pixels identified as edges by Canny."""
        edges = cv2.Canny(gray, 50, 150)
        return float(np.count_nonzero(edges)) / edges.size

    @staticmethod
    def _transparency_pct(prepared: PreparedImage) -> float:
        if not prepared.has_alpha or prepared.alpha_channel is None:
            return 0.0
        alpha = prepared.alpha_channel
        transparent_pixels = np.sum(alpha < 128)
        return float(transparent_pixels) / alpha.size * 100.0

    @staticmethod
    def _dominant_colors(
        rgb: np.ndarray, max_colors: int = 64
    ) -> Tuple[List[Tuple[int, int, int]], int]:
        """
        Estimate dominant color count using MiniBatch K-Means.
        Samples up to 10 000 pixels for speed.
        """
        pixels = rgb.reshape(-1, 3).astype(np.float32)
        if len(pixels) > 10_000:
            idx = np.random.choice(len(pixels), 10_000, replace=False)
            pixels = pixels[idx]

        # Find the "knee" in inertia curve to estimate natural color count
        best_k = 8
        best_inertia_ratio = float("inf")
        prev_inertia = None

        for k in [4, 8, 16, 32, max_colors]:
            km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3)
            km.fit(pixels)
            if prev_inertia is not None:
                if prev_inertia < 1e-9:
                    # Perfect fit (solid/near-solid image) — stop here
                    best_k = k
                    break
                ratio = km.inertia_ / prev_inertia
                if ratio > best_inertia_ratio:
                    break
                best_inertia_ratio = ratio
                best_k = k
            prev_inertia = km.inertia_

        # Get final palette
        km = MiniBatchKMeans(n_clusters=best_k, random_state=42, n_init=5)
        km.fit(pixels)
        # Centers are in uint8-scale LAB. Convert to uint8 first, then LAB→RGB.
        centers_lab_u8 = km.cluster_centers_.astype(np.uint8).reshape(1, -1, 3)
        centers_rgb = cv2.cvtColor(centers_lab_u8, cv2.COLOR_LAB2RGB)[0]  # Kx3 RGB
        palette = [(int(c[0]), int(c[1]), int(c[2])) for c in centers_rgb]

        return palette, best_k

    @staticmethod
    def _complexity_score(
        entropy: float,
        edge_density: float,
        color_count: int,
        h: int,
        w: int,
    ) -> float:
        """Composite complexity score 0–1."""
        # Normalise each factor
        e_norm = min(entropy / 12.0, 1.0)          # entropy 0–12 bits theoretically
        ed_norm = min(edge_density / 0.15, 1.0)    # dense edges ~15 %
        c_norm = min(color_count / 64.0, 1.0)
        res_norm = min((h * w) / (2048 * 2048), 1.0)
        return 0.35 * e_norm + 0.30 * ed_norm + 0.25 * c_norm + 0.10 * res_norm

    @staticmethod
    def _vector_complexity_label(complexity: float, color_count: int) -> str:
        if complexity < 0.25 and color_count <= 16:
            return "LOW"
        if complexity < 0.50:
            return "MEDIUM"
        if complexity < 0.75:
            return "HIGH"
        return "VERY HIGH"

    @staticmethod
    def _classify(
        entropy: float,
        edge_density: float,
        color_count: int,
        complexity: float,
        transparency_pct: float,
        h: int,
        w: int,
        prepared: PreparedImage,
    ) -> ImageClass:
        """Rule-based classification heuristic."""
        # Very small + few colors + transparent → ICON
        if max(h, w) <= 256 and color_count <= 16 and transparency_pct > 10:
            return ImageClass.ICON

        # Few colors + very low entropy → LOGO or FLAT_GRAPHIC
        if color_count <= 12 and entropy < 3.0:
            if transparency_pct > 5 or max(h, w) <= 512:
                return ImageClass.LOGO
            return ImageClass.FLAT_GRAPHIC

        # Medium entropy, medium colors → ILLUSTRATION
        if entropy < 6.0 and color_count <= 32:
            return ImageClass.ILLUSTRATION

        # High complexity but might be a portrait — use face-detection heuristic
        if complexity > 0.55 and 0.5 < (w / h) < 1.5:
            return ImageClass.PORTRAIT  # best-effort; proper detection in Phase 6

        # High complexity
        if complexity >= 0.75:
            return ImageClass.COMPLEX

        return ImageClass.PHOTOGRAPH

    @staticmethod
    def _recommendations(
        classification: ImageClass, complexity: float
    ) -> Tuple[int, int]:
        """(recommended_colors, recommended_detail 1–10)"""
        mapping = {
            ImageClass.ICON: (8, 4),
            ImageClass.LOGO: (16, 5),
            ImageClass.FLAT_GRAPHIC: (16, 6),
            ImageClass.ILLUSTRATION: (32, 7),
            ImageClass.PORTRAIT: (64, 8),
            ImageClass.PHOTOGRAPH: (64, 7),
            ImageClass.COMPLEX: (128, 9),
        }
        return mapping.get(classification, (32, 6))
