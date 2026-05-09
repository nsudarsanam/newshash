#!/usr/bin/env python3
"""Gmail Newsletter Link Summarizer — finds interesting links from the past 7 days."""

import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()

console = Console()


def run(days: int = 7, max_emails: int = 100, verbose: bool = False):
    from auth import get_gmail_service
    from gmail_fetcher import fetch_newsletters
    from summarizer import summarize_newsletters
    from html_report import generate_html

    console.print("[dim]Authenticating with Gmail...[/dim]")
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    console.print(f"[dim]Fetching newsletters from the last {days} days...[/dim]")
    newsletters = fetch_newsletters(service, days=days, max_results=max_emails, verbose=verbose)

    if not newsletters:
        console.print("[yellow]No newsletters found in the past 7 days.[/yellow]")
        sys.exit(0)

    total_links = sum(len(nl.links) for nl in newsletters)
    console.print(
        f"[dim]Found [bold]{len(newsletters)}[/bold] newsletters with "
        f"[bold]{total_links}[/bold] links. Analyzing with Gemini...[/dim]"
    )

    result = summarize_newsletters(newsletters)

    if "error" in result:
        console.print(f"[red]Gemini returned an unexpected response:[/red] {result['error']}")
        sys.exit(1)

    categories = result.get("categories", [])
    if not categories:
        console.print("[yellow]No interesting links found this week.[/yellow]")
        sys.exit(0)

    html = generate_html(result, newsletter_count=len(newsletters), days=days)

    output_path = Path("digest.html")
    output_path.write_text(html, encoding="utf-8")

    console.print()
    console.print(Panel.fit(
        f"[bold green]Done![/bold green] "
        f"[bold]{result.get('total_interesting', 0)}[/bold] interesting links "
        f"across [bold]{len(categories)}[/bold] categories.\n"
        f"[dim]Saved to [cyan]{output_path.resolve()}[/cyan][/dim]",
        border_style="green",
    ))

    webbrowser.open(output_path.resolve().as_uri())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Summarize newsletter links from Gmail")
    parser.add_argument("--days", type=int, default=7, help="How many days back to look (default: 7)")
    parser.add_argument("--max-emails", type=int, default=100, help="Max emails to scan (default: 100)")
    parser.add_argument("--verbose", action="store_true", help="Show which emails are accepted/skipped")
    args = parser.parse_args()

    run(days=args.days, max_emails=args.max_emails, verbose=args.verbose)
