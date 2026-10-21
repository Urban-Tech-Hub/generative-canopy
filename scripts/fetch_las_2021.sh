#!/usr/bin/env bash
# Parallel, resumable download of the NYC 2021 LAS tiles listed in tiles_all.txt
set -u
cd "$(dirname "$0")/../work/las2021"
xargs -P 6 -I{} sh -c 'curl -sS --retry 8 --retry-all-errors --max-time 3600 -C - -o "{}" "ftp://ftp.gis.ny.gov/elevation/LIDAR/NYC_2021/{}" && echo "done {}" || echo "FAIL {}"' < tiles_all.txt
echo "ALL DONE $(ls *.las | wc -l) files"
