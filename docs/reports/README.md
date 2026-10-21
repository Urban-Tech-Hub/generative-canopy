# Source reports

Vendor reports for the datasets behind the package. These are the only documentation
New York State holds for the 2021 NYC lidar; the city did not supply formal metadata.

| File | What it is |
|---|---|
| `65220909_Eagleview_NYC_Mapping_Report_EV.pdf` | EagleView-Surdex JV, *Lidar Mapping Report, Eagleview NYC Project* (Sept 2021). Flight dates (12–21 May 2021), sensor (Optech Galaxy T2000, 12 pts/m² spec), CRS (NAD83(2011) / NY Long Island ftUS, NAVD88 GEOID18 ftUS), LAS 1.4 PDRF 6 classification scheme, control and checkpoint accuracy (NVA RMSEz 3.8 cm; VVA 95th pct 39 cm, failed spec). Also on the state FTP next to the LAS tiles. |
| `Eagleview_NYC_Final_Control_Report.pdf` | EagleView, *Final Control Report* for the same project: the surveyed ground control / checkpoint network used in the accuracy tests above. Supplied by NYS ITS. |

Both were sent by Jeffrey Langella (NYS ITS Geospatial Data Services, Elevation Program Manager,
Jeffrey.Langella@its.ny.gov) on 21 Oct 2026 with the FTP locations below. The state hosts the
data but left it out of its standard download index because there is almost no metadata, it is
not part of the USGS National Map, and the point classification is known to have problems.

- DTM (2 ft, per borough): `ftp://ftp.gis.ny.gov/elevation/DEM/NYC_2021/`
- DSM (2 ft, per borough): `ftp://ftp.gis.ny.gov/elevation/DEM/NYC_2021_DSM/`
- LAS tiles (1,740 × 2,500 ft, 700 GB) + tile index shapefile: `ftp://ftp.gis.ny.gov/elevation/LIDAR/NYC_2021/`
