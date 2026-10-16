"""Build the 50 cm DSM and DTM for each buffered AOI from the NYC 2017 lidar.

DTM: NOAA Digital Coast copy of the NYC 2017 bare-earth, hydro-flattened DEM
     (1 ft, EPSG:6539, NAVD88 ft) read remotely from S3 as COGs.
DSM: NYC Open Data "Highest Hit" surface model (1 ft, EPSG:2263, NAVD88 ft)
     from the 2017 Topobathymetric LiDAR package (Highest_Hit.zip, 30 GB),
     unpacked locally first.

Both are resampled (bilinear) to 50 cm, clipped to the AOI, and written as
Cloud-Optimized GeoTIFFs in EPSG:2263 with elevations converted to METERS
(NAVD88, EPSG:5703) so Or's tools see one consistent unit.

Run:  uv run python scripts/build_elevation.py [--cd 202 305 404] [--dsm-dir DIR]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "work" / "aoi" / "aoi.gpkg"
PACKAGE = ROOT / "package"
WORK = ROOT / "work" / "elevation"
RES_FT = 0.5 / 0.3048006096  # 50 cm in US survey feet
DTM_VRT = (
    "/vsicurl/https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/dem/"
    "NYC_topobathy_BE_DEM_2017_9307/NYC_topobathy_BE_DEM_2017_m9307_EPSG-6539.vrt"
)

ENV = {
    **os.environ,
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_TIMEOUT": "300",
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.vrt",
    "GDAL_NUM_THREADS": "ALL_CPUS",
}


def warp(src: str, s_srs: str, cd: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "gdalwarp",
        "-q",
        "-overwrite",
        "-s_srs",
        s_srs,
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
        src,
        str(out),
    ]
    subprocess.run(cmd, check=True, env=ENV)


def dsm_vrt(dsm_dir: Path) -> Path:
    """Index every GeoTIFF under the unpacked Highest_Hit folder into one VRT."""
    tifs = sorted(
        p
        for p in dsm_dir.rglob("*.tif")
        if "hh" in p.name.lower() or "highest" in p.name.lower() or True
    )
    if not tifs:
        raise SystemExit(f"no GeoTIFFs under {dsm_dir}")
    WORK.mkdir(parents=True, exist_ok=True)
    lst = WORK / "dsm_tiles.txt"
    lst.write_text("\n".join(map(str, tifs)) + "\n")
    vrt = WORK / "dsm_2017_highest_hit.vrt"
    subprocess.run(
        ["gdalbuildvrt", "-q", "-overwrite", "-input_file_list", str(lst), str(vrt)],
        check=True,
        env=ENV,
    )
    print(f"DSM VRT from {len(tifs)} tiles -> {vrt}", flush=True)
    return vrt


def main(cds: list[str], dsm_dir: Path | None) -> None:
    vrt = dsm_vrt(dsm_dir) if dsm_dir else None
    for cd in cds:
        t0 = time.time()
        warp(DTM_VRT, "EPSG:6539+6360", cd, PACKAGE / cd / f"dtm_2017_50cm_m_{cd}.tif")
        print(f"[{cd}] DTM done {time.time() - t0:.0f}s", flush=True)
        if vrt:
            t0 = time.time()
            warp(
                str(vrt),
                "EPSG:2263+6360",
                cd,
                PACKAGE / cd / f"dsm_2017_50cm_m_{cd}.tif",
            )
            print(f"[{cd}] DSM done {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd", nargs="*", default=["202", "305", "404"])
    ap.add_argument(
        "--dsm-dir",
        type=Path,
        default=None,
        help="folder with unpacked Highest_Hit tiles",
    )
    a = ap.parse_args(sys.argv[1:])
    main(a.cd, a.dsm_dir)
