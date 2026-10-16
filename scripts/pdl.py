"""Parallel HTTP range downloader for hosts that throttle single connections (Zenodo).

Usage: uv run python scripts/pdl.py URL OUT [--conns 24]
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests


def fetch_range(url: str, start: int, end: int, part: Path) -> None:
    have = part.stat().st_size if part.exists() else 0
    want = end - start + 1
    while have < want:
        try:
            with requests.get(
                url,
                headers={"Range": f"bytes={start + have}-{end}"},
                stream=True,
                timeout=120,
            ) as r:
                r.raise_for_status()
                with part.open("ab") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        except Exception as e:  # noqa: BLE001 - retry any transport error
            print(f"  retry {part.name}: {e}", file=sys.stderr, flush=True)
            time.sleep(5)
        have = part.stat().st_size if part.exists() else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out", type=Path)
    ap.add_argument("--conns", type=int, default=24)
    a = ap.parse_args()
    # Some hosts (Socrata) do not answer HEAD; a one-byte ranged GET returns the size.
    with requests.get(
        a.url, headers={"Range": "bytes=0-0"}, stream=True, timeout=120
    ) as probe:
        probe.raise_for_status()
        size = int(probe.headers["Content-Range"].split("/")[-1])
    if a.out.exists() and a.out.stat().st_size == size:
        print(f"{a.out} already complete")
        return
    parts_dir = a.out.with_suffix(a.out.suffix + ".parts")
    parts_dir.mkdir(parents=True, exist_ok=True)
    chunk = -(-size // a.conns)
    ranges = [(i * chunk, min((i + 1) * chunk, size) - 1) for i in range(a.conns)]
    t0 = time.time()
    with ThreadPoolExecutor(a.conns) as ex:
        list(
            ex.map(
                lambda r: fetch_range(
                    a.url, r[0], r[1], parts_dir / f"{ranges.index(r):03d}"
                ),
                ranges,
            )
        )
    with a.out.open("wb") as f:
        for i in range(a.conns):
            f.write((parts_dir / f"{i:03d}").read_bytes())
    got = a.out.stat().st_size
    assert got == size, f"size mismatch {got} != {size}"
    for p in parts_dir.iterdir():
        p.unlink()
    parts_dir.rmdir()
    print(
        f"{a.out.name}: {size / 1e9:.2f} GB in {time.time() - t0:.0f}s ({size / 1e6 / (time.time() - t0):.1f} MB/s)"
    )


if __name__ == "__main__":
    main()
