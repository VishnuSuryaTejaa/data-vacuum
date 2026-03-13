#!/usr/bin/env python3
"""
Data Vacuum Pipeline — CLI Entry Point

Orchestrates all 5 phases:
  1. Search Orchestration  (LLM + Tavily)
  2. Web Scraping          (Playwright + stealth)
  3. Data Cleaning         (Trafilatura + chunking)
  4. Classification        (HuggingFace DeBERTa zero-shot)
  5. Export                (Pandas → Parquet)

Usage:
    python main.py \\
        --prompt "Find negative reviews of IoT hardware" \\
        --labels "Positive,Negative,Neutral" \\
        --include-comments
"""

import argparse
import os
import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import config
import phase1_search
import phase2_scrape
import phase3_clean
import phase4_classify
import phase5_export

console = Console()


def banner():
    title = Text("DATA VACUUM PIPELINE", style="bold bright_cyan")
    subtitle = Text("Web Data Harvester → ML-Ready Dataset",
                     style="dim white")
    console.print(Panel(
        Text.assemble(title, "\n", subtitle),
        border_style="bright_cyan",
        padding=(1, 4),
    ))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Data Vacuum: convert a prompt into a labelled, "
                    "ML-ready Parquet dataset."
    )
    parser.add_argument(
        "--prompt", "-p",
        required=True,
        help="Plain-English research topic / instruction.",
    )
    parser.add_argument(
        "--labels", "-l",
        required=True,
        help='Comma-separated classification labels, e.g. "Positive,Negative,Neutral".',
    )
    parser.add_argument(
        "--include-comments",
        action="store_true",
        default=False,
        help="Include user comments when extracting text (useful for forums/reviews).",
    )
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(config.DEFAULT_OUTPUT_DIR, config.DEFAULT_OUTPUT_FILE),
        help="Output Parquet file path.",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=config.MAX_QUERIES,
        help=f"Max number of search queries to generate (default {config.MAX_QUERIES}).",
    )
    return parser.parse_args()


def validate_keys():
    """Check that API keys are configured."""
    missing = []
    if not config.GROQ_API_KEY or config.GROQ_API_KEY.startswith("your_"):
        missing.append("GROQ_API_KEY")
    if not config.TAVILY_API_KEY or config.TAVILY_API_KEY.startswith("your_"):
        missing.append("TAVILY_API_KEY")
    if missing:
        console.print(f"\n[bold red]✗ Missing API keys:[/] {', '.join(missing)}")
        console.print("  Set them in the [bold].env[/] file and try again.\n")
        sys.exit(1)


def main():
    banner()
    args = parse_args()
    validate_keys()

    labels = [l.strip().title() for l in args.labels.split(",") if l.strip()]
    if not labels:
        console.print("[red]✗ No labels provided.[/]")
        sys.exit(1)

    console.print(f"\n[bold]Prompt:[/]   {args.prompt}")
    console.print(f"[bold]Labels:[/]   {labels}")
    console.print(f"[bold]Output:[/]   {args.output}")

    t0 = time.time()

    # ── Phase 1: Search ──────────────────────────────────────────────────
    urls = phase1_search.run(args.prompt, max_queries=args.max_queries)
    if not urls:
        console.print("\n[red]✗ No URLs collected. Pipeline aborted.[/]")
        sys.exit(1)

    # ── Phase 2: Scrape ──────────────────────────────────────────────────
    scraped = phase2_scrape.run(urls)
    if not scraped:
        console.print("\n[red]✗ No pages scraped. Pipeline aborted.[/]")
        sys.exit(1)

    # ── Phase 3: Clean ───────────────────────────────────────────────────
    chunks = phase3_clean.run(scraped, include_comments=args.include_comments)
    if not chunks:
        console.print("\n[red]✗ No text extracted. Pipeline aborted.[/]")
        sys.exit(1)

    # ── Phase 4: Classify ────────────────────────────────────────────────
    labelled = phase4_classify.run(chunks, labels, prompt=args.prompt)
    if not labelled:
        console.print("\n[red]✗ No chunks passed the confidence filter.[/]")
        console.print("  [dim]Tip: lower confidence gates in config.py or "
                      "broaden your prompt.[/]")
        sys.exit(1)

    # ── Phase 5: Export ──────────────────────────────────────────────────
    output_path = phase5_export.run(labelled, args.output)

    elapsed = time.time() - t0
    console.print(Panel(
        f"[bold green]Pipeline complete![/]\n"
        f"Time elapsed: {elapsed:.1f}s\n"
        f"Output: {output_path}",
        border_style="green",
        title="✓ Done",
    ))


if __name__ == "__main__":
    main()
