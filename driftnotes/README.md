# DriftNotes: A lightweight journaling engine for thoughts that drift between tweets and blogs.

DriftNotes is a minimal static site generator for short-form, everyday journaling. Write Markdown entries grouped by year and month, and DriftNotes compiles them into clean, fast, fully static HTML—complete with tags, permalinks, dark mode, on-this-day pages, and offline search. Perfect for writing posts that are more meaningful than a tweet but less formal than a full blog post.

See DriftNotes being used live at: [https://journal.rohitfarmer.com/](https://journal.rohitfarmer.com/).

## Getting Started

## Dependencies

### System requirements

* Python 3.8+
* pip (Python package manager)

### Python packages

```bash
pip install markdown pyyaml beautifulsoup4
```

### Directory Structure

A typical DrifNotes journal project consists of a `journal-root` folder that contains the `contents` to be published, a configuration `YAML` file, and the downloaded or cloned `driftnotes` repository **(this repository)**. Upon execution of the [build command](#building-the-journal-website), the build system will generate an output directory (specified in the configuration file) with the HTML files. 

```bash
journal-root
    content             # Journal content folder
        2025            # Year folder
            2025-12.md  # Per month Markdown files
            2025-11.md
        2024
            2024-10.md
            2024-09.md
    driftnotes          # Cloned or downloaded driftnotes repo with it's contents.
    config.yml         # Configuration file with site title, URL etc.
    _site               # Output directory as mentioned in the configuration file.
```

### Configuration YAML File

Create a `config.yml` YAML file with the contents as mentioned below (modify for your project) and place it in the project root folder. All paths mentioned in the configuration file are relative to it.

```yaml
site_title: "Rohit's Journal"
site_tagline: 'Welcome to my online journal.'
site_url: "journal.rohitfarmer.com"

# Where the year folders live (relative to this config)
content_root: "content"

# Where to write the generated HTML (relative to this config)
output_dir: "_site"

order: "reverse"             # "reverse" (newest first) or "chronological"
latest_as_index: true        # latest year becomes index.html

enable_search: true          # Lunr search on year pages
include_drafts: false        # include entries with draft: true or not

# Optional elements to include in the head section of the html or in the footer of the website.
extra_head: |
    <meta name="author" content="Rohit Farmer">
    <meta name="robots" content="noindex">

extra_footer: |
    <p>© 2025 Rohit Farmer — All rights reserved.</p>
    <p><a href="mailto:rohit@rohitfarmer.com">Contact</a></p>
```

## Journal Content Format

### Files and Folders

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

### Entry Metadata

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

### Markdown to HTML

* Headings use the level in Markdown: `##` → `<h2>`, `###` → `<h3>`, etc., but still between `h2`–`h6`.
* Images (`![caption](url)`) are converted to:

  ```html
  <figure class="entry-figure">
    <img src="..." alt="caption">
    <figcaption>caption</figcaption>
  </figure>
  ```

  So the alt text becomes a visible caption.

## Building the Journal Website

From the project root folder:

```bash
python3 diffnet/build.py config.yml
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

## Common Gotchas/Things to Remember

* **Dates must be in `YYYY-MM-DD`** in the heading, e.g. `## 2025-12-02`.
* Metadata (`tags:`, `draft:`) must be **above the first blank line** of an entry.
* Drafts are skipped unless `include_drafts: true` in `config.yml`.
* Tag slugs are auto-generated (`My Tag` → `my-tag`).
* `_site/` is generated; don’t manually edit files inside – they’ll be overwritten on the next build.
* Always run `python3 driftnotes/build.py` after editing:

  * Markdown content
  * `config.yml`
  * `style.css`
  * `search.js`
  * `build.py` itself


## TL;DR

### Generated Pages

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

#### Year pages / index

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

#### Tag pages

* URL: `_site/tag/<slug>.html`

  * e.g. tag `outdoors` → `_site/tag/outdoors.html`
* Lists **all entries** across all years with that tag, newest first.
* Sidebar is consistent (On this day, Tags, year list).
* No search box (to keep things simple and avoid path issues).
* Tag pills on these pages are **non-clickable** (just visual).

#### Tag index (`tags.html`)

* URL: `_site/tags.html`

* Shows all tags, with entry counts:

  ```text
  outdoors (5)
  family (12)
  coding (9)
  ```

* Each tag links to its tag page: `tag/<slug>.html`.

#### On This Day

* URL: `_site/on-this-day.html`
* Uses the current system date when you run the build.
* Lists all entries across years where the date’s month-day matches today.
* No search box.

#### RSS feed

* URL: `_site/rss.xml`
* Contains items for the **latest year**.
* Each item has:

  * title (`YYYY-MM-DD – Site Title`)
  * link to `YYYY.html#YYYY-MM-DD`
  * `description` with the rendered HTML body (wrapped in CDATA).
