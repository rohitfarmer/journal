#!/usr/bin/env python3
import re
import sys
import shutil
import html
import time
from pathlib import Path
from datetime import datetime
from email.utils import formatdate

import markdown       # pip install markdown
import yaml           # pip install pyyaml
from bs4 import BeautifulSoup  # pip install beautifulsoup4

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.yaml"

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
        "site_url": data.get("site_url", ""),          # optional, for RSS
        "content_root": data.get("content_root", "."),
        "output_dir": data.get("output_dir", "_site"),
        "css_path": data.get("css_path", "style.css"),
        # default to newest first
        "order": data.get("order", "reverse"),         # "reverse" or "chronological"
        "latest_as_index": bool(data.get("latest_as_index", True)),
        "extra_head": extra_head_list,
        "extra_footer": extra_footer_list,
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


def collect_entries_by_year(content_root: Path, order: str = "reverse"):
    """
    Walk through YEAR directories and collect entries per year.
    Returns: { "2024": [entries...], "2025": [entries...] }

    Entries are sorted by date within each year according to `order`.
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
                e["_dt"] = datetime.strptime(e["date"], "%Y-%m-%d")
                e["source_file"] = md_file
                year_entries.append(e)

        if not year_entries:
            continue

        reverse = (order == "reverse")
        year_entries.sort(key=lambda x: x["_dt"], reverse=reverse)

        entries_by_year[year] = year_entries

    return entries_by_year


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


def render_entry(entry):
    """Render one entry as an <article> block with a permalink."""
    date_str = entry["date"]
    level = entry.get("heading_level", 2)
    level = max(2, min(6, level))  # clamp between h2–h6
    heading_tag = f"h{level}"

    # Convert Markdown to HTML
    raw_html = markdown.markdown(entry["content_md"])
    # Wrap images in <figure> + <figcaption>
    content_html = wrap_images_with_figures(raw_html)

    permalink = f"#{date_str}"

    return f"""<article id="{date_str}" class="entry">
  <header class="entry-header">
    <{heading_tag} class="entry-date">
      <time datetime="{date_str}">{date_str}</time>
    </{heading_tag}>
    <a class="entry-permalink" href="{permalink}" title="Permalink to this entry">¶</a>
  </header>
  <div class="entry-body">
    {content_html}
  </div>
</article>
"""


def render_year_page(year, years, entries, cfg, *, is_index=False):
    """
    Render a full HTML page for a given year.

    - year: string "2025"
    - years: list of all years (e.g. ["2023", "2024", "2025"])
    - entries: list of entries for this year
    - cfg: config dict
    - is_index: if True, this will be index.html (latest year)
    """
    articles_html = "\n\n".join(render_entry(e) for e in entries)

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

    # Extra <head> HTML from config
    extra_head_items = cfg.get("extra_head") or []
    extra_head_html = ""
    if extra_head_items:
        extra_head_html = "\n  " + "\n  ".join(extra_head_items)

    # Extra footer HTML from config
    extra_footer_items = cfg.get("extra_footer") or []
    extra_footer_html = ""
    if extra_footer_items:
        extra_footer_html = "\n    " + "\n    ".join(extra_footer_items)

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
<div class="layout">
  <aside class="sidebar">
    <header class="site-header">
      <h1 class="site-title"><a href="index.html">{site_title}</a></h1>
      <p class="site-tagline">{site_tagline}</p>
    </header>
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

      {articles_html}
    </div>
  </main>
</div>

<footer class="site-footer">
  {extra_footer_html}
</footer>

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


def generate_rss(latest_year: str, entries, cfg: dict, output_dir: Path):
    """
    Generate an RSS 2.0 feed for the latest year and write _site/rss.xml.

    IMPORTANT: description now contains rendered HTML (not Markdown),
    wrapped in CDATA so RSS readers can display it properly.
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

        # URL of this entry
        path = f"{latest_year}.html#{date_str}"
        if site_url:
            link = f"{site_url}/{path}"
        else:
            link = path

        title = f"{date_str} – {site_title}"

        # Render full entry HTML for RSS (like the page body, but without <article>)
        entry_html = wrap_images_with_figures(
            markdown.markdown(e["content_md"])
        )

        # Use CDATA so we can include HTML in <description>
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


def main():
    cfg = load_config()

    content_root = (BASE_DIR / cfg["content_root"]).resolve()
    output_dir = (BASE_DIR / cfg["output_dir"]).resolve()
    css_src = (BASE_DIR / cfg["css_path"]).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    entries_by_year = collect_entries_by_year(
        content_root=content_root,
        order=cfg["order"],
    )

    if not entries_by_year:
        print("No entries found.", file=sys.stderr)
        sys.exit(1)

    years = sorted(entries_by_year.keys())
    latest_year = years[-1]

    # Copy CSS
    copy_css(css_src, output_dir)

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


if __name__ == "__main__":
    main()
