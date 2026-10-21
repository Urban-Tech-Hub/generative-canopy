"""Inventory everything under package/ into manifest.json (sizes, checksums, CRS,
resolution, extent, layer counts) so the website and README stay in sync with
the files that were actually built.

Run:  uv run python scripts/write_manifest.py [--release-base URL]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "package"
MANIFEST = ROOT / "docs" / "manifest.json"

DISTRICTS = {
    "202": {"code": "Bx2", "name": "Hunts Point, Longwood & Morrisania (Bronx CD 2)"},
    "305": {
        "code": "Bk5",
        "name": "East New York, Cypress Hills & Starrett City (Brooklyn CD 5)",
    },
    "404": {"code": "Qn4", "name": "Corona & Elmhurst (Queens CD 4)"},
}

# filename prefix -> (requested layer, title, source, vintage, license)
LAYERS = {
    "dsm_2021_50cm_m": (
        "DSM",
        "Digital Surface Model 2021 (highest return), 50 cm, meters NAVD88",
        "NYC 2021 lidar (EagleView for NYC OTI), LAS tiles hosted by NYS ITS GIS (ftp.gis.ny.gov), gridded by this project",
        "Lidar flown 12-21 May 2021, leaf-on emerging",
        "Public domain (NYC / NYS ITS)",
    ),
    "dtm_2021_50cm_m": (
        "DTM",
        "Digital Terrain Model 2021 (ground-classified returns, holes interpolated), 50 cm, meters NAVD88",
        "NYC 2021 lidar (EagleView for NYC OTI), LAS tiles hosted by NYS ITS GIS (ftp.gis.ny.gov), gridded by this project",
        "Lidar flown 12-21 May 2021",
        "Public domain (NYC / NYS ITS)",
    ),
    "dsm_2017_50cm_m": (
        "DSM (2017, superseded)",
        "Digital Surface Model, 50 cm, meters NAVD88",
        "NYC OTI 2017 Topobathymetric LiDAR - Highest Hit DSM (NYC Open Data 7sc8-jtbz)",
        "Lidar flown 3-17 May 2017, 50% leaf-off",
        "NYC Open Data Terms of Use (public domain)",
    ),
    "dtm_2017_50cm_m": (
        "DTM (2017, superseded)",
        "Digital Terrain Model (bare earth, hydro-flattened), 50 cm, meters NAVD88",
        "NYC OTI 2017 Topobathymetric LiDAR - Bare Earth DEM, NOAA Digital Coast copy (ID 9307)",
        "Lidar flown 3-17 May 2017",
        "NYC Open Data Terms of Use (public domain)",
    ),
    "ortho_2024_20cm_rgbnir": (
        "Orthophoto",
        "Orthophoto 2024, 20 cm, 4-band R-G-B-NIR",
        "NYS GIS Program Office / NYC OTI 2024 NYC orthoimagery (6 in source), NYS GIS Clearinghouse",
        "Flown 14-24 March 2024, leaf-off, true ortho",
        "Public domain (NYS ITS)",
    ),
    "naip_2022_leafon_60cm_rgbnir": (
        "Orthophoto (leaf-on reference)",
        "NAIP 2022 summer, 60 cm, 4-band R-G-B-NIR",
        "USDA NAIP via Microsoft Planetary Computer",
        "Flown 19 Jul and 15 Sep 2022, leaf-on",
        "Public domain (USDA)",
    ),
    "landcover_2021_6in": (
        "Tree canopy",
        "Land cover 2021, 8 classes, 6 in (class 1 = tree canopy)",
        "The Nature Conservancy / UVM Spatial Analysis Lab (Zenodo 10.5281/zenodo.14053441)",
        "2021 lidar + 2021 NAIP + 2022 NYS ortho",
        "CC BY-NC-SA 4.0",
    ),
    "canopy_change_2017_2021_6in": (
        "Tree canopy",
        "Tree canopy change 2017-2021, 6 in (1 no change, 2 gain, 3 loss)",
        "The Nature Conservancy / UVM Spatial Analysis Lab (Zenodo 10.5281/zenodo.14053441)",
        "2017 vs 2021",
        "CC BY-NC-SA 4.0",
    ),
    "tree_canopy_2021": (
        "Tree canopy / tree locations",
        "Canopy polygons + estimated tree centroids, crown circles and crown objects (all trees > 8 ft, public and private)",
        "The Nature Conservancy / UVM Spatial Analysis Lab (Zenodo 10.5281/zenodo.14053441)",
        "2021",
        "CC BY-NC-SA 4.0",
    ),
    "vectors": (
        "Land use, open space, building footprints, tree trunks",
        "Building footprints, MapPLUTO land use, planimetric sidewalk/roadbed/median/plazas, parks, DOT plazas, POPS, GreenThumb gardens, LION streets, active Forestry tree points",
        "NYC Open Data (OTI, DCP, DPR, DOT); DCP ArcGIS services",
        "Snapshot fetched VECTOR_DATE",
        "NYC Open Data Terms of Use (public domain)",
    ),
}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def raster_info(p: Path) -> dict:
    j = json.loads(
        subprocess.check_output(["gdalinfo", "-json", "-norat", "-nomd", str(p)])
    )
    gt = j["geoTransform"]
    crs = j.get("stac", {}).get("proj:epsg") or j["coordinateSystem"]["wkt"][:40]
    return {
        "type": "raster",
        "format": "Cloud-Optimized GeoTIFF",
        "size_px": j["size"],
        "pixel_size_ft": [abs(gt[1]), abs(gt[5])],
        "pixel_size_m": [
            round(abs(gt[1]) * 0.3048006096, 3),
            round(abs(gt[5]) * 0.3048006096, 3),
        ],
        "bands": len(j["bands"]),
        "dtype": j["bands"][0]["type"],
        "nodata": j["bands"][0].get("noDataValue"),
        "crs": crs,
        "bbox_wgs84": j.get("wgs84Extent", {}).get("coordinates"),
    }


def vector_info(p: Path) -> dict:
    out = subprocess.check_output(["ogrinfo", "-so", "-ro", str(p)], text=True)
    layers = {}
    for line in out.splitlines():
        if line[:1].isdigit() and ":" in line:
            name = line.split(":", 1)[1].split("(")[0].strip()
            n = subprocess.check_output(
                ["ogrinfo", "-so", "-ro", str(p), name], text=True
            )
            cnt = next(
                (
                    ln.split(":")[1].strip()
                    for ln in n.splitlines()
                    if ln.startswith("Feature Count")
                ),
                "?",
            )
            geom = next(
                (
                    ln.split(":")[1].strip()
                    for ln in n.splitlines()
                    if ln.startswith("Geometry:")
                ),
                "?",
            )
            layers[name] = {"features": int(cnt), "geometry": geom}
    return {
        "type": "vector",
        "format": "GeoPackage",
        "crs": "EPSG:2263",
        "layers": layers,
    }


def main(release_base: str | None) -> None:
    files = []
    for p in sorted(PACKAGE.rglob("*")):
        if (
            not p.is_file()
            or p.name.startswith(".")
            or p.name.endswith((".aux.xml", ".dates.txt"))
        ):
            continue
        cd = p.parent.name
        key = next((k for k in LAYERS if p.name.startswith(k)), None)
        if key is None or cd not in DISTRICTS:
            continue
        req, title, source, vintage, lic = LAYERS[key]
        if key == "vectors":
            vintage = vintage.replace(
                "VECTOR_DATE",
                datetime.fromtimestamp(p.stat().st_mtime).date().isoformat(),
            )
        info = (
            raster_info(p)
            if p.suffix == ".tif"
            else vector_info(p)
            if p.suffix == ".gpkg"
            else {"type": "text"}
        )
        files.append(
            {
                "district": cd,
                "district_code": DISTRICTS[cd]["code"],
                "file": p.name,
                "bytes": p.stat().st_size,
                "sha256": sha256(p),
                "requested_layer": req,
                "title": title,
                "source": source,
                "vintage": vintage,
                "license": lic,
                "url": f"{release_base.rstrip('/')}/{p.name}" if release_base else None,
                **info,
            }
        )
        print(f"{cd} {p.name:48s} {p.stat().st_size / 1e6:8.1f} MB", flush=True)
    MANIFEST.parent.mkdir(exist_ok=True)
    MANIFEST.write_text(
        json.dumps(
            {
                "generated": date.today().isoformat(),
                "crs": "EPSG:2263 (NAD83 / New York Long Island, US survey feet); elevations in meters NAVD88 (EPSG:5703)",
                "buffer_m": 300,
                "districts": DISTRICTS,
                "files": files,
            },
            indent=1,
        )
    )
    print(
        f"wrote {MANIFEST} ({len(files)} files, {sum(f['bytes'] for f in files) / 1e9:.2f} GB)"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--release-base", default=None)
    main(ap.parse_args(sys.argv[1:]).release_base)
