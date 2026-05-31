#!/usr/bin/env python3
"""Gmail Newsletter Link Summarizer — finds interesting links from the past 10 days."""

from __future__ import annotations

import base64
import email.mime.application
import email.mime.multipart
import email.mime.text
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv()

console = Console()


def run(days: int = 10, max_emails: int = 200, verbose: bool = False, pinned_config: str | None = None):
    from auth import get_gmail_service
    from gmail_fetcher import fetch_newsletters, load_pinned_patterns
    from summarizer import summarize_newsletters
    from html_report import generate_html

    pinned_patterns = load_pinned_patterns(pinned_config)
    if pinned_patterns:
        console.print(f"[dim]Loaded [bold]{len(pinned_patterns)}[/bold] pinned newsletter pattern(s).[/dim]")

    console.print("[dim]Authenticating with Gmail...[/dim]")
    try:
        service = get_gmail_service()
    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    console.print(f"[dim]Fetching newsletters from the last {days} days...[/dim]")
    newsletters = fetch_newsletters(
        service, days=days, max_results=max_emails, verbose=verbose,
        pinned_patterns=pinned_patterns,
    )

    if not newsletters:
        console.print("[yellow]No newsletters found in the past 7 days.[/yellow]")
        sys.exit(0)

    pinned = [nl for nl in newsletters if nl.is_pinned]
    regular = [nl for nl in newsletters if not nl.is_pinned]
    regular_links = sum(len(nl.links) for nl in regular)
    pinned_links = sum(len(nl.links) for nl in pinned)

    msg = (
        f"[dim]Found [bold]{len(newsletters)}[/bold] newsletters "
        f"([bold]{regular_links}[/bold] regular links"
    )
    if pinned:
        msg += f", [bold]{pinned_links}[/bold] pinned links from [bold]{len(pinned)}[/bold] pinned newsletter(s)"
    msg += "). Analyzing with Gemini...[/dim]"
    console.print(msg)

    result = summarize_newsletters(newsletters)

    if "error" in result:
        console.print(f"[red]Gemini returned an unexpected response:[/red] {result['error']}")
        sys.exit(1)

    categories = result.get("categories", [])
    if not categories:
        console.print("[yellow]No interesting links found this week.[/yellow]")
        sys.exit(0)

    html = generate_html(result, newsletter_count=len(newsletters), days=days)

    html_path = Path("digest.html")
    html_path.write_text(html, encoding="utf-8")

    console.print()
    console.print(Panel.fit(
        f"[bold green]Done![/bold green] "
        f"[bold]{result.get('total_interesting', 0)}[/bold] interesting links "
        f"across [bold]{len(categories)}[/bold] categories.\n"
        f"[dim]HTML: [cyan]{html_path.resolve()}[/cyan][/dim]",
        border_style="green",
    ))

    webbrowser.open(html_path.resolve().as_uri())

    _send_digest_email(service, html, html_path)


def _send_digest_email(service, html: str, html_path: Path):
    profile = service.users().getProfile(userId="me").execute()
    recipient = profile.get("emailAddress", "")
    if not recipient:
        console.print("[yellow]Could not determine Gmail address; skipping email delivery.[/yellow]")
        return

    msg = email.mime.multipart.MIMEMultipart()
    msg["To"] = recipient
    msg["From"] = recipient
    msg["Subject"] = "Summary"

    attachment = email.mime.application.MIMEApplication(
        html.encode("utf-8"), _subtype="octet-stream"
    )
    attachment.add_header(
        "Content-Disposition", "attachment", filename=html_path.name
    )
    msg.attach(attachment)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service.users().messages().send(userId="me", body={"raw": raw}).execute()

    console.print(f"[dim]Digest emailed to [cyan]{recipient}[/cyan].[/dim]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Summarize newsletter links from Gmail")
    parser.add_argument("--days", type=int, default=7, help="How many days back to look (default: 7)")
    parser.add_argument("--max-emails", type=int, default=150, help="Max emails to scan (default: 150)")
    parser.add_argument("--verbose", action="store_true", help="Show which emails are accepted/skipped")
    parser.add_argument(
        "--pinned-config", default=None,
        help="Path to pinned_newsletters.json (default: pinned_newsletters.json in script directory)"
    )
    args = parser.parse_args()

    run(days=args.days, max_emails=args.max_emails, verbose=args.verbose, pinned_config=args.pinned_config)
