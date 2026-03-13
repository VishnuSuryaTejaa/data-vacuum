"""
Phase 5 — Output Formatter

Converts labelled results into a Pandas DataFrame and exports to
Apache Parquet (pyarrow + snappy compression) + a human-readable CSV.
"""

import os
from pathlib import Path
import pandas as pd
from rich.console import Console

import config

console = Console()


def export(
    results: list[dict],
    output_path: str = None,
) -> str:
    """
    Build a DataFrame with columns ['text', 'label', 'confidence_score']
    and save as Parquet + CSV.

    Returns the path to the Parquet file.
    """
    if not results:
        console.print("[yellow]  ⚠ No results to export.[/]")
        return ""

    output_path = output_path or os.path.join(
        config.DEFAULT_OUTPUT_DIR, config.DEFAULT_OUTPUT_FILE
    )

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    console.print(f"\n[bold cyan]Phase 5[/] → Exporting [bold]{len(results)}[/] "
                  f"labelled chunks…")

    df = pd.DataFrame([
        {
            "text": r["chunk"],
            "label": r["label"],
            "confidence_score": r["confidence_score"],
            "source_url": r.get("url", ""),
        }
        for r in results
    ])

    # Parquet export
    df.to_parquet(
        output_path,
        engine=config.PARQUET_ENGINE,
        compression=config.PARQUET_COMPRESSION,
        index=False,
    )
    parquet_size = os.path.getsize(output_path)
    console.print(f"  [green]✓[/] Parquet → [bold]{output_path}[/]  "
                  f"({parquet_size / 1024:.1f} KB)")

    # CSV export (for human inspection) — safe extension swap
    csv_path = str(Path(output_path).with_suffix(".csv"))
    df.to_csv(csv_path, index=False)
    csv_size = os.path.getsize(csv_path)
    console.print(f"  [green]✓[/] CSV    → [bold]{csv_path}[/]  "
                  f"({csv_size / 1024:.1f} KB)")

    # Summary stats
    console.print(f"\n  [bold]Dataset Summary[/]")
    console.print(f"  ├─ Total rows : {len(df)}")
    console.print(f"  ├─ Columns    : {list(df.columns)}")
    console.print(f"  ├─ Labels     : {df['label'].value_counts().to_dict()}")
    console.print(f"  └─ Avg conf.  : {df['confidence_score'].mean():.4f}")

    return output_path


def run(results: list[dict], output_path: str = None) -> str:
    """Alias for export."""
    return export(results, output_path)
