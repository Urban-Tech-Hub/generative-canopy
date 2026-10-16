"""Build a leaf-on summer 4-band (RGB+NIR) reference image per AOI from NAIP.

NAIP is the only free leaf-on imagery over NYC. It is 60 cm (2022) so it is a
canopy-QC reference, not a substitute for the 20 cm 2024 orthophoto. Items are
discovered through the Microsoft Planetary Computer STAC and read as COGs.

Run:  uv run python scripts/build_naip.py [--cd 202 305 404]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import planetary_computer as pc
import pystac_client

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "work" / "aoi" / "aoi.gpkg"
PACKAGE = ROOT / "package"
WORK = ROOT / "work" / "naip"
STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
# Mid-summer leaf-on window; 2022 is the most recent summer NAIP over NYC.
DATETIME = "2022-06-15/2022-09-30"

ENV = {
    **os.environ,
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_TIMEOUT": "300",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
}


def main(cds: list[str]) -> None:
    aois = gpd.read_file(AOI_GPKG, layer="aoi_buffer300m")
    cat = pystac_client.Client.open(STAC, modifier=pc.sign_inplace)
    WORK.mkdir(parents=True, exist_ok=True)
    for cd in cds:
        aoi = aois[aois.boro_cd == cd]
        bbox = list(aoi.to_crs("EPSG:4326").total_bounds)
        items = list(
            cat.search(collections=["naip"], bbox=bbox, datetime=DATETIME).items()
        )
        # Prefer the earliest (most leaf-on) date per quarter-quad.
        best: dict[str, object] = {}
        for it in sorted(items, key=lambda i: i.datetime):
            # id looks like ny_m_4007309_sw_18_060_20220719[_...]; group by quad + quarter
            parts = it.id.split("_")
            qq = f"{parts[2]}_{parts[3]}"
            best.setdefault(qq, it)
        chosen = list(best.values())
        dates = sorted({it.datetime.date().isoformat() for it in chosen})
        urls = [it.assets["image"].href for it in chosen]
        print(f"[{cd}] {len(chosen)} NAIP quarter-quads, dates {dates}", flush=True)
        vrt = WORK / f"naip_{cd}.vrt"
        subprocess.run(
            [
                "gdalbuildvrt",
                "-q",
                "-overwrite",
                str(vrt),
                *[f"/vsicurl/{u}" for u in urls],
            ],
            check=True,
            env=ENV,
        )
        out_dir = PACKAGE / cd
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"naip_2022_leafon_60cm_rgbnir_{cd}.tif"
        subprocess.run(
            [
                "gdalwarp",
                "-q",
                "-overwrite",
                "-t_srs",
                "EPSG:2263",
                "-tr",
                "1.968503937",
                "1.968503937",
                "-tap",
                "-r",
                "bilinear",
                "-cutline",
                str(AOI_GPKG),
                "-cl",
                "aoi_buffer300m",
                "-cwhere",
                f"boro_cd='{cd}'",
                "-crop_to_cutline",
                "-dstnodata",
                "0",
                "-of",
                "COG",
                "-co",
                "COMPRESS=DEFLATE",
                "-co",
                "PREDICTOR=2",
                str(vrt),
                str(out),
            ],
            check=True,
            env=ENV,
        )
        (out_dir / f"naip_2022_leafon_60cm_rgbnir_{cd}.dates.txt").write_text(
            "\n".join(dates) + "\n"
        )
        print(f"[{cd}] wrote {out} ({out.stat().st_size / 1e6:.0f} MB)", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd", nargs="*", default=["202", "305", "404"])
    main(ap.parse_args(sys.argv[1:]).cd)
