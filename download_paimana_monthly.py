#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path
import pandas as pd

MONTHS = pd.period_range("2025-07", "2026-05", freq="M").astype(str).tolist()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--extractor", default="paimana_dashboard_extract.py")
    p.add_argument("--insecure", action="store_true")
    args = p.parse_args()

    out_dir = Path("data/raw/paimana/monthly")
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = []
    for month in MONTHS:
        out = out_dir / f"paimana_dashboard_{month}.csv"
        if out.exists():
            print(f"[skip] {month}: {out}")
            continue

        cmd = [
            sys.executable,
            args.extractor,
            "--month", month,
            "--output", str(out),
        ]
        if args.insecure:
            cmd.append("--insecure")

        print(f"[fetch] {month}")
        result = subprocess.run(cmd)
        if result.returncode != 0:
            failures.append(month)

    print()
    if failures:
        print("Failed months:", ", ".join(failures))
        return 2

    print("All monthly snapshots downloaded.")
    print("Next: build the longitudinal LandGuard training panel.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
