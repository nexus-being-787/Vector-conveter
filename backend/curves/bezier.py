"""
VectorForge — Bézier Curve Fitting Module
Stage 6: Simplify contours with Douglas-Peucker and fit cubic Bézier curves.

Implements the Schneider "An Algorithm for Automatically Fitting Digitized Curves"
adapted for SVG path generation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from backend.contours.extractor import ExtractedContour

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CubicBezier:
    """Four control points of a cubic Bézier segment."""
    p0: np.ndarray  # anchor start  (x, y)
    p1: np.ndarray  # control start
    p2: np.ndarray  # control end
    p3: np.ndarray  # anchor end    (x, y)


@dataclass
class PathSegment:
    """One segment: either a straight line or a cubic Bézier."""
    is_bezier: bool
    bezier: Optional[CubicBezier]
    line_end: Optional[np.ndarray]  # for straight segments, the endpoint


@dataclass
class FittedPath:
    """A complete SVG path for one contour."""
    start: np.ndarray
    segments: List[PathSegment]
    is_closed: bool
    is_hole: bool


# ─────────────────────────────────────────────────────────────────────────────
# Douglas-Peucker simplification
# ─────────────────────────────────────────────────────────────────────────────

def douglas_peucker(points: np.ndarray, epsilon: float) -> np.ndarray:
    """
    Recursive Douglas-Peucker line simplification.

    Args:
        points: Nx2 float32 array.
        epsilon: Maximum allowed distance from simplified line.

    Returns:
        Simplified Mx2 float32 array.
    """
    if len(points) <= 2:
        return points

    # Find point with maximum distance from the line (first ↔ last)
    start, end = points[0], points[-1]
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)

    if line_len < 1e-9:
        distances = np.linalg.norm(points - start, axis=1)
    else:
        line_unit = line_vec / line_len
        vecs = points - start
        projections = np.dot(vecs, line_unit)
        projected = start + np.outer(projections, line_unit)
        distances = np.linalg.norm(points - projected, axis=1)

    max_idx = int(np.argmax(distances))
    max_dist = float(distances[max_idx])

    if max_dist > epsilon:
        left = douglas_peucker(points[: max_idx + 1], epsilon)
        right = douglas_peucker(points[max_idx:], epsilon)
        return np.vstack([left[:-1], right])

    return np.array([start, end], dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# Cubic Bézier fitting (Schneider algorithm)
# ─────────────────────────────────────────────────────────────────────────────

def _chord_length_parametrize(points: np.ndarray) -> np.ndarray:
    diffs = np.diff(points, axis=0)
    dists = np.linalg.norm(diffs, axis=1)
    t = np.concatenate([[0.0], np.cumsum(dists)])
    total = t[-1]
    if total < 1e-9:
        return np.linspace(0, 1, len(points))
    return t / total


def _bezier_q(ctrl_pts: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Evaluate cubic Bézier at parameter t (vectorised)."""
    p0, p1, p2, p3 = ctrl_pts
    u = 1 - t
    return (
        u[:, None] ** 3 * p0
        + 3 * u[:, None] ** 2 * t[:, None] * p1
        + 3 * u[:, None] * t[:, None] ** 2 * p2
        + t[:, None] ** 3 * p3
    )


def _fit_cubic(
    points: np.ndarray,
    t: np.ndarray,
    tan1: np.ndarray,
    tan2: np.ndarray,
) -> np.ndarray:
    """
    Fit a single cubic Bézier to a set of points with given tangents.
    Returns 4x2 control-point array.
    """
    n = len(points)
    # Build A matrix (Bernstein basis × tangent)
    b1 = 3 * (1 - t) ** 2 * t
    b2 = 3 * (1 - t) * t ** 2
    a1 = b1[:, None] * tan1
    a2 = b2[:, None] * tan2

    c00 = float(np.sum(a1 * a1))
    c01 = float(np.sum(a1 * a2))
    c11 = float(np.sum(a2 * a2))

    # Right-hand side
    p0, p3 = points[0], points[-1]
    u3 = (1 - t) ** 3
    v3 = t ** 3
    x = points - (u3[:, None] * p0 + 3 * b1[:, None] * p0 + 3 * b2[:, None] * p3 + v3[:, None] * p3)
    # Actually the correct rhs:
    tmp = points - (
        (1 - t[:, None]) ** 3 * p0
        + 3 * (1 - t[:, None]) ** 2 * t[:, None] * p0
        + 3 * (1 - t[:, None]) * t[:, None] ** 2 * p3
        + t[:, None] ** 3 * p3
    )
    x0 = float(np.sum(tmp * a1))
    x1 = float(np.sum(tmp * a2))

    det = c00 * c11 - c01 * c01
    if abs(det) < 1e-9:
        # Fall back: use chord-length heuristic
        d = np.linalg.norm(p3 - p0) / 3.0
        alpha1 = alpha2 = d
    else:
        alpha1 = (x0 * c11 - x1 * c01) / det
        alpha2 = (c00 * x1 - c01 * x0) / det
        alpha1 = max(alpha1, 1e-3)
        alpha2 = max(alpha2, 1e-3)

    ctrl = np.array([
        p0,
        p0 + alpha1 * tan1,
        p3 + alpha2 * tan2,
        p3,
    ], dtype=np.float32)
    return ctrl


def fit_bezier_path(
    points: np.ndarray,
    error_threshold: float = 4.0,
    max_iterations: int = 4,
) -> List[np.ndarray]:
    """
    Fit a sequence of cubic Bézier segments to a polyline.

    Returns:
        List of 4x2 control-point arrays.
    """
    if len(points) < 2:
        return []
    if len(points) == 2:
        p0, p3 = points[0], points[1]
        d = (p3 - p0) / 3.0
        return [np.array([p0, p0 + d, p3 - d, p3], dtype=np.float32)]

    segments: List[np.ndarray] = []
    _fit_recursive(points, 0, len(points) - 1, error_threshold, segments, max_iterations)
    return segments


def _compute_tangent(points: np.ndarray, idx: int, forward: bool) -> np.ndarray:
    n = len(points)
    if forward:
        v = points[min(idx + 1, n - 1)] - points[idx]
    else:
        v = points[max(idx - 1, 0)] - points[idx]
    norm = np.linalg.norm(v)
    return v / norm if norm > 1e-9 else np.array([1.0, 0.0], dtype=np.float32)


def _fit_recursive(
    points: np.ndarray,
    first: int,
    last: int,
    error: float,
    out: List[np.ndarray],
    max_iter: int,
) -> None:
    segment = points[first: last + 1]
    if len(segment) < 2:
        return
    if len(segment) == 2:
        p0, p3 = segment[0], segment[1]
        d = (p3 - p0) / 3.0
        out.append(np.array([p0, p0 + d, p3 - d, p3], dtype=np.float32))
        return

    tan1 = _compute_tangent(points, first, forward=True)
    tan2 = _compute_tangent(points, last, forward=False)
    t = _chord_length_parametrize(segment)
    ctrl = _fit_cubic(segment, t, tan1, tan2)

    # Measure max error
    fitted = _bezier_q(ctrl, t)
    dists = np.linalg.norm(segment - fitted, axis=1)
    max_err = float(np.max(dists))
    max_err_idx = int(np.argmax(dists)) + first

    if max_err < error:
        out.append(ctrl)
        return

    # Split at the point of maximum error and recurse
    split = max(first + 1, min(max_err_idx, last - 1))
    _fit_recursive(points, first, split, error, out, max_iter)
    _fit_recursive(points, split, last, error, out, max_iter)


# ─────────────────────────────────────────────────────────────────────────────
# Public: main fitter
# ─────────────────────────────────────────────────────────────────────────────

class BezierFitter:
    """
    Converts ExtractedContours into smooth FittedPaths.

    detail_level: 1 (very simplified) to 10 (very detailed)
    """

    # epsilon = base / detail_level  (higher detail → smaller epsilon → less simplification)
    DP_BASE_EPSILON = 20.0
    BEZIER_ERROR_BASE = 8.0

    def __init__(self, detail_level: int = 5) -> None:
        detail_level = max(1, min(10, detail_level))
        self.detail_level = detail_level
        self.dp_epsilon = self.DP_BASE_EPSILON / detail_level
        self.bezier_error = self.BEZIER_ERROR_BASE / detail_level

    def fit_contour(self, contour: ExtractedContour) -> Optional[FittedPath]:
        """Simplify and fit one contour to Bézier segments."""
        pts = contour.points  # Nx2 float32
        if len(pts) < 3:
            return None

        # Douglas-Peucker simplification
        simplified = douglas_peucker(pts, self.dp_epsilon)
        if len(simplified) < 2:
            return None

        # Fit Bézier curves
        bezier_segments = fit_bezier_path(simplified, error_threshold=self.bezier_error)
        if not bezier_segments:
            return None

        path_segments: List[PathSegment] = []
        for ctrl in bezier_segments:
            path_segments.append(PathSegment(
                is_bezier=True,
                bezier=CubicBezier(
                    p0=ctrl[0], p1=ctrl[1], p2=ctrl[2], p3=ctrl[3]
                ),
                line_end=None,
            ))

        return FittedPath(
            start=bezier_segments[0][0],
            segments=path_segments,
            is_closed=True,
            is_hole=contour.is_hole,
        )
