#!/usr/bin/env python3
"""
Automated Python Play Store Review Downloader & Extractor for Groww.
Fetches real reviews directly from Google Play Store using the programmatic google-play-scraper API.
No manual exports or browser interaction required.
"""

import sys
import os
import argparse
import json
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.groww_pulse.ingestion.extractor import download_and_extract_8weeks
from rich.console import Console
from rich.table import Table

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Automated Python Google Play Store Review Downloader for Groww")
    parser.add_argument("--package-id", type=str, default="com.nextbillion.groww", help="Play Store App Package ID (default: com.nextbillion.groww)")
    parser.add_argument("--weeks", type=int, default=8, help="Number of weeks to look back (default: 8)")
    parser.add_argument("--max-reviews", type=int, default=5000, help="Maximum reviews to download (default: 5000)")
    parser.add_argument("--output-dir", type=str, default="data", help="Output directory for JSON datasets (default: data)")

    args = parser.parse_args()

    console.print(f"[bold green]Starting automated Python Google Play review download for:[/bold green] [yellow]{args.package_id}[/yellow]")
    console.print(f"[cyan]Lookback timeframe:[/cyan] {args.weeks} weeks | [cyan]Max reviews limit:[/cyan] {args.max_reviews}")

    start_time = datetime.now(timezone.utc)
    stats = download_and_extract_8weeks(
        package_id=args.package_id,
        weeks_lookback=args.weeks,
        max_reviews=args.max_reviews,
        output_dir=args.output_dir
    )
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Display clean formatted summary
    table = Table(title=f"Google Play Store Review Extraction Results ({stats['package_id']})")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold green")

    table.add_row("Total Raw Reviews Fetched", str(stats["total_raw_reviews"]))
    table.add_row("Noise / 1-Word Filtered Out", str(stats["noise_dropped_count"]))
    table.add_row("High-Signal Sanitized Reviews", str(stats["total_sanitized_reviews"]))
    table.add_row("PII Redacted Instances", str(stats["pii_redacted_count"]))
    table.add_row("Date Range (Earliest)", str(stats["date_range"]["earliest"]))
    table.add_row("Date Range (Latest)", str(stats["date_range"]["latest"]))
    table.add_row("Raw Dataset File", stats["raw_file"])
    table.add_row("Sanitized Dataset File", stats["sanitized_file"])
    table.add_row("Extraction Runtime", f"{duration:.2f} seconds")

    console.print(table)
    console.print("[bold green]Automated download & extraction completed successfully![/bold green]")

if __name__ == "__main__":
    main()
