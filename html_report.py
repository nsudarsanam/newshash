"""Generate a nicely formatted HTML digest from the summarized newsletter links."""

from datetime import datetime, timezone


def generate_html(result: dict, newsletter_count: int, days: int) -> str:
    categories = result.get("categories", [])
    total_interesting = result.get("total_interesting", 0)
    total_skipped = result.get("total_skipped", 0)
    generated_at = datetime.now(timezone.utc).strftime("%B %d, %Y")

    category_nav = "\n".join(
        f'<a href="#cat-{i}">{cat["name"]}</a>'
        for i, cat in enumerate(categories)
        if cat.get("links")
    )

    category_sections = ""
    for i, cat in enumerate(categories):
        links = cat.get("links", [])
        if not links:
            continue

        cards = ""
        for link in links:
            title = _esc(link.get("title") or link.get("url", ""))
            desc = _esc(link.get("description", ""))
            url = _esc(link.get("url", ""))
            source = _esc(link.get("source", ""))
            domain = _domain(link.get("url", ""))
            message_id = link.get("message_id", "")
            gmail_url = f"googlegmail:///mail/u/0/#inbox/{message_id}" if message_id else ""

            email_link = (
                f'<a class="email-link" href="{gmail_url}" title="Open original email">✉ view email</a>'
                if gmail_url else ""
            )

            cards += f"""
            <article class="card">
                <div class="card-meta">
                    <span class="domain">{domain}</span>
                    {"<span class='source'>via " + source + "</span>" if source else ""}
                    {email_link}
                </div>
                <h3 class="card-title">
                    <a href="{url}" target="_blank" rel="noopener">{title}</a>
                </h3>
                {"<p class='card-desc'>" + desc + "</p>" if desc else ""}
            </article>"""

        category_sections += f"""
        <section class="category" id="cat-{i}">
            <h2 class="category-title">
                <span class="category-name">{_esc(cat["name"])}</span>
                <span class="category-count">{len(links)}</span>
            </h2>
            <div class="cards">{cards}
            </div>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Newsletter Digest — {generated_at}</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        :root {{
            --bg: #0f1117;
            --surface: #1a1d27;
            --surface2: #222636;
            --border: #2e3148;
            --accent: #6c8ff8;
            --accent-dim: #3d4f8a;
            --text: #e2e4f0;
            --text-dim: #8b8fa8;
            --text-faint: #555972;
            --tag-bg: #1e2238;
        }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
            font-size: 15px;
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* Header */
        header {{
            background: linear-gradient(135deg, #131625 0%, #1a1f35 100%);
            border-bottom: 1px solid var(--border);
            padding: 48px 24px 36px;
            text-align: center;
        }}

        .header-eyebrow {{
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 12px;
        }}

        header h1 {{
            font-size: clamp(24px, 4vw, 38px);
            font-weight: 700;
            color: var(--text);
            letter-spacing: -0.02em;
            margin-bottom: 8px;
        }}

        .header-sub {{
            color: var(--text-dim);
            font-size: 14px;
            margin-bottom: 24px;
        }}

        .stats {{
            display: inline-flex;
            gap: 24px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 12px 24px;
            font-size: 13px;
        }}

        .stat {{ color: var(--text-dim); }}
        .stat strong {{ color: var(--text); font-weight: 600; }}

        /* Nav */
        nav {{
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 0 24px;
            display: flex;
            gap: 4px;
            overflow-x: auto;
            scrollbar-width: none;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        nav::-webkit-scrollbar {{ display: none; }}

        nav a {{
            display: inline-block;
            padding: 14px 16px;
            font-size: 13px;
            font-weight: 500;
            color: var(--text-dim);
            text-decoration: none;
            white-space: nowrap;
            border-bottom: 2px solid transparent;
            transition: color 0.15s, border-color 0.15s;
        }}

        nav a:hover {{
            color: var(--text);
            border-bottom-color: var(--accent);
        }}

        /* Main layout */
        main {{
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 24px 80px;
        }}

        /* Category sections */
        .category {{ margin-bottom: 56px; }}

        .category-title {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-dim);
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
        }}

        .category-name {{ color: var(--text); }}

        .category-count {{
            background: var(--accent-dim);
            color: var(--accent);
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 20px;
            letter-spacing: 0.05em;
        }}

        /* Cards */
        .cards {{ display: flex; flex-direction: column; gap: 12px; }}

        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 18px 20px;
            transition: border-color 0.15s, background 0.15s;
        }}

        .card:hover {{
            border-color: var(--accent-dim);
            background: var(--surface2);
        }}

        .card-meta {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 6px;
        }}

        .domain {{
            font-size: 11px;
            font-weight: 600;
            color: var(--accent);
            background: var(--tag-bg);
            border: 1px solid var(--accent-dim);
            padding: 2px 8px;
            border-radius: 6px;
            letter-spacing: 0.03em;
        }}

        .source {{
            font-size: 11px;
            color: var(--text-faint);
        }}

        .card-title {{
            font-size: 15px;
            font-weight: 600;
            line-height: 1.4;
            margin-bottom: 6px;
        }}

        .card-title a {{
            color: var(--text);
            text-decoration: none;
            transition: color 0.15s;
        }}

        .card-title a:hover {{ color: var(--accent); }}

        .card-desc {{
            font-size: 13px;
            color: var(--text-dim);
            line-height: 1.55;
        }}

        .email-link {{
            margin-left: auto;
            font-size: 11px;
            color: var(--text-faint);
            text-decoration: none;
            transition: color 0.15s;
        }}

        .email-link:hover {{ color: var(--accent); }}

        /* Footer */
        footer {{
            text-align: center;
            padding: 32px 24px;
            border-top: 1px solid var(--border);
            font-size: 12px;
            color: var(--text-faint);
        }}

        /* Responsive */
        @media (max-width: 600px) {{
            header {{ padding: 32px 16px 24px; }}
            main {{ padding: 24px 16px 60px; }}
            .stats {{ flex-direction: column; gap: 8px; text-align: center; }}
        }}

        /* Print / PDF */
        @media print {{
            nav {{ display: none; }}
            body {{ font-size: 13px; }}
            header {{ padding: 32px 24px 24px; }}
            main {{ padding: 24px; }}
            .card {{ break-inside: avoid; }}
            .category {{ break-inside: avoid-page; }}
            .card-title a {{ color: #e2e4f0; }}
        }}
    </style>
</head>
<body>
    <header>
        <p class="header-eyebrow">Newsletter Digest</p>
        <h1>What's Worth Reading</h1>
        <p class="header-sub">{generated_at} &nbsp;·&nbsp; Last {days} days</p>
        <div class="stats">
            <span class="stat"><strong>{newsletter_count}</strong> newsletters</span>
            <span class="stat"><strong>{total_interesting}</strong> interesting links</span>
            <span class="stat"><strong>{total_skipped}</strong> filtered out</span>
        </div>
    </header>

    <nav>{category_nav}</nav>

    <main>{category_sections}
    </main>

    <footer>Generated from your Gmail inbox &nbsp;·&nbsp; {generated_at}</footer>
</body>
</html>"""


def generate_pdf(html: str) -> bytes:
    from weasyprint import HTML
    return HTML(string=html).write_pdf()


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        return host.removeprefix("www.")
    except Exception:
        return ""
