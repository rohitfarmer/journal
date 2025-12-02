# Rohit’s Journal – Static Site Generator

This repo contains a tiny static site generator (SSG) for my personal journal:

* Daily entries written in **Markdown**, grouped by **month** and stored in **year folders**.
* A Python build script turns them into a static HTML site with:

  * One page per **year** (plus `index.html` for the latest year)
  * **On This Day** page
  * **Tag pages** (`tag/<tag>.html`) and a **tag index** (`tags.html`)
  * **RSS feed** for the latest year
  * **Dark mode** toggle with persistence
  * **Search** powered by Lunr.js (offline client-side search)

Everything is static HTML, CSS, and JS – easy to host anywhere.

---

## 1. Directory layout

Typical repo layout:

```text
.
├── build.py          # Main build script (Python SSG)
├── config.yml        # Configuration file (paths, title, URL, etc.)
├── style.css         # Site CSS (manually maintained)
├── lunr.js           # Lunr search library (downloaded)
├── search.js         # Custom search wiring for this site
├── _site/            # Build output (generated, can be deleted/rebuilt)
├── 2024/             # Year folder
│   ├── 2024-01.md
│   ├── 2024-02.md
│   └── ...
└── 2025/
    ├── 2025-11.md
    ├── 2025-12.md
    └── ...
```

The `_site/` directory is **safe to delete**; it will be recreated when you run the build.

---

## 2. Dependencies

### System requirements

* Python **3.8+**
* `pip` (Python package manager)

### Python packages

Install once per machine:

```bash
pip install markdown pyyaml beautifulsoup4
```

These are used for:

* `markdown` – converting Markdown entries to HTML
* `pyyaml` – reading `config.yml`
* `beautifulsoup4` – post-processing HTML (for image captions and search index)

### JavaScript files (in the repo)

* `lunr.js` – Lunr search engine (downloaded from the Lunr release page)
* `search.js` – Custom script that:

  * loads `_site/search_index.json`
  * initialises Lunr index
  * wires up the search box on year pages

These files are copied into `_site/` during the build.

---

## 3. The config file (`config.yml`)

`config.yml` controls site metadata and paths.

Example:

```yaml
site_title: "Rohit's Journal"
site_tagline: "Daily notes and reflections"
site_url: "https://example.com/journal"  # used for RSS + full URLs, optional

content_root: "."       # where year folders (2024, 2025, ...) live
output_dir: "_site"     # build output

css_path: "style.css"   # source CSS file to copy into _site/style.css

order: "reverse"        # "reverse" = newest first (recommended)
latest_as_index: true   # latest year becomes index.html

enable_search: true
lunr_js_path: "lunr.js"
search_js_path: "search.js"
search_index_filename: "search_index.json"

include_drafts: false   # if true, include entries marked draft: true

# Optional: extra <head> and footer HTML
extra_head:
  - '<meta name="description" content="Rohit''s personal journal">'
  - '<meta name="google-site-verification" content="XYZ">'

extra_footer:
  - '<p>&copy; 2025 Rohit Farmer</p>'
```

Notes:

* `site_url` is **recommended** if you care about correct absolute URLs in RSS and search.
* `extra_head` and `extra_footer` can be a string or a list of strings.
* `include_drafts: false` means `draft: true` entries are ignored.

---

## 4. Journal content format

### 4.1. Files and folders

Each year gets its own folder:

```text
2025/
  2025-11.md
  2025-12.md
```

Each month file (`YYYY-MM.md`) contains:

* An optional **month heading** (ignored by the parser):

  ```markdown
  # December 2025
  ```
* Then multiple **entries**, each starting with a heading containing a date in `YYYY-MM-DD` format.

Example:

```markdown
# December 2025

## 2025-12-02
tags: outdoors, family
draft: false

It was a cold but beautiful day. Went for a walk with the kids…

## 2025-12-01
tags: coding, journal

Worked on the journal SSG and added tags & search…
```

### 4.2. Entry metadata

At the top of each entry (between the date heading and the first blank line), you can add:

* `tags:` – comma-separated tags
* `draft:` – whether this entry is a draft

Example:

```markdown
## 2025-12-02
tags: outdoors, family, sup
draft: true

This will be skipped unless include_drafts: true in config.yml.
```

Rules:

* `tags:` and `draft:` must be **before** the first blank line.
* `draft:` accepts `true/false`, `yes/no`, `1/0`, etc.
* Tags are used to:

  * show tag **pills** under each entry date
  * generate `tag/<tag>.html` pages
  * generate `tags.html` index

### 4.3. Markdown to HTML

* Headings use the level in Markdown: `##` → `<h2>`, `###` → `<h3>`, etc., but still between `h2`–`h6`.
* Images (`![caption](url)`) are converted to:

  ```html
  <figure class="entry-figure">
    <img src="..." alt="caption">
    <figcaption>caption</figcaption>
  </figure>
  ```

  So the alt text becomes a visible caption.

---

## 5. Generated pages

Running the build creates:

* `_site/index.html` – latest year’s entries
* `_site/YYYY.html` – one per year
* `_site/on-this-day.html` – entries that match today’s month-day across years
* `_site/tags.html` – tag index page
* `_site/tag/<slug>.html` – one page per tag
* `_site/rss.xml` – RSS feed for latest year
* `_site/search_index.json` – JSON search index for Lunr
* `_site/style.css` – copy of your CSS
* `_site/lunr.js`, `_site/search.js` – JS files copied over
* `_site/theme.js` – auto-generated JS for dark mode persistence

### 5.1. Year pages / index

* Show entries for that year in chronological or reverse-chronological order (from `order` in config).
* Include:

  * **Search box** (unless `enable_search: false`)
  * **Dark mode toggle**
  * **Sidebar**:

    * Site title + tagline
    * Links: “On this day”, “Tags”
    * List of years (latest first)
  * Each entry has:

    * Date heading
    * Permalink (`¶`) linking to `#YYYY-MM-DD`
    * Tag pills

### 5.2. Tag pages

* URL: `_site/tag/<slug>.html`

  * e.g. tag `outdoors` → `_site/tag/outdoors.html`
* Lists **all entries** across all years with that tag, newest first.
* Sidebar is consistent (On this day, Tags, year list).
* No search box (to keep things simple and avoid path issues).
* Tag pills on these pages are **non-clickable** (just visual).

### 5.3. Tag index (`tags.html`)

* URL: `_site/tags.html`

* Shows all tags, with entry counts:

  ```text
  outdoors (5)
  family (12)
  coding (9)
  ```

* Each tag links to its tag page: `tag/<slug>.html`.

### 5.4. On This Day

* URL: `_site/on-this-day.html`
* Uses the current system date when you run the build.
* Lists all entries across years where the date’s month-day matches today.
* No search box.

### 5.5. RSS feed

* URL: `_site/rss.xml`
* Contains items for the **latest year**.
* Each item has:

  * title (`YYYY-MM-DD – Site Title`)
  * link to `YYYY.html#YYYY-MM-DD`
  * `description` with the rendered HTML body (wrapped in CDATA).

---

## 6. Dark mode

The build script:

* Adds a checkbox `<input id="theme-toggle">` to every page.
* Injects the necessary HTML structure for light/dark CSS.
* Writes `_site/theme.js`, which:

  * Reads `localStorage.theme`
  * Sets the checkbox state on load
  * Saves new state (`"dark"`/`"light"`) whenever you toggle

You only maintain **CSS**, not the JS.

---

## 7. Search (Lunr.js)

* Search is enabled if `enable_search: true` in `config.yml`.
* Build steps:

  * `build.py` generates `_site/search_index.json` with:

    * id, year, date, URL, text (plain text extracted from HTML), tags
  * `lunr.js` + `search.js` are copied into `_site/`
* On year pages / index:

  * Search box appears at the top of content.
  * Typing triggers Lunr search, showing results (implementation details in `search.js`).

Tag pages and `on-this-day.html` **do not** show a search box.

---

## 8. Building the site

From the repo root:

```bash
python3 build.py
```

What happens:

1. Reads `config.yml`.
2. Walks `content_root` and scans year folders.
3. Parses each `YYYY-MM.md`, splitting into entries by `## YYYY-MM-DD` headings.
4. Extracts `tags:` and `draft:` metadata.
5. Groups entries by year, sorts by date (order from config).
6. Builds:

   * year pages
   * `index.html`
   * `rss.xml`
   * `on-this-day.html`
   * `tag/<slug>.html` pages
   * `tags.html`
   * `search_index.json`
7. Copies:

   * `style.css` → `_site/style.css`
   * `lunr.js` → `_site/lunr.js`
   * `search.js` → `_site/search.js`
8. Writes `_site/theme.js`.

To preview locally:

```bash
cd _site
python3 -m http.server 8000
```

Open: [http://localhost:8000](http://localhost:8000)

---

## 9. Moving to a new machine

When cloning this repo on a new computer:

1. Clone the repo:

   ```bash
   git clone <your-repo-url>
   cd <repo>
   ```

2. Install Python dependencies:

   ```bash
   pip install markdown pyyaml beautifulsoup4
   ```

3. Ensure `config.yml` is correct for that environment:

   * `content_root` and `output_dir` are usually fine as-is.
   * Update `site_url` if the hosting location changed.
   * Paths to `style.css`, `lunr.js`, `search.js` are relative to the repo root.

4. Run the build:

   ```bash
   python3 build.py
   ```

5. Deploy the `_site/` folder to your static host (or just view locally).

---

## 10. Common gotchas / things to remember

* **Dates must be in `YYYY-MM-DD`** in the heading, e.g. `## 2025-12-02`.
* Metadata (`tags:`, `draft:`) must be **above the first blank line** of an entry.
* Drafts are skipped unless `include_drafts: true` in `config.yml`.
* Tag slugs are auto-generated (`My Tag` → `my-tag`).
* `_site/` is generated; don’t manually edit files inside – they’ll be overwritten on the next build.
* Always run `python3 build.py` after editing:

  * Markdown content
  * `config.yml`
  * `style.css`
  * `search.js`
  * `build.py` itself
