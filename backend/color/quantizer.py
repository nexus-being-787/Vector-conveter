"""
VectorForge — Color Quantization Module
Stage 3: Reduce image to a manageable palette using K-Means in LAB color space.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from sklearn.cluster import MiniBatchKMeans

logger = logging.getLogger(__name__)

# Supported palette sizes
PALETTE_SIZES = [8, 16, 32, 64, 128, 256]


@dataclass
class QuantizedImage:
    """Result of color quantization."""
    quantized_bgr: np.ndarray           # HxWx3 uint8, each pixel = palette center
    label_map: np.ndarray               # HxW int32, index into palette
    palette_bgr: List[Tuple[int, int, int]]  # (B, G, R) tuples
    palette_hex: List[str]              # "#RRGGBB" strings
    num_colors: int


class ColorQuantizer:
    """
    Perceptually-accurate color quantization via MiniBatch K-Means in CIE LAB space.
    """

    def __init__(
        self,
        num_colors: int = 32,
        random_state: int = 42,
        max_sample_pixels: int = 50_000,
    ) -> None:
        if num_colors < 2:
            raise ValueError("num_colors must be at least 2")
        self.num_colors = num_colors
        self.random_state = random_state
        self.max_sample_pixels = max_sample_pixels

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def quantize(self, bgr_image: np.ndarray) -> QuantizedImage:
        """
        Quantize a BGR image to num_colors.

        Args:
            bgr_image: HxWx3 uint8 numpy array in BGR format.

        Returns:
            QuantizedImage with quantized array, label map, and palette.
        """
        h, w = bgr_image.shape[:2]

        # Convert to LAB for perceptual clustering
        lab_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2LAB).astype(np.float32)
        pixels_lab = lab_image.reshape(-1, 3)

        # Sub-sample for large images to keep fitting fast
        if len(pixels_lab) > self.max_sample_pixels:
            idx = np.random.default_rng(self.random_state).choice(
                len(pixels_lab), self.max_sample_pixels, replace=False
            )
            sample = pixels_lab[idx]
        else:
            sample = pixels_lab

        # Fit K-Means
        km = MiniBatchKMeans(
            n_clusters=self.num_colors,
            random_state=self.random_state,
            n_init=5,
            batch_size=min(4096, len(sample)),
        )
        km.fit(sample)

        # Assign every pixel to its nearest cluster
        labels = km.predict(pixels_lab).reshape(h, w).astype(np.int32)

        # Cluster centers back to BGR
        # IMPORTANT: K-Means was trained on uint8-scale LAB values (L∈[0,255]).
        # cv2.cvtColor with float32 expects LAB in a *different* scale (L∈[0,100]),
        # so we must cast to uint8 first before converting.
        centers_lab_u8 = km.cluster_centers_.astype(np.uint8)  # Kx3, uint8 LAB scale
        palette_lab_img = centers_lab_u8.reshape(1, -1, 3)     # 1xKx3, uint8
        palette_bgr_arr = cv2.cvtColor(palette_lab_img, cv2.COLOR_LAB2BGR)[0]  # Kx3, uint8

        palette_bgr = [
            (int(c[0]), int(c[1]), int(c[2])) for c in palette_bgr_arr
        ]
        palette_hex = [
            "#{:02x}{:02x}{:02x}".format(int(c[2]), int(c[1]), int(c[0]))
            for c in palette_bgr_arr
        ]

        # Reconstruct quantized image
        quantized = palette_bgr_arr[labels]  # HxWx3

        return QuantizedImage(
            quantized_bgr=quantized,
            label_map=labels,
            palette_bgr=palette_bgr,
            palette_hex=palette_hex,
            num_colors=self.num_colors,
        )

    # ------------------------------------------------------------------ #
    # Color auto-selection                                                 #
    # ------------------------------------------------------------------ #

    @classmethod
    def auto_select_colors(
        cls,
        bgr_image: np.ndarray,
        max_colors: int = 64,
    ) -> int:
        """
        Use elbow method on inertia to pick a good number of colors automatically.
        Returns the recommended number of colors (snapped to a standard palette size).
        """
        lab = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2LAB).astype(np.float32)
        pixels = lab.reshape(-1, 3)
        if len(pixels) > 10_000:
            pixels = pixels[
                np.random.default_rng(42).choice(len(pixels), 10_000, replace=False)
            ]

        candidates = [k for k in PALETTE_SIZES if k <= max_colors]
        inertias: List[float] = []
        for k in candidates:
            km = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3)
            km.fit(pixels)
            inertias.append(float(km.inertia_))

        # Find the elbow: point where improvement falls below 20 %
        best = candidates[-1]
        for i in range(1, len(inertias)):
            reduction = (inertias[i - 1] - inertias[i]) / max(inertias[i - 1], 1e-9)
            if reduction < 0.20:
                best = candidates[i - 1]
                break

        return best

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def bgr_to_hex(b: int, g: int, r: int) -> str:
        return "#{:02x}{:02x}{:02x}".format(r, g, b)

    @staticmethod
    def sort_palette_by_area(
        quantized: QuantizedImage,
    ) -> List[Tuple[str, int, float]]:
        """
        Returns palette entries sorted by pixel coverage (descending).
        Each entry: (hex_color, label_index, coverage_fraction).
        """
        label_map = quantized.label_map
        total = label_map.size
        result = []
        for idx, hex_color in enumerate(quantized.palette_hex):
            count = int(np.sum(label_map == idx))
            result.append((hex_color, idx, count / total))
        result.sort(key=lambda x: -x[2])
        return result
