#!/usr/bin/env python3
"""
VectorForge CLI
Converts raster images to SVG from the command line.

Usage:
    python scripts/vectorforge_cli.py input.png --colors 32 --detail 7 --output out.svg
    python scripts/vectorforge_cli.py portrait.jpg --mode portrait --colors 64 --detail 8
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from backend.preprocessing.image_prep import ImagePreprocessor
from backend.vectorizer.pipeline import (
    PipelineConfig,
    VectorizationMode,
    BackgroundHandling,
    VectorizationPipeline,
)

console = Console()


@click.command()
@click.argument("input_path", type=click.Path(exists=True, readable=True))
@click.option("--output", "-o", type=click.Path(), default=None,
              help="Output SVG path (default: <input_basename>.svg)")
@click.option("--mode", "-m",
              type=click.Choice(["auto", "icon", "logo", "illustration",
                                 "portrait", "photograph"], case_sensitive=False),
              default="auto", show_default=True,
              help="Vectorization mode / image type")
@click.option("--colors", "-c",
              type=click.Choice(["auto", "8", "16", "32", "64", "128", "256"]),
              default="auto", show_default=True,
              help="Number of palette colors")
@click.option("--custom-colors", type=int, default=None,
              help="Custom color count (2–256, overrides --colors)")
@click.option("--detail", "-d", type=click.IntRange(1, 10), default=5, show_default=True,
              help="Detail level: 1=coarse, 10=fine")
@click.option("--background", "-b",
              type=click.Choice(["keep", "remove", "transparent", "simplify"],
                                case_sensitive=False),
              default="keep", show_default=True,
              help="Background handling strategy")
@click.option("--watershed/--no-watershed", default=False,
              help="Use watershed for region boundary refinement")
@click.option("--max-size", type=int, default=2048, show_default=True,
              help="Maximum image dimension after resize")
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Print detailed pipeline stage info")
def main(
    input_path: str,
    output: str | None,
    mode: str,
    colors: str,
    custom_colors: int | None,
    detail: int,
    background: str,
    watershed: bool,
    max_size: int,
    verbose: bool,
) -> None:
    """
    VectorForge — Convert a raster image into an editable, colored SVG.

    Examples:\n
      python scripts/vectorforge_cli.py icon.png --colors 16 --detail 4\n
      python scripts/vectorforge_cli.py photo.jpg --mode photograph --colors 64 --detail 8\n
      python scripts/vectorforge_cli.py person.jpg --mode portrait --background remove
    """
    input_file = Path(input_path)
    output_file = Path(output) if output else input_file.with_suffix(".svg")

    console.rule("[bold cyan]VectorForge[/bold cyan]")
    console.print(f"  Input:  [green]{input_file}[/green]")
    console.print(f"  Output: [green]{output_file}[/green]")
    console.print(f"  Mode: [yellow]{mode}[/yellow]  Colors: [yellow]{colors}[/yellow]  Detail: [yellow]{detail}[/yellow]")
    console.rule()

    # ── Load image ──────────────────────────────────────────────────────
    try:
        preprocessor = ImagePreprocessor(max_dimension=max_size)
        with open(input_file, "rb") as f:
            raw_bytes = f.read()
        prepared = preprocessor.prepare(raw_bytes)
    except Exception as exc:
        console.print(f"[red]✗ Failed to load image:[/red] {exc}")
        sys.exit(1)

    console.print(
        f"  Loaded: [bold]{prepared.processed_size[0]}×{prepared.processed_size[1]}[/bold] px  "
        f"Alpha: {'yes' if prepared.has_alpha else 'no'}"
    )

    # ── Config ──────────────────────────────────────────────────────────
    if custom_colors:
        num_colors = max(2, min(256, custom_colors))
        auto = False
    elif colors == "auto":
        num_colors = 32
        auto = True
    else:
        num_colors = int(colors)
        auto = False

    config = PipelineConfig(
        num_colors=num_colors,
        detail_level=detail,
        mode=VectorizationMode(mode),
        background_handling=BackgroundHandling(background),
        use_watershed=watershed,
        auto_colors=auto,
    )

    # ── Run pipeline ─────────────────────────────────────────────────────
    pipeline = VectorizationPipeline(config=config)

    with Progress(
        SpinnerColumn(),
        BarColumn(bar_width=40),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Processing…", total=100)

        for event in pipeline.run_with_progress(prepared, len(raw_bytes)):
            progress.update(task, completed=event.percent,
                            description=f"[cyan]{event.stage}[/cyan] — {event.message}")
            if verbose and event.data:
                console.print(f"   [dim]{event.data}[/dim]")

    result = pipeline.last_result
    if result is None:
        console.print("[red]✗ Pipeline returned no result.[/red]")
        sys.exit(1)

    # ── Save SVG ─────────────────────────────────────────────────────────
    try:
        output_file.write_text(result.optimized_svg, encoding="utf-8")
    except Exception as exc:
        console.print(f"[red]✗ Could not write SVG:[/red] {exc}")
        sys.exit(1)

    # ── Report ────────────────────────────────────────────────────────────
    r = result
    qr = r.quality_report
    opt = r.optimization_report

    table = Table(title="VectorForge Result", show_header=False, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Value", style="green")

    table.add_row("Classification", r.analysis.classification.value)
    table.add_row("Image size", f"{prepared.processed_size[0]}×{prepared.processed_size[1]} px")
    table.add_row("Original file", f"{len(raw_bytes) // 1024} KB")
    table.add_row("SVG size", f"{opt.optimized_bytes // 1024} KB")
    table.add_row("Compression", f"{opt.size_reduction_pct:.1f}% reduced")
    table.add_row("Vector paths", str(r.svg_document.path_count))
    table.add_row("Colors used", str(r.svg_document.color_count))
    table.add_row("Processing time", f"{r.total_time_ms:.0f} ms")

    if qr:
        table.add_row("SSIM", f"{qr.ssim:.4f}")
        table.add_row("PSNR", f"{qr.psnr:.1f} dB")
        table.add_row("Reconstruction score", f"{qr.reconstruction_score:.1f} / 100")

    table.add_row("Output", str(output_file))

    console.print(table)
    console.print(f"\n[bold green]✓ Done![/bold green] SVG saved to [green]{output_file}[/green]")
    console.print("[dim]Open in Inkscape, Figma, or Illustrator to edit individual paths.[/dim]")


if __name__ == "__main__":
    main()
