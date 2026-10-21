### Read this first

- **Everything is in one grid.** All rasters and vectors are in **EPSG:2263** (NAD83 / New York Long Island, US survey feet), the native CRS of every NYC dataset. Raster grids are pixel-aligned to that CRS (`-tap`): the 50 cm products have a pixel of exactly 1.6404 ft, the 20 cm ortho 0.6562 ft. **Elevations are in meters** (NAVD88, EPSG:5703), converted from the city's feet so the DSM, DTM and any nDSM you derive are directly in metric units. Horizontal coordinates stay in feet; reproject everything to EPSG:6539 or UTM 18N if you prefer metric x/y.
- **Each district is clipped to its boundary plus a 300 m buffer** so buildings and trees just outside the district still cast their shadows inward. Rasters are masked to the buffer polygon; vector features are kept whole if they intersect it. The `aoi_buffer300m` and `cd_boundary` layers in each `vectors_*.gpkg` give you the clip extents.
- **The two biggest limitations are season and classification.** Since v1.1 the surface and terrain models come from the city's May 2021 lidar (the 2017 pair is still shipped for change detection); the orthophoto is leaf-off; the canopy layer is 2021, from the same lidar. The sections below say what that means and how to compensate.

### 1. DSM and DTM (50 cm)

**2021 (use these):** `dsm_2021_50cm_m_*.tif`, `dtm_2021_50cm_m_*.tif`

| | DSM 2021 | DTM 2021 |
|---|---|---|
| Source | NYC 2021 lidar point cloud (EagleView-Surdex JV for NYC OTI), LAS 1.4 tiles hosted by NYS ITS GIS at `ftp://ftp.gis.ny.gov/elevation/LIDAR/NYC_2021/` (not in the state's public index; see `docs/reports/`) | same |
| Method | highest return per 50 cm cell from the **classified** points only (2 ground, 3–5 vegetation, 6 building, 8 model key point, 9 water); gaps under 5 m interpolated; open water filled from the DTM | ground (2) + model key point (8) returns, inverse-distance onto the 50 cm grid; holes under buildings and water interpolated from the surrounding ground (`gdal_fillnodata`, up to 300 m) |
| Delivered | 50 cm, Float32, **meters**, nodata −9999, EPSG:2263 grid identical to the 2017 pair | same |
| Capture | **12–21 May 2021**, Optech Galaxy T2000, spec 12 pulses/m² (tiles measure 12–27 pts/m² where flight lines overlap) | same flight |
| Accuracy (vendor) | — | non-vegetated 3.8 cm RMSEz (7.5 cm at 95%); vegetated 39 cm at 95th pct, **failed** the 10 cm class |
| CRS of the source | NAD83(2011) / NY Long Island ftUS (EPSG:6539), NAVD88 ftUS via GEOID18 | same |

Caveats:

- **Why the surface is built from classified points only.** The delivered point cloud carries dense mid-air noise in class 1 (unclassified), striped along the flight lines and reaching 45 m above ground; only the higher noise was put in class 18. A highest-return DSM that includes class 1 is unusable (half the cells land more than 5 m above the 2017 surface). Restricting to the classified classes removes it: the result matches the state's own 2 ft DSM to within 0.5 m in 94% of cells (Hunts Point test window), and the 2017 DSM in about two-thirds of land cells (64–67% per district), with the remaining differences being tree growth (median +2.3 to +3.0 m over tree canopy), new and demolished buildings, and leaf state. The price is that **anything EagleView left unclassified is missing**: some cars, cranes, poles, wires, small roof furniture, and occasionally a bridge deck or elevated structure. The Bruckner Expressway, the elevated 6 line and the rail viaducts in these districts are present. Where a 2017 feature is absent, the 2017 DSM is still in the package.
- **Season.** Mid-May 2021 is later than the 3–17 May 2017 flight, but still before full leaf-out for many species. Expect crowns to be slightly fuller than in 2017 and still thinner than a July surface. Canopy extent should be taken from the TNC 2021 layer (section 3), which was mapped from this same lidar plus 2021 NAIP.
- **Classification quality.** NYS warns that the city-supplied classification "has problems", and the vendor's own report shows the vegetated-terrain accuracy test failed. The DTM is where that matters: on land it agrees with the 2017 bare-earth model within 25 cm in 87–92% of cells per district (median difference 0 cm; 95% or better on roads) and the larger discrepancies are construction sites and interpolated areas under buildings. Points of class 1 that are actually ground are lost to the DTM, and a few elevated structures were classified as ground and pulled the terrain up locally: in Qn4 some highway ramps on the western buffer edge appear as 5–8 m ridges, and in Bk5 about 3.6% of railroad cells are more than 5 m above the 2017 terrain. Compare with the 2017 DTM where a terrain value matters.
- **Water has no returns in 2021.** The DSM's water cells are filled with the DTM's interpolated shoreline values so the raster is complete; they are not a measured surface. Mask with `landcover` class 4 if needed.
- **A newer city lidar is still pending.** NYC Local Law 148 of 2023 required a new citywide lidar by 31 July 2025; nothing from it has been published yet (checked October 2026).

**2017 (kept for change detection):** `dsm_2017_50cm_m_*.tif`, `dtm_2017_50cm_m_*.tif`

| | DSM `dsm_2017_50cm_m_*.tif` | DTM `dtm_2017_50cm_m_*.tif` |
|---|---|---|
| Source | NYC 2017 Topobathymetric LiDAR, **Highest Hit** surface model (NYC Open Data `7sc8-jtbz`, file `Highest_Hit.zip`) | NYC 2017 Topobathymetric LiDAR, **bare-earth, hydro-flattened** DEM, NOAA Digital Coast mirror (ID 9307) |
| Native | 1 ft (30.5 cm), Float32, NAVD88 ft | 1 ft (30.5 cm), Float32, NAVD88 ft |
| Delivered | 50 cm, Float32, **meters**, bilinear resample, nodata −9999 | same |
| Capture | 3–17 May 2017, 01:00–06:00, Leica ALS80, QL1 (≥8 pulses/m², measured 10.75 pts/m²) | same flight |
| Accuracy | non-vegetated vertical 0.074 m (95%), vegetated 0.158 m (95th pct) | same |

- The 2017 highest-hit surface includes every return, so it keeps the bridges, wires, cranes and vehicles that the 2021 classified surface drops, and its water is interpolated from shoreline breaklines. Buildings completed after mid-2017 are absent; the `building_footprints` layer carries `construction_year`, `height_roof` and `ground_elevation` for burning new buildings into either DSM.
- The city describes the 2017 flight as "50% leaf-off", so deciduous crowns are thinner and lower than in summer; subtracting the two DSMs over tree canopy mostly measures four years of growth plus the two weeks' difference in leaf state.

### 2. Orthophoto (20 cm, RGB+NIR) and leaf-on reference

`ortho_2024_20cm_rgbnir_*.tif`

- Source: NYS GIS Program Office / NYC OTI **2024 NYC orthoimagery**, 6-inch (15 cm) source, 4-band, full true ortho (building lean removed). Flown **14–24 March 2024**, i.e. **leaf-off**. Bands are **1 Red, 2 Green, 3 Blue, 4 Near-infrared**, 8-bit.
- Delivered at 20 cm by averaging 6-inch pixels (a ~1.3× downsample); nodata 0. The native 6-inch tiles (JPEG2000, about 35 MB each) can be pulled from the borough zips listed in the manifest if you want full resolution.
- NYC has flown every ortho since 2016 in March–April, so there is no leaf-on city imagery. **For leaf-on QC we include `naip_2022_leafon_60cm_rgbnir_*.tif`**: USDA NAIP, flown 19 July and 15 September 2022, 60 cm, 4-band (same band order). It is coarse but it shows summer crowns, and it is close in time to the 2021 lidar behind the canopy layer. The exact acquisition dates of the quarter-quads used are in the `.dates.txt` next to each file.
- The 2024 ortho post-dates the 2021 DSM and canopy by three years; use it to check building footprints and street geometry, not to validate the DSM's trees.

### 3. Tree canopy, tree crowns and tree locations (2021)

`tree_canopy_2021_*.gpkg` (layers `canopy_polygons`, `tree_centroids`, `tree_crown_circles`, `tree_crown_objects`), `landcover_2021_6in_*.tif`, `canopy_change_2017_2021_6in_*.tif`

- Source: **The Nature Conservancy, New York Cities Program**, data developed by the **University of Vermont Spatial Analysis Laboratory** (Zenodo [10.5281/zenodo.14053441](https://doi.org/10.5281/zenodo.14053441), released Dec 2024). Method: object-based image analysis of the 2021 NYS lidar, 2021 NAIP and 2022 NYS orthoimagery, followed by manual correction; overall land-cover accuracy 95.5%, tree canopy 99.1%. Same protocol as the city's 2010 and 2017 canopy maps (MacFaden et al. 2012).
- **This is the canopy-projection layer Or asked for, and it covers private as well as public trees.** `canopy_polygons` is land-cover class 1 vectorised (so edges are 6-inch stair-steps). `tree_crown_objects` are UVM's segmented individual crowns, `tree_crown_circles` the same trees approximated as circles, `tree_centroids` their centers; each carries `Height` (ft, from the 2021 lidar) and `Radius` (ft), so crown height is available without touching the 2017 DSM. Only crowns taller than **8 ft (2.44 m)** and visible from above are mapped; understory trees in overlapping canopy are not separate objects. Rooftop trees (planters, green roofs) are excluded.
- Because the lidar behind it is the same 12–21 May 2021 flight as the DSM/DTM in section 1 and the land-cover classes cover the whole landscape, this layer is the most recent canopy evidence available; the `Height` attribute of the crown objects and the 2021 DSM are mutually consistent.
- `landcover_2021_6in` classes: 1 tree canopy, 2 grass/shrub, 3 bare soil, 4 water, 5 buildings, 6 roads, 7 other impervious, 8 railroads. `canopy_change_2017_2021_6in` classes: 1 no change, 2 gain, 3 loss.
- **License: CC BY-NC-SA 4.0** — academic use is fine, commercial use is not, derivatives must carry the same license, and TNC's metadata (the `.xml` sidecars in the Zenodo record) should accompany any redistribution.

### 4. Tree trunk locations (public trees)

Layer `forestry_tree_points` in `vectors_*.gpkg`

- Source: NYC Parks **Forestry Tree Points** (ForMS 2.0 live inventory, NYC Open Data `hn5i-inap`), the dataset used in Tree Folio. Snapshot date is in the manifest.
- **Filtered to `tpstructure = 'Full'`**, i.e. standing trees with a crown. Retired (removed), stump and shaft records are excluded. Attributes include `dbh` (inches), `genusspecies`, `tpcondition`, `riskrating`, `planteddate`, and `plantingspaceglobalid` to join to the Forestry Planting Spaces dataset.
- Coverage is street trees and park trees in **maintained** park areas; trees in forested natural areas and on private property are not inventoried. For private trees use the TNC `tree_centroids` (section 3).

### 5. Land use, right-of-way and open space

All in `vectors_*.gpkg`, each a separate layer:

| Layer | Source | Use |
|---|---|---|
| `mappluto` | DCP MapPLUTO **26v2** (tax lots) | Land use (`LandUse` 01–11: 1–3 residential, 4 mixed, 5 commercial, 6 industrial, 7 transport/utility, 8 institutions, 9 open space & recreation, 10 parking, 11 vacant), `OwnerType` (C city, M mixed, O other public, P private, X federal/state), `BldgClass`, zoning, floors |
| `planimetric_roadbed`, `planimetric_sidewalk`, `planimetric_median` | NYC Planimetric Database (OTI), updated April 2024 from 2022 imagery | Right-of-way polygons; `sidewalk` and `roadbed` are the layers Or already found |
| `planimetric_public_plazas` | DCP planimetric public plazas (June 2025) | Pedestrian plazas as polygons |
| `lion_streets` | DCP LION street centerlines | Segment the right-of-way; `SegmentID`, `Street`, `StreetWidth_Min/Max`, `RW_TYPE` |
| `parks_properties` | NYC Parks Properties (live) | City-managed parks, playgrounds, greenstreets, malls; `typecategory`, `jurisdiction`, `acres` |
| `dot_pedestrian_plazas` | NYC DOT | DOT plaza program sites |
| `privately_owned_public_spaces` | DCP POPS (points) | Privately owned public plazas/arcades; mostly Manhattan, few in these districts |
| `greenthumb_gardens` | GreenThumb community gardens (polygons) | City-licensed community gardens |
| `building_footprints` | NYC OTI Building Footprints (live, Oct 2026) | Footprints with `height_roof`, `ground_elevation`, `construction_year`, `bin`, `base_bbl` |

- **There is no single "city-managed open public space" layer in NYC**; the usual recipe is the union of `parks_properties` + `dot_pedestrian_plazas` + `planimetric_public_plazas` + `greenthumb_gardens`, with MapPLUTO `LandUse = '09'` or `OwnerType = 'C'` as a cross-check. We ship the parts rather than a pre-merged layer so the definition stays yours.
- Vintages differ: planimetrics are 2022 imagery, MapPLUTO is 2026, footprints are live. Buildings in planimetric `roadbed`/`sidewalk` therefore match the 2024 ortho well but not every 2026 footprint.
- Vector features were selected by intersection with the buffer and kept whole, so large parcels, parks and roads extend past the buffer edge.

### 6. Citywide

Everything here is clipped from citywide sources, so extending to all 59 community districts is a matter of re-running the scripts with more district codes (and disk: roughly 5× the size per district for the ortho alone). The one layer with a cost is the TNC tree-crown geodatabase, which is distributed as a single 2 GB file for the whole city and only needs to be downloaded once.

### Changelog

- **2026-10-21 (v1.1)** — **2021 DSM and DTM added** (`dsm_2021_50cm_m_*`, `dtm_2021_50cm_m_*`), built from the NYC 2021 lidar point cloud that NYS ITS hosts on its FTP but does not list publicly (see section 1 and `docs/reports/` for the vendor reports NYS supplied). The 2017 pair stays in the package. Scripts: `index_las_2021.py`, `fetch_las_2021.sh`, `build_elevation_2021.py`. QC against 2017 (`scripts/qc_elevation_2021.py`, land cells only): DSM within 0.5 m in 67 / 65 / 64% and DTM within 0.25 m in 87 / 92 / 89% of cells for Bx2 / Bk5 / Qn4; median difference 0 m for both. The vectors rebuilt on 2026-10-18 (below) were never uploaded to v1.0-pilot, so v1.1 re-publishes the whole package under one tag.
- **2026-10-18** — `vectors_*.gpkg` rebuilt. The first release paged NYC Open Data without an `$order` clause, which returns rows in arbitrary order per page; `building_footprints` and `forestry_tree_points` (the two layers over 5,000 features) were therefore missing roughly a third of their features and contained duplicates. Paging is now ordered by `:id` and the fetched count is asserted against the server's count. New totals: footprints 5,003 / 28,099 / 21,036 and standing trees 9,894 / 23,820 / 13,577 for Bx2 / Bk5 / Qn4. All other layers were unaffected. Checksums in `manifest.json` updated.
