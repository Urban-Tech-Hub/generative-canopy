"""Compare the 2021 DSM/DTM with the 2017 pair and the TNC land cover, per district,
and print the figures quoted in docs/NOTES.md.

Run:  uv run python scripts/qc_elevation_2021.py [--cd 202 305 404]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, reproject

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package"
LC = {
    1: "tree",
    2: "grass",
    3: "soil",
    4: "water",
    5: "building",
    6: "road",
    7: "imperv",
    8: "rail",
}


def landcover_on(ref: rasterio.DatasetReader, cd: str) -> np.ndarray:
    lc = np.zeros(ref.shape, dtype="uint8")
    with rasterio.open(PACKAGE / cd / f"landcover_2021_6in_{cd}.tif") as src:
        reproject(
            rasterio.band(src, 1),
            lc,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=Resampling.mode,
            dst_nodata=0,
        )
    return lc


def compare(cd: str, kind: str) -> None:
    new = rasterio.open(PACKAGE / cd / f"{kind}_2021_50cm_m_{cd}.tif")
    a = new.read(1)
    b = rasterio.open(PACKAGE / cd / f"{kind}_2017_50cm_m_{cd}.tif").read(1)
    assert a.shape == b.shape, "2021 and 2017 grids differ"
    lc = landcover_on(new, cd)
    m = (a > -9000) & (b > -9000)
    d = a - b
    land = m & (lc != 4) & (lc != 0)
    dl = d[land]
    print(
        f"[{cd}] {kind.upper()} 2021-2017 on land: median {np.median(dl):+.2f} m, "
        f"|d|<0.25 {100 * (abs(dl) < 0.25).mean():.1f}%, |d|<0.5 {100 * (abs(dl) < 0.5).mean():.1f}%, "
        f"d>5 {100 * (dl > 5).mean():.2f}%, d<-5 {100 * (dl < -5).mean():.2f}%; "
        f"nodata 2021 {int((a == -9999).sum())} / 2017 {int((b == -9999).sum())}"
    )
    for k, name in LC.items():
        c = m & (lc == k)
        if c.sum():
            dd = d[c]
            print(
                f"      {name:9s} n={c.sum():9d} median {np.median(dd):+.2f} "
                f"|d|<0.5 {100 * (abs(dd) < 0.5).mean():5.1f}% d>5 {100 * (dd > 5).mean():5.2f}% d<-5 {100 * (dd < -5).mean():5.2f}%"
            )


def ndsm(cd: str) -> None:
    s = rasterio.open(PACKAGE / cd / f"dsm_2021_50cm_m_{cd}.tif").read(1)
    t = rasterio.open(PACKAGE / cd / f"dtm_2021_50cm_m_{cd}.tif").read(1)
    v = (s > -9000) & (t > -9000)
    h = (s - t)[v]
    print(
        f"[{cd}] nDSM 2021: p50 {np.percentile(h, 50):.1f} p90 {np.percentile(h, 90):.1f} "
        f"p99 {np.percentile(h, 99):.1f} max {h.max():.1f} m; below ground (< -1 m) {100 * (h < -1).mean():.2f}%"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd", nargs="*", default=["202", "305", "404"])
    for cd in ap.parse_args(sys.argv[1:]).cd:
        compare(cd, "dsm")
        compare(cd, "dtm")
        ndsm(cd)
