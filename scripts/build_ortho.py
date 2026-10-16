"""Build the 20 cm 4-band (RGB+NIR) orthophoto for each buffered AOI.

Source: NYS GIS Clearinghouse, NYC 2024 orthoimagery (6-inch, 4-band, flown
14-24 March 2024, leaf-off). Tiles are JPEG2000 inside per-borough zips at
https://gisdata.ny.gov/ortho/nysdop12/new_york_city/spcs/zips/ . Only the
tiles intersecting each AOI are pulled out of the remote zips (GDAL vsizip +
vsicurl), then mosaicked, resampled 6 in -> 20 cm (average) and clipped.

Run:  uv run python scripts/build_ortho.py [--cd 202 305 404]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "work" / "aoi" / "aoi.gpkg"
INDEX_DIR = ROOT / "work" / "ortho_index"
TILE_DIR = ROOT / "work" / "ortho_tiles"
PACKAGE = ROOT / "package"
ZIP_URL = (
    "https://gisdata.ny.gov/ortho/nysdop12/new_york_city/spcs/zips/boro_{boro}_sp24.zip"
)
BOROS = ["bronx", "brooklyn", "queens"]
# 20 cm expressed in US survey feet (EPSG:2263 units).
RES_FT = 0.2 / 0.3048006096

ENV = {
    **os.environ,
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "10",
    "GDAL_HTTP_TIMEOUT": "300",
    "GDAL_NUM_THREADS": "ALL_CPUS",
}


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, env=ENV)


def tiles_for(aoi_geom, boro: str) -> list[str]:
    idx = gpd.read_file(
        INDEX_DIR / f"ortho24_{boro}.gpkg", layer=f"24_b_{boro}_l06_4bd"
    )
    idx = idx.to_crs("EPSG:2263")
    return sorted(idx[idx.intersects(aoi_geom)].Image.tolist())


def fetch_tile(boro: str, image: str) -> Path:
    """Copy one JP2 tile (and its world file) out of the remote zip; skip if present."""
    dst_dir = TILE_DIR / boro
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{image}.jp2"
    if tile_ok(dst):
        return dst
    src = f"/vsizip//vsicurl/{ZIP_URL.format(boro=boro)}/{image}"
    for attempt in range(4):
        try:
            run(["gdal", "vsi", "copy", f"{src}.jp2", str(dst)])
            run(["gdal", "vsi", "copy", f"{src}.j2w", str(dst.with_suffix(".j2w"))])
            if tile_ok(dst):
                return dst
        except subprocess.CalledProcessError:
            pass
        time.sleep(15 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {boro}/{image}")


_ZIP_SIZES: dict[str, dict[str, int]] = {}


def zip_sizes(boro: str) -> dict[str, int]:
    """Entry sizes from the remote zip's central directory (one request per borough)."""
    if boro not in _ZIP_SIZES:
        out = subprocess.run(
            [
                "gdal",
                "vsi",
                "list",
                "-l",
                "--of",
                "json",
                f"/vsizip//vsicurl/{ZIP_URL.format(boro=boro)}",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=ENV,
        ).stdout
        _ZIP_SIZES[boro] = {e["name"]: e["size"] for e in json.loads(out)}
    return _ZIP_SIZES[boro]


def tile_ok(p: Path) -> bool:
    """A tile is complete when its size matches the zip entry and GDAL reads it as 5000x5000x4."""
    if not p.exists() or p.stat().st_size != zip_sizes(p.parent.name).get(p.name, -1):
        return False
    try:
        info = json.loads(
            subprocess.run(
                ["gdalinfo", "-json", str(p)],
                check=True,
                capture_output=True,
                text=True,
                env=ENV,
            ).stdout
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False
    return info.get("size") == [5000, 5000] and len(info.get("bands", [])) == 4


def main(cds: list[str]) -> None:
    aois = gpd.read_file(AOI_GPKG, layer="aoi_buffer300m")
    for cd in cds:
        t0 = time.time()
        geom = aois[aois.boro_cd == cd].geometry.union_all()
        tiles: list[Path] = []
        for boro in BOROS:
            names = tiles_for(geom, boro)
            print(f"[{cd}] {boro}: {len(names)} tiles", flush=True)
            for i, name in enumerate(names, 1):
                tiles.append(fetch_tile(boro, name))
                if i % 10 == 0:
                    print(f"[{cd}]   {boro} {i}/{len(names)} fetched", flush=True)
        out_dir = PACKAGE / cd
        out_dir.mkdir(parents=True, exist_ok=True)
        vrt = TILE_DIR / f"ortho24_{cd}.vrt"
        run(
            [
                "gdalbuildvrt",
                "-q",
                "-overwrite",
                "-a_srs",
                "EPSG:2263",
                str(vrt),
                *map(str, tiles),
            ]
        )
        out = out_dir / f"ortho_2024_20cm_rgbnir_{cd}.tif"
        run(
            [
                "gdalwarp",
                "-q",
                "-overwrite",
                "-t_srs",
                "EPSG:2263",
                "-tr",
                f"{RES_FT:.9f}",
                f"{RES_FT:.9f}",
                "-tap",
                "-r",
                "average",
                "-cutline",
                str(AOI_GPKG),
                "-cl",
                "aoi_buffer300m",
                "-cwhere",
                f"boro_cd='{cd}'",
                "-crop_to_cutline",
                "-dstnodata",
                "0",
                "-ot",
                "Byte",
                "-of",
                "COG",
                "-co",
                "COMPRESS=DEFLATE",
                "-co",
                "PREDICTOR=2",
                "-co",
                "NUM_THREADS=ALL_CPUS",
                "-co",
                "BIGTIFF=IF_SAFER",
                str(vrt),
                str(out),
            ]
        )
        print(
            f"[{cd}] wrote {out} ({out.stat().st_size / 1e9:.2f} GB) in {time.time() - t0:.0f}s",
            flush=True,
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd", nargs="*", default=["202", "305", "404"])
    main(ap.parse_args(sys.argv[1:]).cd)
