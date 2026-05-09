"""Use Gemini to summarize and categorize newsletter links."""

import json
import os
import re

import google.generativeai as genai

from gmail_fetcher import NewsletterEmail

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-3-flash-preview")

SYSTEM_PROMPT = """You are a research assistant that reads newsletter links and identifies genuinely interesting content.

Your task: given a list of links extracted from newsletter emails (with their anchor text and source), identify the most interesting ones, then group them into meaningful categories.

Guidelines:
- Ignore generic homepage links, social profiles, unsubscribe pages, and obvious self-promotion
- Prioritize: articles, tools, research, projects, events, and ideas worth knowing about
- Group by topic (e.g. "AI & Machine Learning", "Design", "Engineering", "Business", "Science", "Culture & Society", etc.)
- For each link, write a 1-2 sentence description of what it's about based on its anchor text and URL
- If a link's purpose isn't clear from context, use your best judgment based on the domain/URL
- Skip truly uninformative links (no anchor text AND unclear URL)

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
          "source": "Newsletter name that contained this"
        }
      ]
    }
  ],
  "total_interesting": <number of links you kept>,
  "total_skipped": <number you filtered out>
}"""


def _build_links_payload(newsletters: list[NewsletterEmail]) -> str:
    items = []
    for nl in newsletters:
        for link in nl.links:
            items.append({
                "url": link["url"],
                "anchor_text": link["anchor_text"] or "(no text)",
                "source": nl.subject,
                "sender": nl.sender,
            })
    return json.dumps(items, indent=2)


def summarize_newsletters(newsletters: list[NewsletterEmail]) -> dict:
    if not newsletters:
        return {"categories": [], "total_interesting": 0, "total_skipped": 0}

    payload = _build_links_payload(newsletters)
    total_links = sum(len(nl.links) for nl in newsletters)

    prompt = f"""{SYSTEM_PROMPT}

Here are {total_links} links extracted from {len(newsletters)} newsletter emails received in the past 7 days.

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
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {"categories": [], "total_interesting": 0, "total_skipped": 0, "error": text[:200]}
