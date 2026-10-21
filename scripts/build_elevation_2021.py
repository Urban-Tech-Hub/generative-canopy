"""Build the 50 cm DSM and DTM for each buffered AOI from the NYC 2021 lidar
point cloud (EagleView, 12-21 May 2021) hosted by NYS ITS.

Source: ftp://ftp.gis.ny.gov/elevation/LIDAR/NYC_2021/<tile>.las  (LAS 1.4, PDRF 6,
        NAD83(2011) / New York Long Island ftUS + NAVD88 (GEOID18) ftUS; the files
        carry no CRS record, so it is assigned here).
Tiles per district come from the state's NYC2021_LAS_Index shapefile intersected
with the 300 m AOI buffers (work/las2021/tiles_by_cd.json, written by
work/las2021/fetch_las.sh's companion step in this script's --index mode).

DSM = highest classified return per 50 cm cell (classes 2 ground, 3-5 vegetation,
      6 building, 8 model key point, 9 water). Class 1 (unclassified) is deliberately
      excluded: in this delivery it holds dense mid-air noise, striped by flight line,
      up to ~45 m above ground (class 18 only catches the higher noise), and a DSM
      that includes it is unusable. Small gaps (< 5 m) are interpolated; the remaining
      holes are open water with no returns and are filled from the DTM.
DTM = class 2 (ground) + 8 (model key point) returns, IDW onto the 50 cm grid,
      remaining holes (buildings, water) interpolated with gdal_fillnodata.

Both are then warped (bilinear) to the package grid: EPSG:2263, 50 cm, -tap,
clipped to the AOI, elevations converted to METERS (NAVD88, EPSG:5703), COG.

Run:  uv run python scripts/build_elevation_2021.py [--cd 202 305 404] [--las-dir work/las2021]
Requires the `pdal` CLI (brew install pdal).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "work" / "aoi" / "aoi.gpkg"
PACKAGE = ROOT / "package"
WORK = ROOT / "work" / "elevation_2021"
LAS_DIR = ROOT / "work" / "las2021"
SRC_SRS = "EPSG:6539+6360"  # NAD83(2011) NY Long Island ftUS + NAVD88 ftUS
RES_FT = 0.5 / 0.3048006096  # 50 cm in US survey feet
Z_MIN_FT, Z_MAX_FT = -20.0, 900.0  # safety net; plausible range in these districts

ENV = {**os.environ, "GDAL_NUM_THREADS": "ALL_CPUS"}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, env=ENV)


def grid_bounds(cd: str) -> tuple[float, float, float, float]:
    """AOI bounds in the LAS CRS, snapped outward to the 50 cm grid."""
    import geopandas as gpd

    a = gpd.read_file(AOI_GPKG, layer="aoi_buffer300m")
    g = a[a.boro_cd == cd].to_crs("EPSG:6539").geometry.iloc[0]
    minx, miny, maxx, maxy = g.bounds

    def snap(v: float, up: bool) -> float:
        return (int(v / RES_FT) + (1 if up else -1)) * RES_FT

    return snap(minx, False), snap(miny, False), snap(maxx, True), snap(maxy, True)


def pdal_grid(tiles: list[Path], out: Path, bounds: tuple, *, dsm: bool) -> dict:
    minx, miny, maxx, maxy = bounds
    width = round((maxx - minx) / RES_FT)
    height = round((maxy - miny) / RES_FT)
    stages: list[dict] = [
        {"type": "readers.las", "filename": str(t), "override_srs": SRC_SRS}
        for t in tiles
    ]
    if dsm:
        stages.append(
            {
                "type": "filters.range",
                "limits": (
                    "Classification[2:6],Classification[8:9],"
                    f"Withheld[0:0],Z[{Z_MIN_FT}:{Z_MAX_FT}]"
                ),
            }
        )
        output_type, radius, window = "max", RES_FT * 0.75, 3
    else:
        stages.append(
            {
                "type": "filters.range",
                "limits": "Classification[2:2],Classification[8:8],Withheld[0:0]",
            }
        )
        output_type, radius, window = "idw", RES_FT * 1.5, 6
    stages.append(
        {
            "type": "writers.gdal",
            "filename": str(out),
            "gdaldriver": "GTiff",
            "output_type": output_type,
            "resolution": RES_FT,
            "radius": radius,
            "window_size": window,
            "origin_x": minx,
            "origin_y": miny,
            "width": width,
            "height": height,
            "nodata": -9999,
            "data_type": "float32",
            "gdalopts": "COMPRESS=DEFLATE,PREDICTOR=3,TILED=YES,BIGTIFF=YES",
        }
    )
    pipe = out.with_suffix(".json")
    pipe.write_text(json.dumps({"pipeline": stages}, indent=1))
    run(["pdal", "pipeline", str(pipe)])
    return {"width": width, "height": height, "tiles": len(tiles)}


def warp(src: Path, cd: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "gdalwarp",
            "-q",
            "-overwrite",
            "-s_srs",
            SRC_SRS,
            "-t_srs",
            "EPSG:2263+5703",
            "-tr",
            f"{RES_FT:.9f}",
            f"{RES_FT:.9f}",
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
            "-9999",
            "-ot",
            "Float32",
            "-of",
            "COG",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "PREDICTOR=3",
            "-co",
            "NUM_THREADS=ALL_CPUS",
            str(src),
            str(out),
        ]
    )


def main(cds: list[str], las_dir: Path) -> None:
    by_cd = json.loads((las_dir / "tiles_by_cd.json").read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    for cd in cds:
        tiles = [las_dir / f for f in by_cd[cd]]
        missing = [t.name for t in tiles if not t.exists()]
        if missing:
            raise SystemExit(f"[{cd}] {len(missing)} tiles missing: {missing[:5]}")
        bounds = grid_bounds(cd)
        # DTM first: its filled surface also closes the water holes in the DSM.
        t0 = time.time()
        dtm_raw = WORK / f"dtm_2021_raw_{cd}.tif"
        info = pdal_grid(tiles, dtm_raw, bounds, dsm=False)
        dtm_filled = WORK / f"dtm_2021_filled_{cd}.tif"
        fillnodata(dtm_raw, dtm_filled, max_dist_px=600)
        out = PACKAGE / cd / f"dtm_2021_50cm_m_{cd}.tif"
        warp(dtm_filled, cd, out)
        print(
            f"[{cd}] DTM {info['tiles']} tiles -> {out.name} {time.time() - t0:.0f}s",
            flush=True,
        )
        t0 = time.time()
        dsm_raw = WORK / f"dsm_2021_raw_{cd}.tif"
        info = pdal_grid(tiles, dsm_raw, bounds, dsm=True)
        dsm_gaps = WORK / f"dsm_2021_gapfilled_{cd}.tif"
        fillnodata(dsm_raw, dsm_gaps, max_dist_px=10)
        dsm_filled = WORK / f"dsm_2021_filled_{cd}.tif"
        fill_from(dsm_gaps, dtm_filled, dsm_filled)
        out = PACKAGE / cd / f"dsm_2021_50cm_m_{cd}.tif"
        warp(dsm_filled, cd, out)
        print(
            f"[{cd}] DSM {info['tiles']} tiles -> {out.name} {time.time() - t0:.0f}s",
            flush=True,
        )


def fillnodata(src: Path, dst: Path, max_dist_px: int) -> None:
    run(
        [
            "gdal_fillnodata",
            "-q",
            "-md",
            str(max_dist_px),
            "-si",
            "1",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "TILED=YES",
            "-co",
            "BIGTIFF=YES",
            str(src),
            str(dst),
        ]
    )


def fill_from(src: Path, fallback: Path, dst: Path) -> None:
    """Write src with its remaining nodata cells (open water) taken from fallback."""
    import rasterio

    with rasterio.open(src) as a, rasterio.open(fallback) as b:
        prof = a.profile | {"compress": "deflate", "tiled": True, "bigtiff": "yes"}
        with rasterio.open(dst, "w", **prof) as o:
            for _, win in a.block_windows(1):
                x = a.read(1, window=win)
                y = b.read(1, window=win)
                hole = x == a.nodata
                x[hole] = y[hole]
                o.write(x, 1, window=win)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd", nargs="*", default=["202", "305", "404"])
    ap.add_argument("--las-dir", type=Path, default=LAS_DIR)
    a = ap.parse_args(sys.argv[1:])
    main(a.cd, a.las_dir)
