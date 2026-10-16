"""Clip the TNC / UVM 2021 canopy products to each buffered AOI.

Inputs (downloaded from Zenodo record 14053441, CC BY-NC-SA 4.0):
  landcover_nyc_2021_6in.tif               8-class land cover, 6 in
  treecanopychange_nyc_2017_2021_6in.tif   canopy no-change / gain / loss, 6 in
  Trees_Centroids_Crown_Objects_2021.gdb   tree centroids, crown circles, crown objects

Outputs per district:
  landcover_2021_6in_<cd>.tif, canopy_change_2017_2021_6in_<cd>.tif  (COG, EPSG:2263)
  tree_canopy_2021_<cd>.gpkg  with layers: canopy_polygons (land cover class 1
  vectorised), tree_centroids, tree_crown_circles, tree_crown_objects

Run:  uv run python scripts/build_canopy.py --src DIR [--cd 202 305 404]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import pyogrio

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "work" / "aoi" / "aoi.gpkg"
PACKAGE = ROOT / "package"
ENV = {**os.environ, "GDAL_NUM_THREADS": "ALL_CPUS"}


def clip_raster(src: Path, cd: str, out: Path) -> None:
    subprocess.run(
        [
            "gdalwarp",
            "-q",
            "-overwrite",
            "-t_srs",
            "EPSG:2263",
            "-cutline",
            str(AOI_GPKG),
            "-cl",
            "aoi_buffer300m",
            "-cwhere",
            f"boro_cd='{cd}'",
            "-crop_to_cutline",
            "-r",
            "near",
            "-of",
            "COG",
            "-co",
            "COMPRESS=DEFLATE",
            "-co",
            "NUM_THREADS=ALL_CPUS",
            str(src),
            str(out),
        ],
        check=True,
        env=ENV,
    )


def canopy_polygons(landcover: Path, cd: str) -> gpd.GeoDataFrame:
    """Vectorise land-cover class 1 (tree canopy) into polygons."""
    with tempfile.TemporaryDirectory() as td:
        mask = Path(td) / "canopy.tif"
        subprocess.run(
            [
                "gdal",
                "raster",
                "calc",
                "--overwrite",
                "-i",
                f"lc={landcover}",
                "--calc",
                "(lc==1)*1",
                "--output-data-type",
                "Byte",
                "--no-data",
                "0",
                "-o",
                str(mask),
            ],
            check=True,
            env=ENV,
        )
        shp = Path(td) / "canopy.gpkg"
        subprocess.run(
            [
                "gdal_polygonize.py",
                "-q",
                str(mask),
                "-f",
                "GPKG",
                str(shp),
                "canopy",
                "value",
            ],
            check=True,
            env=ENV,
        )
        gdf = gpd.read_file(shp)
    gdf["area_sqft"] = gdf.geometry.area
    gdf["source"] = "TNC/UVM 2021 land cover class 1 (tree canopy > 8 ft)"
    return gdf[["area_sqft", "source", "geometry"]]


def main(src: Path, cds: list[str]) -> None:
    aois = gpd.read_file(AOI_GPKG, layer="aoi_buffer300m")
    gdb = next(src.glob("*.gdb"))
    layers = [name for name, _ in pyogrio.list_layers(gdb)]
    print("gdb layers:", layers, flush=True)
    for cd in cds:
        t0 = time.time()
        out_dir = PACKAGE / cd
        out_dir.mkdir(parents=True, exist_ok=True)
        aoi = aois[aois.boro_cd == cd]
        geom = aoi.geometry.union_all()
        lc_out = out_dir / f"landcover_2021_6in_{cd}.tif"
        clip_raster(src / "landcover_nyc_2021_6in.tif", cd, lc_out)
        clip_raster(
            src / "treecanopychange_nyc_2017_2021_6in.tif",
            cd,
            out_dir / f"canopy_change_2017_2021_6in_{cd}.tif",
        )
        gpkg = out_dir / f"tree_canopy_2021_{cd}.gpkg"
        if gpkg.exists():
            gpkg.unlink()
        canopy_polygons(lc_out, cd).to_file(gpkg, layer="canopy_polygons")
        bbox = tuple(aoi.to_crs("EPSG:2263").total_bounds)
        for name in layers:
            g = gpd.read_file(gdb, layer=name, bbox=bbox)
            g = g.to_crs("EPSG:2263")
            g = g[g.intersects(geom)]
            key = name.lower()
            lname = (
                "tree_centroids"
                if "centroid" in key
                else "tree_crown_circles"
                if "shape" in key
                else "tree_crown_objects"
            )
            g.to_file(gpkg, layer=lname)
            print(f"[{cd}] {name} -> {lname}: {len(g)}", flush=True)
        print(f"[{cd}] canopy done {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--cd", nargs="*", default=["202", "305", "404"])
    a = ap.parse_args(sys.argv[1:])
    main(a.src, a.cd)
