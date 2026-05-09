#!/usr/bin/env python3
"""Gmail Newsletter Link Summarizer — finds interesting links from the past 7 days."""

import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich import box

load_dotenv()

console = Console()


def _print_header(newsletter_count: int, days: int):
    console.print()
    console.print(Panel.fit(
        f"[bold cyan]Newsletter Link Digest[/bold cyan]\n"
        f"[dim]Last {days} days · {newsletter_count} newsletters scanned[/dim]",
        border_style="cyan",
    ))
    console.print()


def _print_category(category: dict, index: int):
    name = category.get("name", "Misc")
    links = category.get("links", [])
    if not links:
        return

    console.print(Rule(f"[bold yellow]{name}[/bold yellow] [dim]({len(links)} links)[/dim]"))
    console.print()

    for link in links:
        title = link.get("title") or link.get("url", "")
        desc = link.get("description", "")
        url = link.get("url", "")
        source = link.get("source", "")

        console.print(f"  [bold white]{title}[/bold white]")
        if desc:
            console.print(f"  [dim]{desc}[/dim]")
        console.print(f"  [blue underline]{url}[/blue underline]")
        if source:
            console.print(f"  [dim italic]via {source}[/dim italic]")
        console.print()


def _print_summary(result: dict):
    kept = result.get("total_interesting", 0)
    skipped = result.get("total_skipped", 0)
    console.print(Rule())
    console.print(
        f"[dim]Showing [bold]{kept}[/bold] interesting links "
        f"({skipped} filtered out)[/dim]"
    )
    console.print()


def run(days: int = 7, max_emails: int = 50):
    from auth import get_gmail_service
    from gmail_fetcher import fetch_newsletters
    from summarizer import summarize_newsletters

    console.print("[dim]Authenticating with Gmail...[/dim]")
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    console.print(f"[dim]Fetching newsletters from the last {days} days...[/dim]")
    newsletters = fetch_newsletters(service, days=days, max_results=max_emails)

    if not newsletters:
        console.print("[yellow]No newsletters found in the past 7 days.[/yellow]")
        sys.exit(0)

    total_links = sum(len(nl.links) for nl in newsletters)
    console.print(
        f"[dim]Found [bold]{len(newsletters)}[/bold] newsletters with "
        f"[bold]{total_links}[/bold] links. Analyzing with Claude...[/dim]"
    )

    result = summarize_newsletters(newsletters)

    if "error" in result:
        console.print(f"[red]Claude returned an unexpected response:[/red] {result['error']}")
        sys.exit(1)

    categories = result.get("categories", [])
    if not categories:
        console.print("[yellow]No interesting links found this week.[/yellow]")
        sys.exit(0)

    _print_header(len(newsletters), days)
    for i, cat in enumerate(categories):
        _print_category(cat, i)
    _print_summary(result)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Summarize newsletter links from Gmail")
    parser.add_argument("--days", type=int, default=7, help="How many days back to look (default: 7)")
    parser.add_argument("--max-emails", type=int, default=50, help="Max emails to scan (default: 50)")
    args = parser.parse_args()

    run(days=args.days, max_emails=args.max_emails)
