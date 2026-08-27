"""
VectorForge — Contour Extraction Module
Stage 5: Extract hierarchical contours from region masks.
         Supports outer boundaries + holes for SVG even-odd fill rules.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

from backend.segmentation.segmenter import Region, SegmentationResult

logger = logging.getLogger(__name__)

# Minimum contour perimeter to keep (pixels)
MIN_PERIMETER = 8


@dataclass
class ExtractedContour:
    """A single contour (outer boundary or hole) for one region."""
    points: np.ndarray          # Nx2 float32 array of (x, y)
    is_hole: bool
    perimeter: float
    area: float


@dataclass
class RegionContours:
    """All contours for one segmented region."""
    region: Region
    outer_contours: List[ExtractedContour]
    hole_contours: List[ExtractedContour]


@dataclass
class ContoursResult:
    region_contours: List[RegionContours]


class ContourExtractor:
    """
    Extracts hierarchical contours from region masks.

    Uses RETR_CCOMP to distinguish outer boundaries from holes,
    supporting SVG even-odd fill rendering.
    """

    def __init__(
        self,
        min_perimeter: float = MIN_PERIMETER,
        edge_smooth_kernel: int = 0,  # 0 = no smoothing before contour extraction
        approx_method: int = cv2.CHAIN_APPROX_NONE,
    ) -> None:
        self.min_perimeter = min_perimeter
        self.edge_smooth_kernel = edge_smooth_kernel
        self.approx_method = approx_method

    def extract(self, segmentation: SegmentationResult) -> ContoursResult:
        """
        Extract contours for all regions in the segmentation result.

        Args:
            segmentation: Output of Segmenter.segment()

        Returns:
            ContoursResult with per-region contour lists.
        """
        all_region_contours: List[RegionContours] = []

        for region in segmentation.regions:
            rc = self._extract_region_contours(region)
            if rc.outer_contours:  # only keep if there is at least one valid outline
                all_region_contours.append(rc)

        return ContoursResult(region_contours=all_region_contours)

    # ------------------------------------------------------------------ #
    # Private                                                              #
    # ------------------------------------------------------------------ #

    def _extract_region_contours(self, region: Region) -> RegionContours:
        mask = region.mask.copy()

        # Optional mild smoothing to reduce pixel-staircase noise
        if self.edge_smooth_kernel > 0:
            k = self.edge_smooth_kernel | 1  # ensure odd
            mask = cv2.GaussianBlur(mask, (k, k), 0)
            _, mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

        # RETR_CCOMP: two-level hierarchy — outer then holes
        contours, hierarchy = cv2.findContours(
            mask, cv2.RETR_CCOMP, self.approx_method
        )

        outer: List[ExtractedContour] = []
        holes: List[ExtractedContour] = []

        if hierarchy is None or len(contours) == 0:
            return RegionContours(region=region, outer_contours=outer, hole_contours=holes)

        hierarchy = hierarchy[0]  # shape: (N, 4)

        for i, cnt in enumerate(contours):
            perimeter = cv2.arcLength(cnt, closed=True)
            if perimeter < self.min_perimeter:
                continue

            area = abs(cv2.contourArea(cnt))
            pts = cnt.reshape(-1, 2).astype(np.float32)

            # hierarchy[i][3] == -1 means no parent → outer contour
            is_hole = hierarchy[i][3] != -1

            ec = ExtractedContour(
                points=pts,
                is_hole=is_hole,
                perimeter=float(perimeter),
                area=float(area),
            )

            if is_hole:
                holes.append(ec)
            else:
                outer.append(ec)

        return RegionContours(region=region, outer_contours=outer, hole_contours=holes)
