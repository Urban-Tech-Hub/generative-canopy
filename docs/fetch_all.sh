#!/usr/bin/env bash
# Download the whole Generative Canopy package (~6.77 GB) into ./generative-canopy-data
# and verify SHA-256 checksums against manifest.json. Resumable: rerun to continue.
set -euo pipefail
mkdir -p generative-canopy-data && cd generative-canopy-data
curl -sSL -o manifest.json "https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/manifest.json"
while read -r u; do
  [ -n "$u" ] && curl -L -O -C - --retry 5 --retry-all-errors "$u"
done <<'URLS'
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/canopy_change_2017_2021_6in_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dsm_2017_50cm_m_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dsm_2021_50cm_m_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dtm_2017_50cm_m_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dtm_2021_50cm_m_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/landcover_2021_6in_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/naip_2022_leafon_60cm_rgbnir_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/ortho_2024_20cm_rgbnir_202.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/tree_canopy_2021_202.gpkg
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/vectors_202.gpkg
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/canopy_change_2017_2021_6in_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dsm_2017_50cm_m_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dsm_2021_50cm_m_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dtm_2017_50cm_m_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dtm_2021_50cm_m_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/landcover_2021_6in_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/naip_2022_leafon_60cm_rgbnir_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/ortho_2024_20cm_rgbnir_305.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/tree_canopy_2021_305.gpkg
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/vectors_305.gpkg
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/canopy_change_2017_2021_6in_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dsm_2017_50cm_m_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dsm_2021_50cm_m_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dtm_2017_50cm_m_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/dtm_2021_50cm_m_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/landcover_2021_6in_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/naip_2022_leafon_60cm_rgbnir_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/ortho_2024_20cm_rgbnir_404.tif
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/tree_canopy_2021_404.gpkg
https://github.com/Urban-Tech-Hub/generative-canopy/releases/download/v1.1/vectors_404.gpkg
URLS
python3 - <<'PY'
import hashlib, json
bad = 0
for f in json.load(open("manifest.json"))["files"]:
    h = hashlib.sha256(open(f["file"], "rb").read()).hexdigest()
    ok = h == f["sha256"]; bad += not ok
    print(("OK  " if ok else "FAIL"), f["file"])
raise SystemExit(bad)
PY

