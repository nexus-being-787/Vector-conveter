"""
VectorForge — Region Segmentation Module
Stage 4: Convert quantized label map into meaningful regions using
connected-components analysis plus optional watershed refinement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from backend.color.quantizer import QuantizedImage

logger = logging.getLogger(__name__)

# Minimum region area as fraction of total pixels (filters noise)
MIN_AREA_FRACTION = 0.0001   # 0.01 % of image
MIN_AREA_ABSOLUTE = 16       # absolute minimum pixels


@dataclass
class Region:
    """A meaningful image region candidate for vectorization."""
    label_index: int                    # index into the color palette
    color_hex: str
    color_bgr: Tuple[int, int, int]
    mask: np.ndarray                    # HxW binary uint8 mask (255 = in-region)
    area_pixels: int
    bounding_box: Tuple[int, int, int, int]  # x, y, w, h
    centroid: Tuple[float, float]       # (cx, cy)
    is_background: bool = False


@dataclass
class SegmentationResult:
    regions: List[Region]
    total_regions: int
    image_size: Tuple[int, int]  # (W, H)


class Segmenter:
    """
    Converts a quantized label map into a list of meaningful Region objects.

    Strategy:
      1. For each palette color, extract a binary mask.
      2. Apply morphological closing to bridge small gaps.
      3. Run connected-components to split disconnected blobs.
      4. Filter out tiny blobs (noise).
      5. Optionally apply watershed to refine boundaries between similar regions.
    """

    def __init__(
        self,
        min_area_fraction: float = MIN_AREA_FRACTION,
        min_area_absolute: int = MIN_AREA_ABSOLUTE,
        use_watershed: bool = False,
        use_morphology: bool = True,
        morph_kernel_size: int = 3,
    ) -> None:
        self.min_area_fraction = min_area_fraction
        self.min_area_absolute = min_area_absolute
        self.use_watershed = use_watershed
        self.use_morphology = use_morphology
        self.morph_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size)
        )

    def segment(self, quantized: QuantizedImage) -> SegmentationResult:
        """
        Segment a QuantizedImage into meaningful Region objects.

        Args:
            quantized: Output of ColorQuantizer.quantize()

        Returns:
            SegmentationResult with all detected regions.
        """
        label_map = quantized.label_map
        h, w = label_map.shape
        total_pixels = h * w
        min_area = max(
            self.min_area_absolute,
            int(total_pixels * self.min_area_fraction),
        )

        regions: List[Region] = []

        for palette_idx in range(quantized.num_colors):
            hex_color = quantized.palette_hex[palette_idx]
            bgr_color = quantized.palette_bgr[palette_idx]

            # Binary mask for this palette color
            color_mask = (label_map == palette_idx).astype(np.uint8) * 255

            # Morphological closing: bridge small gaps
            if self.use_morphology:
                color_mask = cv2.morphologyEx(
                    color_mask, cv2.MORPH_CLOSE, self.morph_kernel
                )

            # Connected components
            num_comps, comp_labels, stats, centroids = cv2.connectedComponentsWithStats(
                color_mask, connectivity=8
            )

            for comp_idx in range(1, num_comps):  # 0 is background of cc
                area = int(stats[comp_idx, cv2.CC_STAT_AREA])
                if area < min_area:
                    continue

                # Extract individual component mask
                comp_mask = (comp_labels == comp_idx).astype(np.uint8) * 255

                x = int(stats[comp_idx, cv2.CC_STAT_LEFT])
                y = int(stats[comp_idx, cv2.CC_STAT_TOP])
                cw = int(stats[comp_idx, cv2.CC_STAT_WIDTH])
                ch = int(stats[comp_idx, cv2.CC_STAT_HEIGHT])
                cx = float(centroids[comp_idx, 0])
                cy = float(centroids[comp_idx, 1])

                regions.append(Region(
                    label_index=palette_idx,
                    color_hex=hex_color,
                    color_bgr=bgr_color,
                    mask=comp_mask,
                    area_pixels=area,
                    bounding_box=(x, y, cw, ch),
                    centroid=(cx, cy),
                    is_background=False,
                ))

        # Sort regions largest-first (paint order: background first)
        regions.sort(key=lambda r: -r.area_pixels)
        if regions:
            regions[0].is_background = True

        # Optional watershed refinement
        if self.use_watershed and len(regions) > 1:
            regions = self._apply_watershed(
                quantized.quantized_bgr, regions, label_map
            )

        return SegmentationResult(
            regions=regions,
            total_regions=len(regions),
            image_size=(w, h),
        )

    # ------------------------------------------------------------------ #
    # Watershed (optional)                                                 #
    # ------------------------------------------------------------------ #

    def _apply_watershed(
        self,
        bgr_image: np.ndarray,
        regions: List[Region],
        label_map: np.ndarray,
    ) -> List[Region]:
        """
        Apply watershed to refine region boundaries.
        Each region centroid is used as a marker seed.
        """
        h, w = bgr_image.shape[:2]
        markers = np.zeros((h, w), dtype=np.int32)

        for i, region in enumerate(regions, start=1):
            cx, cy = int(region.centroid[0]), int(region.centroid[1])
            # Place a 5x5 seed at the centroid
            y1, y2 = max(0, cy - 2), min(h, cy + 3)
            x1, x2 = max(0, cx - 2), min(w, cx + 3)
            markers[y1:y2, x1:x2] = i

        cv2.watershed(bgr_image, markers)

        # Rebuild masks from watershed result
        for i, region in enumerate(regions, start=1):
            ws_mask = (markers == i).astype(np.uint8) * 255
            region.mask = ws_mask
            region.area_pixels = int(np.sum(ws_mask > 0))

        return regions
