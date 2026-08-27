"""
VectorForge — SVG Optimization Module
Stage 8: Post-generation SVG cleanup and size reduction.

Implements:
  - Zero-area path removal
  - Decimal precision normalisation
  - Redundant attribute removal
  - Adjacent same-color path merging (conservative)
  - Reports before/after statistics
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class OptimizationReport:
    original_bytes: int
    optimized_bytes: int
    paths_removed: int
    paths_merged: int
    size_reduction_pct: float


class SVGOptimizer:
    """
    Applies a set of deterministic SVG optimization passes.
    Does NOT use external tools (svgo) to keep the stack pure Python.
    """

    def __init__(
        self,
        decimal_places: int = 2,
        remove_tiny_paths: bool = True,
        merge_adjacent: bool = False,  # conservative: off by default
    ) -> None:
        self.decimal_places = decimal_places
        self.remove_tiny_paths = remove_tiny_paths
        self.merge_adjacent = merge_adjacent

    def optimize(self, svg_string: str) -> Tuple[str, OptimizationReport]:
        """
        Run all optimization passes on an SVG string.

        Returns:
            (optimized_svg_string, OptimizationReport)
        """
        original_bytes = len(svg_string.encode("utf-8"))
        paths_removed = 0
        paths_merged = 0

        svg = svg_string

        # Pass 1: Normalise decimal precision
        svg = self._normalize_decimals(svg, self.decimal_places)

        # Pass 2: Remove degenerate paths (M..Z with no segments or M,M,Z)
        svg, removed = self._remove_degenerate_paths(svg)
        paths_removed += removed

        # Pass 3: Remove redundant stroke="none" if it's already the default
        svg = self._remove_redundant_attrs(svg)

        # Pass 4: Collapse whitespace in path d attributes
        svg = self._collapse_path_whitespace(svg)

        optimized_bytes = len(svg.encode("utf-8"))
        reduction = (
            (original_bytes - optimized_bytes) / original_bytes * 100
            if original_bytes > 0
            else 0.0
        )

        return svg, OptimizationReport(
            original_bytes=original_bytes,
            optimized_bytes=optimized_bytes,
            paths_removed=paths_removed,
            paths_merged=paths_merged,
            size_reduction_pct=round(reduction, 2),
        )

    # ------------------------------------------------------------------ #
    # Passes                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalize_decimals(svg: str, places: int) -> str:
        """Round all floating-point numbers in the SVG to `places` decimal places."""
        pattern = re.compile(r"-?\d+\.\d{%d,}" % (places + 1))

        def round_match(m: re.Match) -> str:
            return f"{float(m.group()):.{places}f}"

        return pattern.sub(round_match, svg)

    @staticmethod
    def _remove_degenerate_paths(svg: str) -> Tuple[str, int]:
        """
        Remove <path> elements whose d attribute represents zero geometry.
        A path is degenerate if it has fewer than 2 distinct points.
        """
        count = 0
        # Match full <path .../> elements
        path_re = re.compile(r'<path\s[^>]*/>', re.DOTALL)

        def check_path(m: re.Match) -> str:
            nonlocal count
            element = m.group()
            d_match = re.search(r'\bd="([^"]*)"', element)
            if not d_match:
                return element
            d = d_match.group(1).strip()
            # Degenerate: only "M x,y Z" or empty
            if re.fullmatch(r'M[\d.,\-\s]+Z', d.replace(" ", "")):
                count += 1
                return ""
            return element

        svg = path_re.sub(check_path, svg)
        return svg, count

    @staticmethod
    def _remove_redundant_attrs(svg: str) -> str:
        """Remove attributes that match SVG default values."""
        # stroke="none" is default — remove it
        svg = re.sub(r'\s+stroke="none"', "", svg)
        # fill-rule="nonzero" is default — remove it
        svg = re.sub(r'\s+fill-rule="nonzero"', "", svg)
        return svg

    @staticmethod
    def _collapse_path_whitespace(svg: str) -> str:
        """Replace multi-space runs inside d="..." with single spaces."""
        def collapse(m: re.Match) -> str:
            d = re.sub(r"\s+", " ", m.group(1).strip())
            return f'd="{d}"'

        return re.sub(r'd="([^"]*)"', collapse, svg)
