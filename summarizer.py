"""Use Gemini to summarize and categorize newsletter links."""

import json
import os
import re

import google.generativeai as genai

from gmail_fetcher import NewsletterEmail

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-3-flash-preview")

SYSTEM_PROMPT = """You are a curator for a well-read, culturally curious reader. Your job is to surface the best links from a week of newsletters.

Your task: given links extracted from newsletter emails (with anchor text and source), identify the interesting ones and group them into meaningful categories.

Prioritization (in order):
1. Literature, books, reading, writers, translation, literary culture
2. Art, visual culture, design, architecture, museums, galleries
3. History, ideas, philosophy, criticism, essays
4. Film, music, theatre, performance
5. Science, nature, environment
6. Technology (only genuinely interesting pieces — not hype or product announcements)
7. Business/entrepreneurship (only if unusually insightful)

Guidelines:
- Keep the bar low for culture/literature/art — include reviews, interviews, profiles, recommendations
- Skip: homepage links, social media profiles, unsubscribe/manage pages, obvious self-promotion, product landing pages
- Even if a URL is a tracking redirect (e.g. click.convertkit-mail.com), use the anchor text to understand what it links to and keep it if it sounds interesting
- Group by topic using rich category names (e.g. "Books & Reading", "Art & Visual Culture", "Literary Criticism", "Film & Television", "Music", "Ideas & Essays", "Science & Nature", "Technology", "Architecture & Design")
- For each link, write a 1-2 sentence description based on anchor text and URL context
- Skip only truly uninformative links (no anchor text AND unrecognizable URL with no context)

Return a JSON object with this structure:
{
  "categories": [
    {
      "name": "Category Name",
      "links": [
        {
          "url": "https://...",
          "title": "Human-readable title",
          "description": "What this is about in 1-2 sentences",
          "source": "Newsletter name that contained this",
          "message_id": "the message_id value from the input"
        }
      ]
    }
  ],
  "total_interesting": <number of links you kept>,
  "total_skipped": <number you filtered out>
}"""


# Anchor texts that indicate action/navigation links rather than content
_SKIP_ANCHOR_RE = re.compile(
    r"^\s*(subscribe(\s+(here|now))?|unsubscribe|"
    r"view\s+(in\s+browser|online|this\s+email(\s+online)?|in\s+your\s+browser)|"
    r"click\s+here|read\s+more|"
    r"manage\s+(preferences|subscription|your\s+subscription)|"
    r"update\s+(your\s+)?preferences|email\s+preferences|"
    r"forward(\s+to\s+a\s+friend)?|share|tweet(\s+this)?|"
    r"privacy\s+policy|terms(\s+of\s+(service|use))?|"
    r"opt\s*out|opt-out|follow\s+us|"
    r"having\s+trouble|can'?t\s+see|display\s+images)\s*$",
    re.IGNORECASE,
)

# URLs where the path or query contains an opaque JWT/base64 token with no semantic value
_OPAQUE_URL_RE = re.compile(
    r"(?:/eyJ[A-Za-z0-9_=.-]{15,}|[?&]j=eyJ[A-Za-z0-9_=.-]{15,})",
)


def _is_useful_pinned_link(url: str, anchor: str) -> bool:
    if anchor and _SKIP_ANCHOR_RE.match(anchor):
        return False
    if _OPAQUE_URL_RE.search(url):
        return False
    return True


def _build_links_payload(newsletters: list[NewsletterEmail]) -> str:
    items = []
    for nl in newsletters:
        for link in nl.links:
            items.append({
                "url": link["url"],
                "anchor_text": link["anchor_text"] or "(no text)",
                "source": nl.subject,
                "sender": nl.sender,
                "message_id": nl.message_id,
            })
    return json.dumps(items, indent=2)


def _build_pinned_sections(pinned: list[NewsletterEmail]) -> list[dict]:
    sections = []
    for nl in pinned:
        sections.append({
            "subject": nl.subject,
            "sender": nl.sender,
            "message_id": nl.message_id,
            "date": nl.date.strftime("%B %d, %Y"),
            "links": [
                {
                    "url": link["url"],
                    "title": link["anchor_text"] or link["url"],
                    "source": nl.subject,
                    "message_id": nl.message_id,
                }
                for link in nl.links
                if _is_useful_pinned_link(link["url"], link["anchor_text"])
            ],
        })
    return sections


def summarize_newsletters(newsletters: list[NewsletterEmail]) -> dict:
    pinned = [nl for nl in newsletters if nl.is_pinned]
    regular = [nl for nl in newsletters if not nl.is_pinned]

    result: dict = {"pinned_newsletters": _build_pinned_sections(pinned)}

    if not regular:
        result.update({"categories": [], "total_interesting": 0, "total_skipped": 0})
        return result

    payload = _build_links_payload(regular)
    total_links = sum(len(nl.links) for nl in regular)

    prompt = f"""{SYSTEM_PROMPT}

Here are {total_links} links extracted from {len(regular)} newsletter emails received in the past 7 days.

Please identify the interesting ones, group them into categories, and return your analysis as JSON.

Links:
{payload}"""

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        gemini_result = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            gemini_result = json.loads(match.group())
        else:
            gemini_result = {"categories": [], "total_interesting": 0, "total_skipped": 0, "error": text[:200]}

    result.update(gemini_result)
    return result
