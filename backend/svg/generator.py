"""
VectorForge — SVG Generator Module
Stage 7: Assemble FittedPaths into a valid SVG 1.1 document.

Produces hierarchical grouped SVG with:
  - Correct viewBox
  - Hex fill colors
  - Closed paths using Bézier C commands
  - Background + region groups
  - Metadata block
  - No raster image embedding
"""

from __future__ import annotations

import datetime
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from backend.curves.bezier import FittedPath, PathSegment
from backend.segmentation.segmenter import Region

logger = logging.getLogger(__name__)

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


@dataclass
class SVGRegionGroup:
    region: Region
    paths: List[FittedPath]


@dataclass
class SVGDocument:
    svg_string: str
    viewbox: Tuple[int, int, int, int]  # x y w h
    path_count: int
    color_count: int
    byte_size: int


class SVGGenerator:
    """
    Assembles the final SVG document from fitted paths.
    """

    def __init__(
        self,
        decimal_places: int = 2,
        add_metadata: bool = True,
        source_classification: str = "UNKNOWN",
    ) -> None:
        self.decimal_places = decimal_places
        self.add_metadata = add_metadata
        self.source_classification = source_classification
        self._fmt = f"{{:.{decimal_places}f}}"

    def generate(
        self,
        region_groups: List[SVGRegionGroup],
        image_width: int,
        image_height: int,
        alpha_mask: Optional[np.ndarray] = None,
    ) -> SVGDocument:
        """
        Build the complete SVG document.

        Args:
            region_groups:  Ordered list of SVGRegionGroup (background first).
            image_width:    Original image width in pixels.
            image_height:   Original image height in pixels.
            alpha_mask:     Optional HxW alpha mask for clipping.

        Returns:
            SVGDocument containing the SVG string and stats.
        """
        # Register namespaces
        ET.register_namespace("", SVG_NS)
        ET.register_namespace("xlink", XLINK_NS)

        root = ET.Element(
            "svg",
            attrib={
                "xmlns": SVG_NS,
                "xmlns:xlink": XLINK_NS,
                "version": "1.1",
                "viewBox": f"0 0 {image_width} {image_height}",
                "width": str(image_width),
                "height": str(image_height),
                "id": "vectorforge-output",
            },
        )

        # Metadata
        if self.add_metadata:
            self._add_metadata(root)

        # Defs (clipPath for alpha if present)
        if alpha_mask is not None:
            defs = ET.SubElement(root, "defs")
            self._add_alpha_clippath(defs, alpha_mask, image_width, image_height)
            root.set("clip-path", "url(#alpha-clip)")

        # Build groups
        path_count = 0
        colors_used: set = set()

        for i, rg in enumerate(region_groups):
            group_id = "background" if rg.region.is_background else f"region-{i}"
            group_label = "background" if rg.region.is_background else f"color-{rg.region.color_hex.lstrip('#')}"

            g = ET.SubElement(
                root,
                "g",
                attrib={
                    "id": group_id,
                    "data-color": rg.region.color_hex,
                    "data-label": group_label,
                },
            )

            for path in rg.paths:
                d = self._path_data(path)
                if not d:
                    continue

                fill_rule = "evenodd" if any(p.is_hole for p in [path]) else "nonzero"

                ET.SubElement(
                    g,
                    "path",
                    attrib={
                        "d": d,
                        "fill": rg.region.color_hex,
                        "fill-rule": "evenodd",
                        "stroke": "none",
                    },
                )
                path_count += 1
                colors_used.add(rg.region.color_hex)

        svg_str = self._to_string(root)
        return SVGDocument(
            svg_string=svg_str,
            viewbox=(0, 0, image_width, image_height),
            path_count=path_count,
            color_count=len(colors_used),
            byte_size=len(svg_str.encode("utf-8")),
        )

    # ------------------------------------------------------------------ #
    # SVG path data                                                        #
    # ------------------------------------------------------------------ #

    def _path_data(self, path: FittedPath) -> str:
        """Convert a FittedPath into an SVG path d attribute string."""
        if not path.segments:
            return ""

        f = self._fmt.format
        parts: List[str] = []

        sx, sy = float(path.start[0]), float(path.start[1])
        parts.append(f"M{f(sx)},{f(sy)}")

        for seg in path.segments:
            if seg.is_bezier and seg.bezier is not None:
                bz = seg.bezier
                parts.append(
                    f"C{f(float(bz.p1[0]))},{f(float(bz.p1[1]))} "
                    f"{f(float(bz.p2[0]))},{f(float(bz.p2[1]))} "
                    f"{f(float(bz.p3[0]))},{f(float(bz.p3[1]))}"
                )
            elif seg.line_end is not None:
                ex, ey = float(seg.line_end[0]), float(seg.line_end[1])
                parts.append(f"L{f(ex)},{f(ey)}")

        if path.is_closed:
            parts.append("Z")

        return " ".join(parts)

    # ------------------------------------------------------------------ #
    # Alpha clip path                                                      #
    # ------------------------------------------------------------------ #

    def _add_alpha_clippath(
        self,
        defs: ET.Element,
        alpha: np.ndarray,
        w: int,
        h: int,
    ) -> None:
        """Add a simple rectangular clipPath for alpha images."""
        clip = ET.SubElement(defs, "clipPath", attrib={"id": "alpha-clip"})
        ET.SubElement(
            clip,
            "rect",
            attrib={"x": "0", "y": "0", "width": str(w), "height": str(h)},
        )

    # ------------------------------------------------------------------ #
    # Metadata                                                             #
    # ------------------------------------------------------------------ #

    def _add_metadata(self, root: ET.Element) -> None:
        meta = ET.SubElement(root, "metadata")
        desc = ET.SubElement(meta, "desc")
        desc.text = (
            f"Generated by VectorForge | "
            f"Source class: {self.source_classification} | "
            f"Date: {datetime.datetime.now(datetime.timezone.utc).isoformat()} | "
            f"No raster data embedded"
        )

    # ------------------------------------------------------------------ #
    # Serialisation                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _to_string(element: ET.Element) -> str:
        ET.indent(element, space="  ")
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            + ET.tostring(element, encoding="unicode", xml_declaration=False)
        )
