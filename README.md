# Generative Canopy — shade analysis data package

Input layers for a shade-index analysis of three New York City community districts
(Bronx CD 2 Hunts Point–Longwood, Brooklyn CD 5 East New York, Queens CD 4 Corona–Elmhurst),
assembled for the Technion Big Data Architectural Lab (Or Aleksandrowicz).

**Download page and documentation: https://urban-tech-hub.github.io/generative-canopy/**

The data files are too large for git; they are attached to GitHub Releases and listed in
[`docs/manifest.json`](docs/manifest.json). This repository holds the scripts that built them and
the notes that describe their sources and caveats ([`docs/NOTES.md`](docs/NOTES.md)).

## What is delivered, per district

| Requested | File | Source |
|---|---|---|
| DSM 50 cm | `dsm_2021_50cm_m_<cd>.tif` | NYC 2021 lidar, highest return (LAS from NYS ITS FTP, gridded here) |
| DTM 50 cm | `dtm_2021_50cm_m_<cd>.tif` | NYC 2021 lidar, ground returns (same) |
| DSM / DTM 2017 (kept for change detection) | `dsm_2017_50cm_m_<cd>.tif`, `dtm_2017_50cm_m_<cd>.tif` | NYC 2017 lidar Highest Hit (NYC Open Data); bare earth (NOAA Digital Coast mirror) |
| Orthophoto 20 cm + NIR | `ortho_2024_20cm_rgbnir_<cd>.tif` | NYS GIS Clearinghouse, NYC 2024 6-inch 4-band |
| Leaf-on reference | `naip_2022_leafon_60cm_rgbnir_<cd>.tif` | USDA NAIP July/Sept 2022 |
| Tree canopy polygons, crowns, tree points (all trees) | `tree_canopy_2021_<cd>.gpkg` | TNC / UVM 2021 (Zenodo 14053441, CC BY-NC-SA) |
| Land cover, canopy change | `landcover_2021_6in_<cd>.tif`, `canopy_change_2017_2021_6in_<cd>.tif` | TNC / UVM 2021 |
| Land use, ROW, open space, footprints, public tree trunks | `vectors_<cd>.gpkg` | NYC Open Data, DCP |

All in EPSG:2263, elevations in meters NAVD88, clipped to the district + 300 m buffer.

## Rebuilding

```bash
uv sync
uv run python scripts/fetch_vectors.py          # Socrata / ArcGIS vectors -> package/<cd>/vectors_<cd>.gpkg
uv run python scripts/build_elevation.py --dsm-dir <unzipped Highest_Hit>   # 2017 DTM from NOAA S3, DSM from city zip
uv run python scripts/index_las_2021.py         # which 2021 LAS tiles cover each district
scripts/fetch_las_2021.sh                        # 2021 LAS tiles (46 GB for the three districts) from ftp.gis.ny.gov
uv run python scripts/build_elevation_2021.py   # 2021 DSM/DTM from the LAS tiles (needs `brew install pdal`)
uv run python scripts/build_ortho.py            # 2024 tiles out of the NYS borough zips -> 20 cm COG
uv run python scripts/build_naip.py             # leaf-on NAIP via Planetary Computer STAC
uv run python scripts/build_canopy.py --src <folder with the three Zenodo files>
uv run python scripts/write_manifest.py --release-base https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/<tag>
uv run python scripts/build_site.py             # docs/index.html + docs/fetch_all.sh
```

`scripts/pdl.py` is a parallel range downloader for Zenodo, which throttles single connections.
Pass `--cd 101 102 ...` to any build script to extend to other community districts; the district
boundaries come from `data/generative-canopy-community-districts.geojson` (add more there first).
