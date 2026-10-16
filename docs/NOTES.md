### Read this first

- **Everything is in one grid.** All rasters and vectors are in **EPSG:2263** (NAD83 / New York Long Island, US survey feet), the native CRS of every NYC dataset. Raster grids are pixel-aligned to that CRS (`-tap`): the 50 cm products have a pixel of exactly 1.6404 ft, the 20 cm ortho 0.6562 ft. **Elevations are in meters** (NAVD88, EPSG:5703), converted from the city's feet so the DSM, DTM and any nDSM you derive are directly in metric units. Horizontal coordinates stay in feet; reproject everything to EPSG:6539 or UTM 18N if you prefer metric x/y.
- **Each district is clipped to its boundary plus a 300 m buffer** so buildings and trees just outside the district still cast their shadows inward. Rasters are masked to the buffer polygon; vector features are kept whole if they intersect it. The `aoi_buffer300m` and `cd_boundary` layers in each `vectors_*.gpkg` give you the clip extents.
- **The two biggest limitations are age and season.** The surface and terrain models come from the city's May 2017 lidar; the orthophoto is leaf-off; the canopy layer is 2021. The sections below say what that means and how to compensate.

### 1. DSM and DTM (50 cm)

| | DSM `dsm_2017_50cm_m_*.tif` | DTM `dtm_2017_50cm_m_*.tif` |
|---|---|---|
| Source | NYC 2017 Topobathymetric LiDAR, **Highest Hit** surface model (NYC Open Data `7sc8-jtbz`, file `Highest_Hit.zip`) | NYC 2017 Topobathymetric LiDAR, **bare-earth, hydro-flattened** DEM, NOAA Digital Coast mirror (ID 9307) |
| Native | 1 ft (30.5 cm), Float32, NAVD88 ft | 1 ft (30.5 cm), Float32, NAVD88 ft |
| Delivered | 50 cm, Float32, **meters**, bilinear resample, nodata −9999 | same |
| Capture | 3–17 May 2017, 01:00–06:00, Leica ALS80, QL1 (≥8 pulses/m², measured 10.75 pts/m²) | same flight |
| Accuracy | non-vegetated vertical 0.074 m (95%), vegetated 0.158 m (95th pct) | same |

Caveats:

- **Leaf-off / half-leaf.** The city describes the May 2017 flight as "50% leaf-off". Deciduous crowns are thinner and sometimes lower in the highest-hit surface than they would be in July. Expect tree shade to be **under-estimated** by the DSM alone; the 2021 canopy polygons (section 3) are a better footprint of where crowns are, and canopy height can be read from the DSM where a crown exists.
- **Nine years old.** Buildings completed after mid-2017 are absent from the DSM; demolished buildings are still there. The `building_footprints` layer carries `construction_year`, `height_roof` (ft above ground) and `ground_elevation` (ft NAVD88) for every building, so new buildings can be burned into the DSM as flat roofs at `ground_elevation + height_roof` (convert ft→m, ×0.3048). Trees have grown; see the 2017→2021 canopy change raster for where.
- **A newer city lidar exists but is not public.** New York State holds a 2021 NYC lidar collection (listed as "NYC-2021" on the state's coverage map and used by TNC/UVM for the 2021 canopy mapping) that is not on any public download index; request it from NYS ITS Geospatial Services (nysgis@its.ny.gov). NYC Local Law 148 of 2023 also required a new citywide lidar by 31 July 2025; nothing from it has been published yet (checked October 2026). If either becomes available we will regenerate the DSM/DTM.
- **Highest hit means highest return.** Bridges, elevated rail (the 7 line through Corona, the Bruckner Expressway in Hunts Point, the elevated lines at Broadway Junction), overpasses, cranes, wires and the occasional bird are in the DSM. They do cast shade, so this is mostly correct, but thin linear features can look noisy at 50 cm.
- **Water is interpolated.** Both models have elevation values across open water interpolated from shoreline breaklines; the DTM is additionally hydro-flattened. Mask with the `landcover` class 4 (water) if needed.
- **Bathymetry is not included.** The city's package has topobathymetric variants; we used the topographic products only.

### 2. Orthophoto (20 cm, RGB+NIR) and leaf-on reference

`ortho_2024_20cm_rgbnir_*.tif`

- Source: NYS GIS Program Office / NYC OTI **2024 NYC orthoimagery**, 6-inch (15 cm) source, 4-band, full true ortho (building lean removed). Flown **14–24 March 2024**, i.e. **leaf-off**. Bands are **1 Red, 2 Green, 3 Blue, 4 Near-infrared**, 8-bit.
- Delivered at 20 cm by averaging 6-inch pixels (a ~1.3× downsample); nodata 0. The native 6-inch tiles (JPEG2000, about 35 MB each) can be pulled from the borough zips listed in the manifest if you want full resolution.
- NYC has flown every ortho since 2016 in March–April, so there is no leaf-on city imagery. **For leaf-on QC we include `naip_2022_leafon_60cm_rgbnir_*.tif`**: USDA NAIP, flown 19 July and 15 September 2022, 60 cm, 4-band (same band order). It is coarse but it shows summer crowns, and it is close in time to the 2021 lidar behind the canopy layer. The exact acquisition dates of the quarter-quads used are in the `.dates.txt` next to each file.
- The 2024 ortho post-dates the 2017 DSM by seven years and the 2021 canopy by three; use it to check building footprints and street geometry, not to validate the DSM's trees.

### 3. Tree canopy, tree crowns and tree locations (2021)

`tree_canopy_2021_*.gpkg` (layers `canopy_polygons`, `tree_centroids`, `tree_crown_circles`, `tree_crown_objects`), `landcover_2021_6in_*.tif`, `canopy_change_2017_2021_6in_*.tif`

- Source: **The Nature Conservancy, New York Cities Program**, data developed by the **University of Vermont Spatial Analysis Laboratory** (Zenodo [10.5281/zenodo.14053441](https://doi.org/10.5281/zenodo.14053441), released Dec 2024). Method: object-based image analysis of the 2021 NYS lidar, 2021 NAIP and 2022 NYS orthoimagery, followed by manual correction; overall land-cover accuracy 95.5%, tree canopy 99.1%. Same protocol as the city's 2010 and 2017 canopy maps (MacFaden et al. 2012).
- **This is the canopy-projection layer Or asked for, and it covers private as well as public trees.** `canopy_polygons` is land-cover class 1 vectorised (so edges are 6-inch stair-steps). `tree_crown_objects` are UVM's segmented individual crowns, `tree_crown_circles` the same trees approximated as circles, `tree_centroids` their centers. Only crowns taller than **8 ft (2.44 m)** and visible from above are mapped; understory trees in overlapping canopy are not separate objects. Rooftop trees (planters, green roofs) are excluded.
- Because the lidar behind it is 2021 and the land-cover classes cover the whole landscape, this layer is the most recent canopy evidence available and should be preferred over anything derived from the 2017 DSM alone. We do not yet know the season of the 2021 lidar flight; TNC (michael.treglia@tnc.org) can confirm.
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
