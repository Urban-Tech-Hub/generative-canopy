"""Fetch the NYS tile index for the NYC 2021 lidar and list the LAS tiles that
intersect each buffered AOI (work/las2021/tiles_by_cd.json, tiles_all.txt),
ordered district by district so scripts/fetch_las_2021.sh completes one
district at a time.

Run:  uv run python scripts/index_las_2021.py [--cd 202 305 404]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "work" / "aoi" / "aoi.gpkg"
LAS_DIR = ROOT / "work" / "las2021"
FTP = "ftp://ftp.gis.ny.gov/elevation/LIDAR/NYC_2021/"
INDEX = "NYC2021_LAS_Index"


def main(cds: list[str]) -> None:
    LAS_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("shp", "shx", "dbf", "prj", "cpg", "shp.xml"):
        dst = LAS_DIR / f"{INDEX}.{ext}"
        if not dst.exists():
            urllib.request.urlretrieve(f"{FTP}{INDEX}.{ext}", dst)
    idx = gpd.read_file(LAS_DIR / f"{INDEX}.shp")
    aoi = gpd.read_file(AOI_GPKG, layer="aoi_buffer300m").to_crs(idx.crs)
    by_cd: dict[str, list[str]] = {}
    for _, a in aoi.iterrows():
        if a.boro_cd in cds:
            hit = idx[idx.intersects(a.geometry)]
            by_cd[a.boro_cd] = sorted(hit.FILENAME.tolist())
    order: list[str] = []
    for cd in cds:
        order += [f for f in by_cd.get(cd, []) if f not in order]
    (LAS_DIR / "tiles_by_cd.json").write_text(json.dumps(by_cd, indent=1))
    (LAS_DIR / "tiles_all.txt").write_text("\n".join(order) + "\n")
    print({k: len(v) for k, v in by_cd.items()}, "union", len(order))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd", nargs="*", default=["202", "404", "305"])
    main(ap.parse_args(sys.argv[1:]).cd)
