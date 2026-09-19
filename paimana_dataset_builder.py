#!/usr/bin/env python3
"""
Build a real PAIMANA/MoSPI project-monitoring dataset from official Flash Report PDFs.

The script is intentionally conservative:
- preserves source month and source file
- never invents missing values
- derives only transparent schedule labels
- keeps rows even when some optional fields are missing

Usage:
  pip install pandas pdfplumber requests python-dateutil
  python paimana_dataset_builder.py --download
  python paimana_dataset_builder.py --raw-dir data/raw/paimana --out data/processed

If MoSPI blocks automated downloads, download the official PDFs manually from the
URLs in paimana_sources.json and place them in --raw-dir. The parser will still work.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

try:
    import pdfplumber
except ImportError:
    raise SystemExit("Install pdfplumber: pip install pdfplumber")

try:
    import requests
except ImportError:
    requests = None


PROJECT_CODE_RE = re.compile(r"\(?\b(\d{6})\b\)?")
LEGACY_CODE_RE = re.compile(r"\(?([A-Z]\d{8,})\)?")
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
MONTH_RE = re.compile(r"(?P<m>\d{1,2})/(?P<y>\d{4})")


def clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\xa0", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def split_lines(value: Any) -> list[str]:
    return [x.strip(" ()") for x in clean(value).splitlines() if x.strip(" ()")]


def parse_num(value: Any) -> float | None:
    text = clean(value).replace(",", "")
    if text in {"", "-", "NA", "N/A"}:
        return None
    m = NUMBER_RE.search(text)
    return float(m.group()) if m else None


def parse_month(value: str) -> pd.Timestamp | None:
    if not value or value in {"-", "NA", "N/A"}:
        return None
    m = MONTH_RE.search(value)
    if m:
        return pd.Timestamp(year=int(m.group("y")), month=int(m.group("m")), day=1)
    for fmt in ("%d/%m/%Y", "%m/%Y", "%d-%m-%Y"):
        try:
            return pd.Timestamp(datetime.strptime(value, fmt))
        except ValueError:
            pass
    return None


def parse_date_pair(value: Any) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    lines = split_lines(value)
    first = parse_month(lines[0]) if lines else None
    second = parse_month(lines[1]) if len(lines) > 1 else None
    return first, second


def parse_cost_pair(value: Any) -> tuple[float | None, float | None]:
    lines = split_lines(value)
    first = parse_num(lines[0]) if lines else None
    second = parse_num(lines[1]) if len(lines) > 1 else None
    return first, second


def parse_project_cell(value: Any) -> tuple[str, str | None, str | None, str | None]:
    lines = split_lines(value)
    if not lines:
        return "", None, None, None

    project_code = None
    legacy = None
    code_idx = None

    for i in range(len(lines) - 1, -1, -1):
        m = PROJECT_CODE_RE.search(lines[i])
        if m:
            project_code = m.group(1)
            code_idx = i
            break

    for line in lines:
        m = LEGACY_CODE_RE.search(line)
        if m:
            legacy = m.group(1)
            break

    if code_idx is None:
        # Section headers/totals are not project rows.
        return clean(value), None, None, legacy

    prior = [x for x in lines[:code_idx] if not LEGACY_CODE_RE.search(x)]
    agency = prior[-1] if len(prior) >= 2 else None
    name_lines = prior[:-1] if agency else prior
    name = " ".join(name_lines).strip()
    return name, agency, project_code, legacy


def report_date(report_month: str) -> pd.Timestamp:
    y, m = map(int, report_month.split("-"))
    # Month-end snapshot is a transparent approximation for the monthly report.
    return pd.Timestamp(year=y, month=m, day=1) + pd.offsets.MonthEnd(0)


def normalize_header(row: list[Any]) -> list[str]:
    return [re.sub(r"\s+", " ", clean(x)).lower() for x in row]


def find_col(headers: list[str], *needles: str) -> int | None:
    for i, h in enumerate(headers):
        if all(n.lower() in h for n in needles):
            return i
    return None


def is_project_table(headers: list[str]) -> bool:
    joined = " | ".join(headers)
    return "project name" in joined and ("original/target" in joined or "original end date" in joined)


def extract_tables(pdf_path: Path) -> Iterable[list[list[Any]]]:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Primary strategy: visible ruled/structured tables.
            tables = page.extract_tables({
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
                "intersection_tolerance": 5,
                "snap_tolerance": 4,
            })
            # Fallback for pages where table borders are weak.
            if not tables:
                tables = page.extract_tables({
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "text_tolerance": 3,
                })
            for table in tables or []:
                if table and len(table) >= 2:
                    yield table


def parse_ongoing_table(table: list[list[Any]], month: str, source_file: str) -> list[dict[str, Any]]:
    headers = normalize_header(table[0])
    if not is_project_table(headers):
        return []

    p_col = find_col(headers, "project name")
    state_col = find_col(headers, "state")
    approval_col = find_col(headers, "approval")
    schedule_col = next((i for i,h in enumerate(headers) if "original/target" in h), None)
    cost_col = next((i for i,h in enumerate(headers) if "original cost" in h), None)
    exp_col = next((i for i,h in enumerate(headers) if "expenditure" in h), None)
    progress_col = next((i for i,h in enumerate(headers) if "physical progress" in h), None)

    if p_col is None or state_col is None or schedule_col is None:
        return []

    out = []
    snap = report_date(month)

    for row in table[1:]:
        if not row or len(row) <= max(p_col, state_col, schedule_col):
            continue

        name, agency, project_code, legacy = parse_project_cell(row[p_col])
        if not project_code:
            continue

        approval, start = parse_date_pair(row[approval_col]) if approval_col is not None and approval_col < len(row) else (None, None)
        original_end, revised_end = parse_date_pair(row[schedule_col])
        original_cost, revised_cost = parse_cost_pair(row[cost_col]) if cost_col is not None and cost_col < len(row) else (None, None)
        expenditure = parse_num(row[exp_col]) if exp_col is not None and exp_col < len(row) else None
        progress = parse_num(row[progress_col]) if progress_col is not None and progress_col < len(row) else None

        schedule_revision_delay_days = None
        schedule_revised_later = None
        if original_end is not None and revised_end is not None:
            schedule_revision_delay_days = int((revised_end - original_end).days)
            schedule_revised_later = int(schedule_revision_delay_days > 0)

        currently_delayed = None
        if original_end is not None and progress is not None:
            currently_delayed = int(snap > original_end and progress < 100)

        elapsed_since_start_days = int((snap - start).days) if start is not None else None
        time_to_original_end_days = int((original_end - snap).days) if original_end is not None else None
        cost_overrun_pct = None
        if original_cost not in (None, 0) and revised_cost is not None:
            cost_overrun_pct = (revised_cost - original_cost) / original_cost * 100
        expenditure_to_original_cost_pct = None
        if original_cost not in (None, 0) and expenditure is not None:
            expenditure_to_original_cost_pct = expenditure / original_cost * 100

        out.append({
            "report_month": month,
            "snapshot_date": snap.date().isoformat(),
            "project_code": project_code,
            "legacy_code": legacy,
            "project_name": name,
            "agency": agency,
            "state": clean(row[state_col]),
            "approval_date": approval.date().isoformat() if approval is not None else None,
            "start_date": start.date().isoformat() if start is not None else None,
            "original_end_date": original_end.date().isoformat() if original_end is not None else None,
            "revised_end_date": revised_end.date().isoformat() if revised_end is not None else None,
            "original_cost_crore": original_cost,
            "revised_cost_crore": revised_cost,
            "cumulative_expenditure_crore": expenditure,
            "physical_progress_pct": progress,
            "elapsed_since_start_days": elapsed_since_start_days,
            "time_to_original_end_days": time_to_original_end_days,
            "cost_overrun_pct": cost_overrun_pct,
            "expenditure_to_original_cost_pct": expenditure_to_original_cost_pct,
            "schedule_revision_delay_days": schedule_revision_delay_days,
            "schedule_revised_later": schedule_revised_later,
            "currently_delayed": currently_delayed,
            "source_file": source_file,
            "source_type": "PAIMANA_MOSPI_FLASH_REPORT",
        })
    return out


def parse_pdf(pdf_path: Path, month: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in extract_tables(pdf_path):
        rows.extend(parse_ongoing_table(table, month, pdf_path.name))
    # Deduplicate within report by project code.
    dedup = {}
    for row in rows:
        dedup[row["project_code"]] = row
    return list(dedup.values())


def download_sources(sources: list[dict[str, str]], raw_dir: Path) -> None:
    if requests is None:
        raise SystemExit("Install requests: pip install requests")
    raw_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LandGuardAI-AcademicPrototype/1.0; +SIH2026)"
    }
    for src in sources:
        out = raw_dir / f"FlashReport_{src['month']}.pdf"
        if out.exists():
            print(f"[skip] {out.name}")
            continue
        print(f"[download] {src['month']} -> {src['url']}")
        try:
            r = requests.get(src["url"], headers=headers, timeout=90, allow_redirects=True)
            r.raise_for_status()
            if "pdf" not in r.headers.get("content-type", "").lower() and not r.content.startswith(b"%PDF"):
                raise RuntimeError(f"Response is not a PDF ({r.headers.get('content-type')})")
            out.write_bytes(r.content)
        except Exception as exc:
            print(f"[warning] could not download {src['month']}: {exc}", file=sys.stderr)
            print("          Download manually from paimana_sources.json and place it in the raw directory.", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default=str(Path(__file__).with_name("paimana_sources.json")))
    ap.add_argument("--raw-dir", default="data/raw/paimana")
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()

    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.download:
        download_sources(sources, raw_dir)

    all_rows: list[dict[str, Any]] = []
    parsed_sources = []

    for src in sources:
        candidates = [
            raw_dir / f"FlashReport_{src['month']}.pdf",
            raw_dir / Path(src["url"].split("path=")[-1]).name,
            raw_dir / Path(src["url"]).name,
        ]
        pdf = next((p for p in candidates if p.exists()), None)
        if pdf is None:
            continue
        print(f"[parse] {src['month']} {pdf.name}")
        rows = parse_pdf(pdf, src["month"])
        print(f"        {len(rows)} project rows")
        all_rows.extend(rows)
        parsed_sources.append({"month": src["month"], "file": pdf.name, "rows": len(rows)})

    if not all_rows:
        print("No project rows were parsed.")
        print("Download one or more official PAIMANA Flash Report PDFs into:", raw_dir)
        return 2

    df = pd.DataFrame(all_rows)
    df = df.sort_values(["project_code", "report_month"]).reset_index(drop=True)

    # Longitudinal fields: changes versus the previous observed month for the same project.
    for col in ["physical_progress_pct", "cumulative_expenditure_crore"]:
        df[f"{col}_change"] = df.groupby("project_code")[col].diff()

    # Do not silently treat unknown labels as negatives.
    # Training code should filter to non-null target rows explicitly.
    snapshots_path = out_dir / "paimana_project_snapshots.csv"
    df.to_csv(snapshots_path, index=False)

    latest = (
        df.sort_values(["project_code", "report_month"])
          .groupby("project_code", as_index=False)
          .tail(1)
          .reset_index(drop=True)
    )
    latest.to_csv(out_dir / "paimana_latest_projects.csv", index=False)

    quality = {
        "rows": int(len(df)),
        "unique_projects": int(df["project_code"].nunique()),
        "months": sorted(df["report_month"].dropna().unique().tolist()),
        "parsed_sources": parsed_sources,
        "non_null_currently_delayed": int(df["currently_delayed"].notna().sum()),
        "non_null_schedule_revision_label": int(df["schedule_revised_later"].notna().sum()),
        "warning": (
            "currently_delayed is a transparent snapshot label: report month is after the "
            "original target date while physical progress is below 100. "
            "schedule_revised_later is based on revised vs original target dates. "
            "Neither should be presented as a validated land-acquisition-delay target."
        ),
    }
    (out_dir / "dataset_quality.json").write_text(json.dumps(quality, indent=2), encoding="utf-8")

    print(f"\nWrote {snapshots_path}")
    print(f"Unique projects: {quality['unique_projects']}")
    print("Review dataset_quality.json before training.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
