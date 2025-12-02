#!/usr/bin/env python3
import re
import sys
import shutil
import html
import time
import json
from pathlib import Path
from datetime import datetime, date
from email.utils import formatdate

import markdown       # pip install markdown
import yaml           # pip install pyyaml
from bs4 import BeautifulSoup  # pip install beautifulsoup4

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.yml"

# Matches lines like "## 2025-01-02" or "### 2025-01-02"
ENTRY_HEADING_RE = re.compile(r"^(#{2,6})\s+(\d{4}-\d{2}-\d{2})\s*$")


def load_config():
    """Load YAML config and apply defaults."""
    if not CONFIG_FILE.exists():
        print(f"Config file not found: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    data = yaml.safe_load(CONFIG_FILE.read_text(encoding="utf-8")) or {}

    # extra_head can be a string or a list
    extra_head = data.get("extra_head", [])
    if isinstance(extra_head, str):
        extra_head_list = [extra_head]
    elif isinstance(extra_head, list):
        extra_head_list = [str(x) for x in extra_head]
    else:
        extra_head_list = []

    # extra_footer can be a string or a list
    extra_footer = data.get("extra_footer", [])
    if isinstance(extra_footer, str):
        extra_footer_list = [extra_footer]
    elif isinstance(extra_footer, list):
        extra_footer_list = [str(x) for x in extra_footer]
    else:
        extra_footer_list = []

    cfg = {
        "site_title": data.get("site_title", "Journal"),
        "site_tagline": data.get("site_tagline", ""),
        "site_url": data.get("site_url", ""),          # optional, for RSS + absolute links
        "content_root": data.get("content_root", "."),
        "output_dir": data.get("output_dir", "_site"),
        "css_path": data.get("css_path", "style.css"),
        # default to newest first
        "order": data.get("order", "reverse"),         # "reverse" or "chronological"
        "latest_as_index": bool(data.get("latest_as_index", True)),
        "extra_head": extra_head_list,
        "extra_footer": extra_footer_list,
        # Search config
        "enable_search": bool(data.get("enable_search", True)),
        "lunr_js_path": data.get("lunr_js_path", "lunr.js"),
        "search_js_path": data.get("search_js_path", "search.js"),
        "search_index_filename": data.get("search_index_filename", "search_index.json"),
        # Drafts
        "include_drafts": bool(data.get("include_drafts", False)),
    }
    return cfg


def parse_month_file(path: Path):
    """
    Parse a monthly markdown file into a list of entries.

    Each entry:
      {
        "date": "YYYY-MM-DD",
        "heading_level": 2,
        "content_md": "markdown text"
      }
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    entries = []
    current_date = None
    current_level = None
    current_lines = []

    for line in lines:
        m = ENTRY_HEADING_RE.match(line)
        if m:
            # Flush previous entry
            if current_date is not None:
                entries.append(
                    {
                        "date": current_date,
                        "heading_level": current_level or 2,
                        "content_md": "\n".join(current_lines).strip(),
                    }
                )
                current_lines = []

            hashes = m.group(1)
            current_level = len(hashes)
            current_date = m.group(2)
        else:
            # Skip top-level month heading like "# December 2025"
            if line.startswith("# ") and current_date is None:
                continue
            current_lines.append(line)

    # Flush last entry
    if current_date is not None:
        entries.append(
            {
                "date": current_date,
                "heading_level": current_level or 2,
                "content_md": "\n".join(current_lines).strip(),
            }
        )

    return entries


def extract_meta(entry):
    """
    Extract metadata from the top of entry["content_md"]:

      tags: outdoors, family
      draft: true

    - tags: comma-separated list
    - draft: true/false/yes/no/1/0

    Strips these meta lines from content_md and attaches:
      entry["tags"] -> list[str]
      entry["draft"] -> bool
    """
    lines = entry["content_md"].splitlines()
    tags = []
    draft = False
    body_start = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            # blank line: body starts after this
            body_start = i + 1
            break

        lower = stripped.lower()
        if lower.startswith("tags:"):
            tag_str = stripped[5:].strip()
            tags = [t.strip() for t in tag_str.split(",") if t.strip()]
        elif lower.startswith("draft:"):
            val = stripped[6:].strip().lower()
            draft = val in ("true", "yes", "1", "y", "on")
        else:
            # first non-meta line: body starts here
            body_start = i
            break

    body = "\n".join(lines[body_start:]).strip()
    entry["content_md"] = body
    entry["tags"] = tags
    entry["draft"] = draft


def collect_entries_by_year(content_root: Path, order: str = "reverse", include_drafts: bool = False):
    """
    Walk through YEAR directories and collect entries per year.
    Returns: { "2024": [entries...], "2025": [entries...] }

    Entries are sorted by date within each year according to `order`.
    Draft entries are skipped unless include_drafts=True.
    """
    entries_by_year = {}

    for year_dir in sorted(content_root.iterdir()):
        if not year_dir.is_dir():
            continue
        if not year_dir.name.isdigit():
            continue  # skip _site, .git, etc.

        year = year_dir.name
        year_entries = []

        for md_file in sorted(year_dir.glob("*.md")):
            for e in parse_month_file(md_file):
                extract_meta(e)  # tags + draft + content cleanup
                if e.get("draft") and not include_drafts:
                    continue

                e["_dt"] = datetime.strptime(e["date"], "%Y-%m-%d")
                e["source_file"] = md_file
                e["year"] = year
                year_entries.append(e)

        if not year_entries:
            continue

        reverse = (order == "reverse")
        year_entries.sort(key=lambda x: x["_dt"], reverse=reverse)

        entries_by_year[year] = year_entries

    return entries_by_year


def slugify_tag(tag: str) -> str:
    """
    Convert a tag like 'Outdoor Trips' into a URL-friendly slug: 'outdoor-trips'.
    """
    s = tag.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "tag"


def build_tag_index(entries_by_year: dict):
    """
    Build a tag index:

      {
        "outdoors": { "name": "outdoors", "entries": [entry, ...] },
        "family":   { "name": "family",   "entries": [entry, ...] },
        ...
      }

    Keys are slugs; "name" is the first-seen display name.
    """
    tag_map = {}

    for year, entries in entries_by_year.items():
        for e in entries:
            for tag in e.get("tags") or []:
                slug = slugify_tag(tag)
                if slug not in tag_map:
                    tag_map[slug] = {"name": tag, "entries": []}
                tag_map[slug]["entries"].append(e)

    # Sort entries per tag by datetime (newest first)
    for slug, data in tag_map.items():
        data["entries"].sort(key=lambda x: x["_dt"], reverse=True)

    return tag_map


def wrap_images_with_figures(html_fragment: str) -> str:
    """
    Wrap <img> tags in <figure> with <figcaption> using the alt text.
    This exposes the Markdown alt text as a visible caption.
    """
    soup = BeautifulSoup(html_fragment, "html.parser")

    for img in soup.find_all("img"):
        alt = img.get("alt", "").strip()

        # Skip if already inside a figure
        if img.find_parent("figure"):
            continue

        figure = soup.new_tag("figure")
        figure["class"] = "entry-figure"

        img.replace_with(figure)
        figure.append(img)

        if alt:
            caption = soup.new_tag("figcaption")
            caption.string = alt
            figure.append(caption)

    return str(soup)


def render_entry(entry, *, link_tags: bool = True):
    """Render one entry as an <article> block with a permalink and tags."""
    date_str = entry["date"]
    level = entry.get("heading_level", 2)
    level = max(2, min(6, level))  # clamp between h2–h6
    heading_tag = f"h{level}"

    # Convert Markdown to HTML
    raw_html = markdown.markdown(entry["content_md"])
    # Wrap images in <figure> + <figcaption>
    content_html = wrap_images_with_figures(raw_html)

    permalink = f"#{date_str}"

    # Tags (visible as pills)
    tag_html = ""
    tags = entry.get("tags") or []
    if tags:
        pills = []
        for tag in tags:
            slug = slugify_tag(tag)
            label = html.escape(tag)
            if link_tags:
                href = f"tag/{slug}.html"
                pill = f'<li><a href="{href}" class="entry-tag">{label}</a></li>'
            else:
                pill = f'<li><span class="entry-tag">{label}</span></li>'
            pills.append(pill)
        tag_html = f'<ul class="entry-tags">{"".join(pills)}</ul>'

    return f"""<article id="{date_str}" class="entry">
  <header class="entry-header">
    <{heading_tag} class="entry-date">
      <time datetime="{date_str}">{date_str}</time>
    </{heading_tag}>
    <a class="entry-permalink" href="{permalink}" title="Permalink to this entry">¶</a>
    {tag_html}
  </header>
  <div class="entry-body">
    {content_html}
  </div>
</article>
"""


def sidebar_extra_links(active_on_this_day: bool = False):
    """Return HTML for extra sidebar links (e.g., On this day)."""
    classes = "sidebar-link"
    if active_on_this_day:
        classes += " active"
    return f"""
    <div class="sidebar-extra-links">
      <a href="on-this-day.html" class="{classes}">On this day</a>
    </div>"""


def build_common_head_and_footer(cfg):
    """Return extra_head_html, extra_footer_html strings."""
    extra_head_items = cfg.get("extra_head") or []
    extra_head_html = ""
    if extra_head_items:
        extra_head_html = "\n  " + "\n  ".join(extra_head_items)

    extra_footer_items = cfg.get("extra_footer") or []
    extra_footer_html = ""
    if extra_footer_items:
        extra_footer_html = "\n    " + "\n    ".join(extra_footer_items)

    return extra_head_html, extra_footer_html


def search_ui_html(cfg):
    if not cfg.get("enable_search", True):
        return ""
    return """
      <section class="search-section">
        <form class="search-form" role="search" onsubmit="return false;">
          <label for="search-input" class="search-label">Search entries</label>
          <input id="search-input" class="search-input" type="search" placeholder="Search this journal">
        </form>
        <div id="search-results" class="search-results" aria-live="polite"></div>
      </section>
"""


def search_scripts_html(cfg):
    if not cfg.get("enable_search", True):
        return ""
    lunr_basename = Path(cfg["lunr_js_path"]).name
    search_basename = Path(cfg["search_js_path"]).name
    return f'\n<script src="{lunr_basename}"></script>\n<script src="{search_basename}"></script>'


def render_year_page(year, years, entries, cfg, *, is_index=False):
    """
    Render a full HTML page for a given year.
    """
    articles_html = "\n\n".join(render_entry(e, link_tags=True) for e in entries)

    site_title = cfg["site_title"]
    site_tagline = cfg["site_tagline"]

    if is_index:
        page_title = f"{site_title}"
        main_heading = f"""<h2 class="year-title">Latest entries &ndash; {year}</h2>"""
    else:
        page_title = f"{site_title} – {year}"
        main_heading = f"""<h2 class="year-title">{year}</h2>"""

    # Sidebar year navigation (reverse chronological)
    year_links = []
    for y in sorted(years, reverse=True):
        href = f"{y}.html"
        css_class = "year-link"
        if (is_index and y == year) or (not is_index and y == year):
            css_class += " active"
        year_links.append(f'<li><a href="{href}" class="{css_class}">{y}</a></li>')

    years_nav_html = "\n          ".join(year_links)

    extra_head_html, extra_footer_html = build_common_head_and_footer(cfg)
    order_text = (
        "reverse chronological" if cfg.get("order", "reverse") == "reverse" else "chronological"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{page_title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="style.css">
  <link rel="alternate" type="application/rss+xml" title="{site_title} – RSS" href="rss.xml">{extra_head_html}
</head>
<body>
<input type="checkbox" id="theme-toggle" class="theme-toggle-checkbox" aria-label="Toggle dark mode">
<div class="layout">
  <aside class="sidebar">
    <header class="site-header">
      <h1 class="site-title"><a href="index.html">{site_title}</a></h1>
      <p class="site-tagline">{site_tagline}</p>
    </header>

    <div class="theme-toggle-control">
      <label for="theme-toggle" class="theme-toggle-label">
        <span class="theme-toggle-icon theme-toggle-light" aria-hidden="true">☀️</span>
        <span class="theme-toggle-icon theme-toggle-dark" aria-hidden="true">🌙</span>
        <span class="theme-toggle-text">Theme</span>
      </label>
    </div>

{sidebar_extra_links(active_on_this_day=False)}

    <nav class="year-nav">
      <h2 class="year-nav-title">Years</h2>
      <ul class="year-nav-list">
          {years_nav_html}
      </ul>
    </nav>
  </aside>

  <main class="content">
    <div class="content-inner">
      <header class="content-header">
        {main_heading}
        <p class="content-subtitle">Entries are shown in {order_text} order.</p>
      </header>

{search_ui_html(cfg)}
      {articles_html}
    </div>
  </main>
</div>

<footer class="site-footer">
  {extra_footer_html}
</footer>{search_scripts_html(cfg)}

</body>
</html>
"""


def render_on_this_day_page(today_label: str, years, entries, cfg):
    """
    Render a page with entries that happened on this month-day across all years.
    """
    site_title = cfg["site_title"]
    site_tagline = cfg["site_tagline"]

    page_title = f"{site_title} – On this day"

    # Sidebar year navigation (reverse chronological)
    year_links = []
    for y in sorted(years, reverse=True):
        href = f"{y}.html"
        css_class = "year-link"
        year_links.append(f'<li><a href="{href}" class="{css_class}">{y}</a></li>')

    years_nav_html = "\n          ".join(year_links)

    extra_head_html, extra_footer_html = build_common_head_and_footer(cfg)

    # Render entries matching this date across years
    if entries:
        articles_html = "\n\n".join(render_entry(e, link_tags=True) for e in entries)
        subtitle = f"Entries from different years that happened on {today_label}."
    else:
        articles_html = "<p>No earlier entries for this date yet.</p>"
        subtitle = f"No earlier entries found on {today_label}."

    main_heading = f"""<h2 class="year-title">On this day – {today_label}</h2>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{page_title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="style.css">
  <link rel="alternate" type="application/rss+xml" title="{site_title} – RSS" href="rss.xml">{extra_head_html}
</head>
<body>
<input type="checkbox" id="theme-toggle" class="theme-toggle-checkbox" aria-label="Toggle dark mode">
<div class="layout">
  <aside class="sidebar">
    <header class="site-header">
      <h1 class="site-title"><a href="index.html">{site_title}</a></h1>
      <p class="site-tagline">{site_tagline}</p>
    </header>

    <div class="theme-toggle-control">
      <label for="theme-toggle" class="theme-toggle-label">
        <span class="theme-toggle-icon theme-toggle-light" aria-hidden="true">☀️</span>
        <span class="theme-toggle-icon theme-toggle-dark" aria-hidden="true">🌙</span>
        <span class="theme-toggle-text">Theme</span>
      </label>
    </div>

{sidebar_extra_links(active_on_this_day=True)}

    <nav class="year-nav">
      <h2 class="year-nav-title">Years</h2>
      <ul class="year-nav-list">
          {years_nav_html}
      </ul>
    </nav>
  </aside>

  <main class="content">
    <div class="content-inner">
      <header class="content-header">
        {main_heading}
        <p class="content-subtitle">{subtitle}</p>
      </header>

{search_ui_html(cfg)}
      {articles_html}
    </div>
  </main>
</div>

<footer class="site-footer">
  {extra_footer_html}
</footer>{search_scripts_html(cfg)}

</body>
</html>
"""


def render_tag_page(tag_name: str, tag_slug: str, years, entries, cfg):
    """
    Render a page listing all entries for a given tag.
    """
    site_title = cfg["site_title"]
    site_tagline = cfg["site_tagline"]

    page_title = f"{site_title} – Tag: {tag_name}"
    main_heading = f"""<h2 class="year-title">Tag: {html.escape(tag_name)}</h2>"""

    # Sidebar year navigation (reverse chronological)
    year_links = []
    for y in sorted(years, reverse=True):
        href = f"../{y}.html"
        css_class = "year-link"
        year_links.append(f'<li><a href="{href}" class="{css_class}">{y}</a></li>')

    years_nav_html = "\n          ".join(year_links)

    extra_head_html, extra_footer_html = build_common_head_and_footer(cfg)

    if entries:
        # From tag pages, render tags as non-clickable to avoid nested relative paths
        articles_html = "\n\n".join(render_entry(e, link_tags=False) for e in entries)
        subtitle = "Entries across all years with this tag."
    else:
        articles_html = "<p>No entries yet for this tag.</p>"
        subtitle = "No entries found for this tag."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{page_title}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="../style.css">
  <link rel="alternate" type="application/rss+xml" title="{site_title} – RSS" href="../rss.xml">{extra_head_html}
</head>
<body>
<input type="checkbox" id="theme-toggle" class="theme-toggle-checkbox" aria-label="Toggle dark mode">
<div class="layout">
  <aside class="sidebar">
    <header class="site-header">
      <h1 class="site-title"><a href="../index.html">{site_title}</a></h1>
      <p class="site-tagline">{site_tagline}</p>
    </header>

    <div class="theme-toggle-control">
      <label for="theme-toggle" class="theme-toggle-label">
        <span class="theme-toggle-icon theme-toggle-light" aria-hidden="true">☀️</span>
        <span class="theme-toggle-icon theme-toggle-dark" aria-hidden="true">🌙</span>
        <span class="theme-toggle-text">Theme</span>
      </label>
    </div>

{sidebar_extra_links(active_on_this_day=False)}

    <nav class="year-nav">
      <h2 class="year-nav-title">Years</h2>
      <ul class="year-nav-list">
          {years_nav_html}
      </ul>
    </nav>
  </aside>

  <main class="content">
    <div class="content-inner">
      <header class="content-header">
        {main_heading}
        <p class="content-subtitle">{subtitle}</p>
      </header>

{search_ui_html(cfg)}
      {articles_html}
    </div>
  </main>
</div>

<footer class="site-footer">
  {extra_footer_html}
</footer>{search_scripts_html(cfg)}

</body>
</html>
"""


def copy_css(css_src: Path, output_dir: Path):
    """Copy the CSS file into the output directory as style.css."""
    if not css_src.exists():
        print(f"WARNING: CSS file not found at {css_src}", file=sys.stderr)
        return
    dest = output_dir / "style.css"
    shutil.copy2(css_src, dest)
    print(f"Copied CSS to {dest}")


def copy_search_js(cfg, output_dir: Path):
    """Copy Lunr.js and search.js into the output directory (if enabled)."""
    if not cfg.get("enable_search", True):
        return

    for key in ("lunr_js_path", "search_js_path"):
        src = (BASE_DIR / cfg[key]).resolve()
        if not src.exists():
            print(f"WARNING: Search JS file not found at {src}", file=sys.stderr)
            continue
        dest = output_dir / src.name
        shutil.copy2(src, dest)
        print(f"Copied {src.name} to {dest}")


def generate_rss(latest_year: str, entries, cfg: dict, output_dir: Path):
    """
    Generate an RSS 2.0 feed for the latest year and write _site/rss.xml.
    description contains rendered HTML (not Markdown), wrapped in CDATA.
    """
    site_title = cfg["site_title"]
    site_tagline = cfg.get("site_tagline", "")
    site_url = (cfg.get("site_url") or "").rstrip("/")

    if site_url:
        channel_link = f"{site_url}/{latest_year}.html"
    else:
        channel_link = f"{latest_year}.html"

    now = formatdate(time.time())

    items_xml = []

    for e in entries:
        date_str = e["date"]
        dt = e["_dt"]

        path = f"{latest_year}.html#{date_str}"
        if site_url:
            link = f"{site_url}/{path}"
        else:
            link = path

        title = f"{date_str} – {site_title}"

        entry_html = wrap_images_with_figures(
            markdown.markdown(e["content_md"])
        )

        description_cdata = f"<![CDATA[{entry_html}]]>"

        items_xml.append(f"""  <item>
    <title>{title}</title>
    <link>{link}</link>
    <guid>{link}</guid>
    <pubDate>{formatdate(dt.timestamp())}</pubDate>
    <description>{description_cdata}</description>
  </item>""")

    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{site_title} – {latest_year}</title>
  <link>{channel_link}</link>
  <description>{site_tagline}</description>
  <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items_xml)}
</channel>
</rss>
"""

    rss_path = output_dir / "rss.xml"
    rss_path.write_text(rss_xml, encoding="utf-8")
    print(f"Wrote {rss_path}")


def build_search_index(entries_by_year: dict, cfg: dict, output_dir: Path):
    """
    Build a Lunr-friendly JSON search index over all years.
    """
    if not cfg.get("enable_search", True):
        return

    site_url = (cfg.get("site_url") or "").rstrip("/")

    docs = []

    for year, entries in entries_by_year.items():
        for e in entries:
            date_str = e["date"]
            url = f"{year}.html#{date_str}"
            if site_url:
                full_url = f"{site_url}/{url}"
            else:
                full_url = url

            html_body = markdown.markdown(e["content_md"])
            text = BeautifulSoup(html_body, "html.parser").get_text(" ", strip=True)

            tags = e.get("tags") or []
            tags_str = " ".join(tags)

            docs.append(
                {
                    "id": f"{year}-{date_str}",
                    "year": year,
                    "date": date_str,
                    "url": url,
                    "full_url": full_url,
                    "title": f"{date_str}",
                    "text": (tags_str + " " + text).strip(),
                }
            )

    index_path = output_dir / cfg["search_index_filename"]
    index_path.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote search index to {index_path}")


def build_on_this_day(entries_by_year: dict, cfg: dict, output_dir: Path):
    """
    Build on-this-day.html for today's month-day, across all years.
    """
    if not entries_by_year:
        return

    today = date.today()
    mm_dd = today.strftime("%m-%d")
    label = today.strftime("%B %d")  # e.g. "December 02"

    matches = []
    for year, entries in entries_by_year.items():
        for e in entries:
            if e["_dt"].strftime("%m-%d") == mm_dd:
                matches.append(e)

    matches.sort(key=lambda x: x["_dt"], reverse=True)

    years = sorted(entries_by_year.keys())

    html_page = render_on_this_day_page(label, years, matches, cfg)
    out_path = output_dir / "on-this-day.html"
    out_path.write_text(html_page, encoding="utf-8")
    print(f"Wrote {out_path}")


def build_tag_pages(tag_index: dict, entries_by_year: dict, cfg: dict, output_dir: Path):
    """
    Build tag/<slug>.html pages for each tag.
    """
    if not tag_index:
        return

    tag_dir = output_dir / "tag"
    tag_dir.mkdir(parents=True, exist_ok=True)

    years = sorted(entries_by_year.keys())

    for slug, data in tag_index.items():
        tag_name = data["name"]
        entries = data["entries"]
        html_page = render_tag_page(tag_name, slug, years, entries, cfg)
        out_path = tag_dir / f"{slug}.html"
        out_path.write_text(html_page, encoding="utf-8")
        print(f"Wrote {out_path}")


def main():
    cfg = load_config()

    content_root = (BASE_DIR / cfg["content_root"]).resolve()
    output_dir = (BASE_DIR / cfg["output_dir"]).resolve()
    css_src = (BASE_DIR / cfg["css_path"]).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    entries_by_year = collect_entries_by_year(
        content_root=content_root,
        order=cfg["order"],
        include_drafts=cfg["include_drafts"],
    )

    if not entries_by_year:
        print("No entries found.", file=sys.stderr)
        sys.exit(1)

    years = sorted(entries_by_year.keys())
    latest_year = years[-1]

    # Tag index
    tag_index = build_tag_index(entries_by_year)

    # Copy CSS
    copy_css(css_src, output_dir)

    # Copy search JS files (if enabled)
    copy_search_js(cfg, output_dir)

    # Per-year pages
    for year in years:
        html_page = render_year_page(
            year=year,
            years=years,
            entries=entries_by_year[year],
            cfg=cfg,
            is_index=False,
        )
        out_path = output_dir / f"{year}.html"
        out_path.write_text(html_page, encoding="utf-8")
        print(f"Wrote {out_path}")

    # index.html -> latest year
    if cfg["latest_as_index"]:
        index_html = render_year_page(
            year=latest_year,
            years=years,
            entries=entries_by_year[latest_year],
            cfg=cfg,
            is_index=True,
        )
        index_path = output_dir / "index.html"
        index_path.write_text(index_html, encoding="utf-8")
        print(f"Wrote {index_path}")

    # RSS for latest year
    generate_rss(latest_year, entries_by_year[latest_year], cfg, output_dir)

    # On this day
    build_on_this_day(entries_by_year, cfg, output_dir)

    # Tag pages
    build_tag_pages(tag_index, entries_by_year, cfg, output_dir)

    # Lunr search index
    build_search_index(entries_by_year, cfg, output_dir)


if __name__ == "__main__":
    main()
