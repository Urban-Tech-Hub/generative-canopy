"""Render docs/index.html (GitHub Pages) from docs/manifest.json and docs/NOTES.md.

Run:  uv run python scripts/build_site.py
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MANIFEST = json.loads((DOCS / "manifest.json").read_text())
NOTES = (DOCS / "NOTES.md").read_text()

ORDER = [
    "dsm_2021_50cm_m",
    "dtm_2021_50cm_m",
    "dsm_2017_50cm_m",
    "dtm_2017_50cm_m",
    "ortho_2024_20cm_rgbnir",
    "naip_2022_leafon_60cm_rgbnir",
    "tree_canopy_2021",
    "landcover_2021_6in",
    "canopy_change_2017_2021_6in",
    "vectors",
]


def md_to_html(md: str) -> str:
    """Tiny Markdown subset: #/##/### headings, paragraphs, -/1. lists, `code`, **bold**, links, tables."""
    out: list[str] = []
    lines = md.splitlines()
    i = 0

    def inline(s: str) -> str:
        s = html.escape(s, quote=False)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    while i < len(lines):
        ln = lines[i]
        if ln.startswith("#"):
            level = len(ln) - len(ln.lstrip("#"))
            text = ln[level:].strip()
            slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            out.append(f'<h{level} id="{slug}">{inline(text)}</h{level}>')
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[2:]]
            out.append(
                "<table><thead><tr>"
                + "".join(f"<th>{inline(c)}</th>" for c in head)
                + "</tr></thead><tbody>"
            )
            for r in body:
                out.append(
                    "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                )
            out.append("</tbody></table>")
        elif re.match(r"^\s*([-*]|\d+\.)\s", ln):
            tag = "ol" if re.match(r"^\s*\d+\.", ln) else "ul"
            out.append(f"<{tag}>")
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s", lines[i]):
                item = re.sub(r"^\s*([-*]|\d+\.)\s", "", lines[i])
                i += 1
                while (
                    i < len(lines)
                    and lines[i].startswith("  ")
                    and not re.match(r"^\s*([-*]|\d+\.)\s", lines[i])
                ):
                    item += " " + lines[i].strip()
                    i += 1
                out.append(f"<li>{inline(item)}</li>")
            out.append(f"</{tag}>")
        elif ln.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(buf)) + "</code></pre>")
        elif ln.strip() == "":
            i += 1
        else:
            para = [ln]
            i += 1
            while (
                i < len(lines)
                and lines[i].strip()
                and not re.match(r"^(#|\||```|\s*([-*]|\d+\.)\s)", lines[i])
            ):
                para.append(lines[i])
                i += 1
            out.append(f"<p>{inline(' '.join(para))}</p>")
    return "\n".join(out)


def fmt_bytes(n: int) -> str:
    return f"{n / 1e9:.2f} GB" if n >= 1e9 else f"{n / 1e6:.0f} MB"


def file_row(f: dict) -> str:
    if f["type"] == "raster":
        spec = f"{f['bands']} band {f['dtype']}, {f['pixel_size_m'][0]:.2f} m px, {f['size_px'][0]}×{f['size_px'][1]}"
    elif f["type"] == "vector":
        spec = "; ".join(f"{k} ({v['features']:,})" for k, v in f["layers"].items())
    else:
        spec = "text"
    link = (
        f'<a href="{f["url"]}">{html.escape(f["file"])}</a>'
        if f.get("url")
        else html.escape(f["file"])
    )
    return (
        f"<tr><td>{html.escape(f['requested_layer'])}</td><td>{link}<div class=spec>{html.escape(spec)}</div></td>"
        f"<td>{fmt_bytes(f['bytes'])}</td><td class=mono title='sha256'>{f['sha256'][:12]}…</td></tr>"
    )


def district_section(cd: str, meta: dict) -> str:
    files = sorted(
        [f for f in MANIFEST["files"] if f["district"] == cd],
        key=lambda f: next(
            (n for n, k in enumerate(ORDER) if f["file"].startswith(k)), 99
        ),
    )
    total = sum(f["bytes"] for f in files)
    rows = "\n".join(file_row(f) for f in files)
    return f"""
<section class="district" id="cd-{cd}">
  <h3>{meta["code"]} · {html.escape(meta["name"])} <span class="total">{len(files)} files · {fmt_bytes(total)}</span></h3>
  <table class="files"><thead><tr><th>Requested layer</th><th>File</th><th>Size</th><th>Checksum</th></tr></thead>
  <tbody>{rows}</tbody></table>
</section>"""


def layer_table() -> str:
    seen: dict[str, dict] = {}
    for f in MANIFEST["files"]:
        key = next((k for k in ORDER if f["file"].startswith(k)), None)
        if key and key not in seen:
            seen[key] = f
    rows = "".join(
        f"<tr><td>{html.escape(f['requested_layer'])}</td><td>{html.escape(f['title'])}</td>"
        f"<td>{html.escape(f['source'])}</td><td>{html.escape(f['vintage'])}</td><td>{html.escape(f['license'])}</td></tr>"
        for k in ORDER
        if (f := seen.get(k))
    )
    return f"<table><thead><tr><th>Requested</th><th>Delivered</th><th>Source</th><th>Vintage</th><th>License</th></tr></thead><tbody>{rows}</tbody></table>"


def fetch_script() -> str:
    urls = [f["url"] for f in MANIFEST["files"] if f.get("url")]
    if not urls:
        return ""
    base = urls[0].rsplit("/", 1)[0]
    total = fmt_bytes(sum(f["bytes"] for f in MANIFEST["files"]))
    body = "\n".join(urls)
    return f"""#!/usr/bin/env bash
# Download the whole Generative Canopy package (~{total}) into ./generative-canopy-data
# and verify SHA-256 checksums against manifest.json. Resumable: rerun to continue.
set -euo pipefail
mkdir -p generative-canopy-data && cd generative-canopy-data
curl -sSL -o manifest.json "{base}/manifest.json"
while read -r u; do
  [ -n "$u" ] && curl -L -O -C - --retry 5 --retry-all-errors "$u"
done <<'URLS'
{body}
URLS
python3 - <<'PY'
import hashlib, json
bad = 0
for f in json.load(open("manifest.json"))["files"]:
    h = hashlib.sha256(open(f["file"], "rb").read()).hexdigest()
    ok = h == f["sha256"]; bad += not ok
    print(("OK  " if ok else "FAIL"), f["file"])
raise SystemExit(bad)
PY
"""


def main() -> None:
    total = sum(f["bytes"] for f in MANIFEST["files"])
    districts = "\n".join(
        district_section(cd, m) for cd, m in MANIFEST["districts"].items()
    )
    script = fetch_script()
    (DOCS / "fetch_all.sh").write_text(script + "\n")
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Generative Canopy data package</title>
<meta name="description" content="Shade-analysis input layers for three NYC community districts: DSM, DTM, orthophoto, tree canopy, land use, building footprints and tree points.">
<style>
:root {{
  --bg:#fbfaf7; --fg:#1d1d1b; --muted:#5f5e58; --line:#e2dfd6; --accent:#1f6f4a; --accent-soft:#e6f2ea; --code:#f1efe8; --card:#ffffff;
}}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --bg:#151614; --fg:#ecebe6; --muted:#a4a39b; --line:#2d2f2a; --accent:#6fcf97; --accent-soft:#1d2e24; --code:#1f211d; --card:#1b1c19;
}} }}
:root[data-theme="dark"] {{ --bg:#151614; --fg:#ecebe6; --muted:#a4a39b; --line:#2d2f2a; --accent:#6fcf97; --accent-soft:#1d2e24; --code:#1f211d; --card:#1b1c19; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }}
main {{ max-width:1060px; margin:0 auto; padding:32px 16px 80px }}
header {{ border-bottom:1px solid var(--line); margin-bottom:28px; padding-bottom:20px }}
h1 {{ font-size:2rem; margin:0 0 6px; letter-spacing:-.01em }}
h2 {{ font-size:1.35rem; margin:44px 0 12px; padding-top:8px; border-top:1px solid var(--line) }}
h3 {{ font-size:1.05rem; margin:28px 0 8px }}
.lede {{ color:var(--muted); max-width:72ch; margin:0 }}
.kpis {{ display:flex; flex-wrap:wrap; gap:10px; margin:18px 0 0 }}
.kpi {{ background:var(--accent-soft); color:var(--fg); border-radius:8px; padding:8px 12px; font-size:.9rem }}
.kpi b {{ color:var(--accent) }}
nav a {{ margin-right:14px; color:var(--accent); text-decoration:none; font-size:.95rem }}
table {{ width:100%; border-collapse:collapse; font-size:.92rem; margin:10px 0 18px; display:block; overflow-x:auto }}
th, td {{ text-align:left; vertical-align:top; padding:8px 10px; border-bottom:1px solid var(--line) }}
th {{ color:var(--muted); font-weight:600; font-size:.82rem; text-transform:uppercase; letter-spacing:.04em }}
.spec {{ color:var(--muted); font-size:.82rem; margin-top:2px }}
.mono {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.8rem; color:var(--muted) }}
.total {{ font-weight:400; color:var(--muted); font-size:.9rem; margin-left:8px }}
code {{ background:var(--code); padding:1px 5px; border-radius:4px; font-size:.88em }}
pre {{ background:var(--code); padding:14px; border-radius:8px; overflow-x:auto; font-size:.84rem; line-height:1.45 }}
pre code {{ background:none; padding:0 }}
a {{ color:var(--accent) }}
.callout {{ border-left:4px solid var(--accent); background:var(--card); padding:12px 16px; border-radius:0 8px 8px 0; margin:16px 0 }}
section.district {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:4px 16px 8px; margin:14px 0 }}
footer {{ color:var(--muted); font-size:.85rem; margin-top:50px; border-top:1px solid var(--line); padding-top:14px }}
</style>
</head>
<body>
<main>
<header>
  <h1>Generative Canopy — shade analysis data package</h1>
  <p class="lede">Input layers for the Technion shade-index analysis of three New York City community districts
  (Bronx CD 2, Brooklyn CD 5, Queens CD 4). Every layer is clipped to the district plus a 300 m buffer,
  delivered in EPSG:2263 with elevations in meters NAVD88, as Cloud-Optimized GeoTIFF and GeoPackage.</p>
  <div class="kpis">
    <div class="kpi"><b>{len(MANIFEST["files"])}</b> files</div>
    <div class="kpi"><b>{fmt_bytes(total)}</b> total</div>
    <div class="kpi"><b>3</b> districts, 300 m buffer</div>
    <div class="kpi">built <b>{MANIFEST["generated"]}</b></div>
  </div>
  <p style="margin-top:16px"><nav>
    <a href="#download">Download</a><a href="#layers">What is in it</a><a href="#notes">Notes &amp; caveats</a><a href="#method">How it was built</a><a href="#citation">Licenses &amp; citation</a>
  </nav></p>
</header>

<h2 id="download">Download</h2>
<p>Files are hosted as GitHub Release assets. Click a file to download it, or fetch everything with
<a href="fetch_all.sh"><code>fetch_all.sh</code></a> (verifies SHA-256 checksums against <a href="manifest.json"><code>manifest.json</code></a>).</p>
{districts}

<h2 id="layers">What is in it</h2>
{layer_table()}

<h2 id="notes">Notes &amp; caveats</h2>
{md_to_html(NOTES)}

<h2 id="method">How it was built</h2>
<p>Everything is reproducible from the scripts in the repository (<code>uv sync</code>, then the <code>scripts/build_*.py</code> files; see the README).
In short:</p>
<ol>
<li>The three community-district polygons were buffered by 300 m (984.25 ft) in EPSG:2263 (<code>work/aoi/aoi.gpkg</code>).</li>
<li><strong>DTM</strong>: NOAA's cloud-optimized copy of the city's 2017 bare-earth DEM was read directly from S3, warped from EPSG:6539 + NAVD88 ft to EPSG:2263 + NAVD88 m, resampled bilinearly to 50 cm on a pixel-aligned grid and cut to the buffer.</li>
<li><strong>DSM</strong>: the city's 30 GB <code>Highest_Hit.zip</code> was downloaded from NYC Open Data, its 1 ft tiles mosaicked and processed identically to the DTM so the two models share a grid.</li>
<li><strong>Orthophoto</strong>: the 2024 6-inch JPEG2000 tiles intersecting each buffer (26 for Bx2, 47 + 19 for Bk5 which crosses into Queens, 27 for Qn4) were extracted from the NYS borough zips, mosaicked, averaged to 20 cm and cut to the buffer; band order R, G, B, NIR preserved.</li>
<li><strong>Leaf-on reference</strong>: NAIP 2022 quarter-quads were found through the Planetary Computer STAC API, the earliest summer date per quad chosen, and mosaicked at 60 cm.</li>
<li><strong>Canopy</strong>: the TNC/UVM 2021 rasters were clipped; land-cover class 1 was vectorised to canopy polygons; the tree centroid / crown layers were extracted from the citywide geodatabase by intersection with the buffer.</li>
<li><strong>Vectors</strong>: NYC Open Data (SODA API) and DCP ArcGIS services were queried by bounding box, features intersecting the buffer kept whole, geometries made valid, written to one GeoPackage per district.</li>
<li><code>write_manifest.py</code> inventories the outputs (GDAL/OGR metadata and SHA-256) and <code>build_site.py</code> renders this page from the manifest and <code>NOTES.md</code>.</li>
</ol>

<h2 id="citation">Licenses &amp; citation</h2>
<p>NYC Open Data and NYS GIS Clearinghouse layers are public domain. The 2021 land cover, canopy change and tree
crown data are &copy; The Nature Conservancy, developed by the University of Vermont Spatial Analysis Laboratory, released under
<a href="https://creativecommons.org/licenses/by-nc-sa/4.0/">CC BY-NC-SA 4.0</a> — non-commercial use only, share-alike, and the
accompanying metadata must travel with any redistribution. Please cite:</p>
<ul>
<li>The Nature Conservancy (2024). <em>New York City Land Cover, Tree Canopy Change, and Estimated Tree Location Data, 2021.</em> doi:<a href="https://doi.org/10.5281/zenodo.14053441">10.5281/zenodo.14053441</a></li>
<li>City of New York, Office of Technology and Innovation (2018). <em>Topobathymetric LiDAR Data (2017).</em> NYC Open Data 7sc8-jtbz.</li>
<li>New York State ITS Geospatial Services (2024). <em>New York City 2024 Orthoimagery.</em> NYS GIS Clearinghouse.</li>
</ul>

<footer>Assembled by Anthony Townsend (Cornell Tech, Urban Tech Hub) with Claude Code. Source scripts and issues:
<a href="https://github.com/Urban-Tech-Hub/generative-canopy">github.com/Urban-Tech-Hub/generative-canopy</a>.</footer>
</main>
</body>
</html>
"""
    (DOCS / "index.html").write_text(page)
    print(f"wrote {DOCS / 'index.html'} and fetch_all.sh")


if __name__ == "__main__":
    main()
