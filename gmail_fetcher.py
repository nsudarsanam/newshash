"""Fetch newsletter emails from Gmail and extract links."""

import base64
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email import message_from_bytes
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from googleapiclient.errors import HttpError

# Patterns that suggest a message is a newsletter, not personal mail
NEWSLETTER_INDICATORS = [
    "list-unsubscribe",
    "list-id",
    "x-campaign",
    "x-mailer",
    "unsubscribe",
    "newsletter",
    "digest",
]

# URL patterns to skip (unsubscribe pages, mailto/tel, pure social homepages, share dialogs)
# NOTE: Keep this list narrow — over-filtering kills entire newsletters.
# Many newsletters (ConvertKit, Beehiiv, etc.) wrap ALL links in tracking redirects,
# so filtering on click./open./track. subdomains drops every link from those senders.
# utm_ params are just analytics on normal article URLs; we already strip query strings
# during deduplication, so there's no reason to drop the URL itself.
SKIP_URL_PATTERNS = re.compile(
    r"(unsubscribe|optout|opt-out|mailto:|tel:|"
    r"list-manage\.com|mandrillapp\.com|"
    r"facebook\.com/sharer|twitter\.com/intent|linkedin\.com/share"
    r"|instagram\.com/?$|twitter\.com/?$|facebook\.com/?$|youtube\.com/?$)",
    re.IGNORECASE,
)

SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".pdf"}

# Sender/subject keywords that should always be excluded (case-insensitive substring match)
EXCLUDED_KEYWORDS = [
    "eventbrite",
    "women's prison",
    "womens prison",
    "prisoner news",
    "oakland y ",       # Oakland YMCA / Oakland Y newsletters
    "ymca of",
    "summary"
]


@dataclass
class NewsletterEmail:
    message_id: str
    subject: str
    sender: str
    date: datetime
    links: list[dict] = field(default_factory=list)  # [{url, anchor_text}]


def _decode_body(part) -> str:
    data = part.get("body", {}).get("data", "")
    if not data:
        return ""
    return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")


def _extract_links_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        url = tag["href"].strip()
        anchor = tag.get_text(separator=" ", strip=True)

        # Basic cleanup
        url = re.sub(r"\s+", "", url)
        if not url.startswith("http"):
            continue

        parsed = urlparse(url)
        _, ext = os.path.splitext(parsed.path)
        if ext.lower() in SKIP_EXTENSIONS:
            continue
        if SKIP_URL_PATTERNS.search(url):
            continue

        # Deduplicate by domain+path (ignore query strings which are often tracking)
        dedup_key = parsed.netloc + parsed.path.rstrip("/")
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        links.append({"url": url, "anchor_text": anchor[:200]})

    return links


def _extract_links_from_text(text: str) -> list[dict]:
    urls = re.findall(r"https?://[^\s<>\"']+", text)
    links = []
    seen = set()

    for url in urls:
        url = url.rstrip(".,);")
        if SKIP_URL_PATTERNS.search(url):
            continue
        parsed = urlparse(url)
        _, ext = os.path.splitext(parsed.path)
        if ext.lower() in SKIP_EXTENSIONS:
            continue
        dedup_key = parsed.netloc + parsed.path.rstrip("/")
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        links.append({"url": url, "anchor_text": ""})

    return links


def _parse_parts(parts, html_bodies, text_bodies):
    for part in parts:
        mime = part.get("mimeType", "")
        sub = part.get("parts", [])
        if sub:
            _parse_parts(sub, html_bodies, text_bodies)
        elif mime == "text/html":
            html_bodies.append(_decode_body(part))
        elif mime == "text/plain":
            text_bodies.append(_decode_body(part))


def _is_newsletter(headers: dict) -> bool:
    header_block = " ".join(headers.values()).lower()
    return any(ind in header_block for ind in NEWSLETTER_INDICATORS)


def _is_excluded(subject: str, sender: str) -> bool:
    combined = (subject + " " + sender).lower()
    return any(kw in combined for kw in EXCLUDED_KEYWORDS)


def fetch_newsletters(
    service, days: int = 7, max_results: int = 150, verbose: bool = False
) -> list[NewsletterEmail]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    after_ts = int(since.timestamp())
    query = f"in:inbox -category:promotions after:{after_ts} -from:me"

    try:
        response = service.users().messages().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
    except HttpError as e:
        raise RuntimeError(f"Gmail API error: {e}") from e

    message_ids = [m["id"] for m in response.get("messages", [])]
    if verbose:
        print(f"[debug] {len(message_ids)} emails found in last {days} days")

    newsletters = []

    for msg_id in message_ids:
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except HttpError:
            continue

        payload = msg.get("payload", {})
        raw_headers = payload.get("headers", [])
        headers = {h["name"].lower(): h["value"] for h in raw_headers}

        subject = headers.get("subject", "(no subject)")
        sender = headers.get("from", "unknown")

        if not _is_newsletter(headers):
            if verbose:
                print(f"[debug] SKIP (not newsletter): {subject!r} from {sender!r}")
            continue

        if _is_excluded(subject, sender):
            if verbose:
                print(f"[debug] SKIP (excluded): {subject!r} from {sender!r}")
            continue

        date_str = headers.get("date", "")
        try:
            from email.utils import parsedate_to_datetime
            date = parsedate_to_datetime(date_str).astimezone(timezone.utc)
        except Exception:
            date = since

        html_bodies, text_bodies = [], []
        parts = payload.get("parts", [])
        if parts:
            _parse_parts(parts, html_bodies, text_bodies)
        else:
            mime = payload.get("mimeType", "")
            if mime == "text/html":
                html_bodies.append(_decode_body(payload))
            else:
                text_bodies.append(_decode_body(payload))

        if html_bodies:
            links = _extract_links_from_html("\n".join(html_bodies))
        else:
            links = _extract_links_from_text("\n".join(text_bodies))

        if not links:
            if verbose:
                print(f"[debug] SKIP (no links extracted): {subject!r}")
            continue

        if verbose:
            print(f"[debug] ACCEPT ({len(links)} links): {subject!r}")

        newsletters.append(NewsletterEmail(
            message_id=msg_id,
            subject=subject,
            sender=sender,
            date=date,
            links=links,
        ))

        # Gentle rate limiting
        time.sleep(0.05)

    return newsletters
