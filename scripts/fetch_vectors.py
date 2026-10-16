"""Fetch vector layers for each buffered community-district AOI.

Sources are NYC Open Data (Socrata SODA API) and NYC DCP ArcGIS feature
services. Every layer is queried by the AOI's WGS84 bounding box, clipped to
the 300 m buffer, reprojected to EPSG:2263 and written to one GeoPackage per
district under ``package/<cd>/vectors_<cd>.gpkg``.

Run:  uv run python scripts/fetch_vectors.py [--cd 202 305 404]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
AOI_GPKG = ROOT / "work" / "aoi" / "aoi.gpkg"
PACKAGE = ROOT / "package"
CRS_OUT = "EPSG:2263"

SODA = "https://data.cityofnewyork.us/resource/{id}.json"
DCP = "https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/{name}/FeatureServer/0/query"

# layer name -> (kind, dataset id/service name, geometry field, extra where)
LAYERS: dict[str, tuple[str, str, str, str | None]] = {
    "building_footprints": ("soda", "5zhs-2jue", "the_geom", None),
    "planimetric_sidewalk": ("soda", "52n9-sdep", "the_geom", None),
    "planimetric_roadbed": ("soda", "i36f-5ih7", "the_geom", None),
    "planimetric_median": ("soda", "ees7-4ufv", "the_geom", None),
    "parks_properties": ("soda", "enfh-gkve", "multipolygon", None),
    "dot_pedestrian_plazas": ("soda", "k5k6-6jex", "the_geom", None),
    "privately_owned_public_spaces": ("soda", "rvih-nhyn", "geocoded_column", None),
    "greenthumb_gardens": ("soda", "p78i-pat6", "multipolygon", None),
    # Active street/park trees only; retired points are trees that were removed.
    "forestry_tree_points": ("soda", "hn5i-inap", "location", "tpstructure='Full'"),
    "mappluto": ("dcp", "MAPPLUTO", None, None),
    "lion_streets": ("dcp", "LION", None, None),
    "planimetric_public_plazas": (
        "dcp",
        "NYC_Planimetric_Database__Public_Plazas_20250630",
        None,
        None,
    ),
}


def soda_fetch(
    ds: str, geom: str, bbox: tuple[float, float, float, float], where: str | None
) -> gpd.GeoDataFrame:
    """Page through a SODA dataset within a WGS84 bbox (minx, miny, maxx, maxy)."""
    minx, miny, maxx, maxy = bbox
    clauses = [f"within_box({geom},{maxy},{minx},{miny},{maxx})"]
    if where:
        clauses.append(where)
    feats: list[dict] = []
    offset, page = 0, 5000
    while True:
        params = {"$where": " AND ".join(clauses), "$limit": page, "$offset": offset}
        for attempt in range(5):
            r = requests.get(SODA.format(id=ds), params=params, timeout=180)
            if r.ok:
                break
            time.sleep(5 * (attempt + 1))
        r.raise_for_status()
        rows = r.json()
        feats.extend(rows)
        if len(rows) < page:
            break
        offset += page
    if not feats:
        return gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    geoms = [shape(f.pop(geom)) if f.get(geom) else None for f in feats]
    for f in feats:
        for k in [k for k in f if k.startswith(":@")]:
            f.pop(k)
    gdf = gpd.GeoDataFrame(feats, geometry=geoms, crs="EPSG:4326")
    return gdf[gdf.geometry.notna()]


def dcp_fetch(
    service: str, bbox: tuple[float, float, float, float]
) -> gpd.GeoDataFrame:
    """Page through an ArcGIS FeatureServer layer by WGS84 bbox, returning EPSG:2263."""
    feats: list[dict] = []
    offset, page = 0, 2000
    while True:
        params = {
            "where": "1=1",
            "geometry": json.dumps(
                {
                    "xmin": bbox[0],
                    "ymin": bbox[1],
                    "xmax": bbox[2],
                    "ymax": bbox[3],
                    "spatialReference": {"wkid": 4326},
                }
            ),
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "outSR": 2263,
            "resultOffset": offset,
            "resultRecordCount": page,
            "f": "geojson",
        }
        for attempt in range(5):
            r = requests.get(DCP.format(name=service), params=params, timeout=180)
            if r.ok:
                break
            time.sleep(5 * (attempt + 1))
        r.raise_for_status()
        fc = r.json()
        if "error" in fc:
            raise RuntimeError(fc["error"])
        feats.extend(fc.get("features", []))
        if (
            not fc.get("properties", {}).get("exceededTransferLimit")
            and len(fc.get("features", [])) < page
        ):
            break
        offset += page
    if not feats:
        return gpd.GeoDataFrame(geometry=[], crs=CRS_OUT)
    return gpd.GeoDataFrame.from_features(feats, crs=CRS_OUT)


def main(cds: list[str]) -> None:
    aois = gpd.read_file(AOI_GPKG, layer="aoi_buffer300m")
    cd_bounds = gpd.read_file(AOI_GPKG, layer="cd_boundary")
    for cd in cds:
        aoi = aois[aois.boro_cd == cd]
        out = PACKAGE / cd / f"vectors_{cd}.gpkg"
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        bbox = tuple(aoi.to_crs("EPSG:4326").total_bounds)
        aoi.to_file(out, layer="aoi_buffer300m")
        cd_bounds[cd_bounds.boro_cd == cd].to_file(out, layer="cd_boundary")
        clip_geom = aoi.geometry.union_all()
        for name, (kind, src, geom, where) in LAYERS.items():
            t0 = time.time()
            gdf = (
                soda_fetch(src, geom, bbox, where)
                if kind == "soda"
                else dcp_fetch(src, bbox)
            )
            if len(gdf):
                gdf = gdf.to_crs(CRS_OUT)
                gdf = gdf[gdf.intersects(clip_geom)]
            n = len(gdf)
            if n:
                gdf = gdf.set_geometry(gdf.geometry.make_valid())
                # Store the clipped geometry; keep polygons that straddle the buffer edge.
                gdf.to_file(out, layer=name)
            print(
                f"[{cd}] {name:32s} {n:7d} features  {time.time() - t0:5.1f}s",
                flush=True,
            )
        print(f"[{cd}] wrote {out}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cd", nargs="*", default=["202", "305", "404"])
    main(ap.parse_args(sys.argv[1:]).cd)
