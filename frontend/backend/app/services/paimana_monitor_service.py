from __future__ import annotations

import json
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from app.core.config import settings
from app.ml.build_paimana_panel import DEFAULT_OUTPUT, DEFAULT_RAW_DIR, build_panel
from app.ml.train_paimana import ARTIFACT_DIR, train

SOURCE_URL = "https://ipm.mospi.gov.in/Home/PublicDashboard"
BACKEND_DIR = Path(__file__).resolve().parents[2]
STATE_PATH = BACKEND_DIR / "data" / "paimana_pipeline_state.json"
ARTIFACT_NAMES = [
    "classifier.joblib", "probability_calibrator.joblib", "delay_duration_regressor.joblib",
    "metadata.json", "duration_metadata.json", "model_comparison.json",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _state() -> dict:
    return _load_json(STATE_PATH, {})


def _save_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _model_metadata() -> dict:
    return _load_json(ARTIFACT_DIR / "metadata.json", {})


def _month_from_test_split(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\d{4}-\d{2}", value)
    return match.group(0) if match else None


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; LandGuardAI-SIH2026/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    s.verify = settings.paimana_verify_ssl
    if not settings.paimana_verify_ssl:
        requests.packages.urllib3.disable_warnings()  # public source only; configurable in .env
    return s


def _latest_published_month(html: str) -> str:
    match = re.search(r'lastFreezeDate\s*=\s*"(\d{4}-\d{2})"', html)
    if match:
        return match.group(1)
    soup = BeautifulSoup(html, "lxml")
    text = " ".join(soup.select_one("#refreshDateText").stripped_strings) if soup.select_one("#refreshDateText") else ""
    months = {m.lower(): i for i, m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"], 1)}
    m = re.search(r"as of\s+([A-Za-z]+),\s*(\d{4})", text, re.I)
    if m and m.group(1).lower() in months:
        return f"{m.group(2)}-{months[m.group(1).lower()]:02d}"
    raise RuntimeError("Could not determine the latest PAIMANA published month from the public dashboard.")


def _parse_projects(html: str) -> pd.DataFrame:
    soup = BeautifulSoup(html, "lxml")
    modal = soup.select_one("#projectcount1")
    table = modal.find("table") if modal else None
    if table is None:
        raise RuntimeError("PAIMANA Project Overview table was not found.")
    headers = [" ".join(th.stripped_strings) for th in table.select("thead th")]
    rows = []
    for tr in table.select("tbody tr"):
        cells = [" ".join(td.stripped_strings) for td in tr.find_all("td")]
        if len(cells) == len(headers):
            rows.append(cells)
    if not rows or len(headers) < 10:
        raise RuntimeError("PAIMANA returned no project rows for this reporting month.")
    df = pd.DataFrame(rows, columns=headers)
    df = df.iloc[:, :10]
    df.columns = [
        "sr_no", "sector_name", "line_ministry", "project_code", "project_name",
        "original_cost_crore", "revised_cost_crore", "expenditure_crore",
        "original_end_date", "revised_date",
    ]
    df = df.replace(r"^\s*$", pd.NA, regex=True)
    for col in ("original_cost_crore", "revised_cost_crore", "expenditure_crore"):
        df[col] = pd.to_numeric(df[col].astype("string").str.replace(",", "", regex=False).str.replace("₹", "", regex=False).str.strip(), errors="coerce")
    for col in ("original_end_date", "revised_date"):
        df[col] = pd.to_datetime(df[col], format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    return df


def _download_month(session: requests.Session, month: str) -> Path:
    get = session.get(SOURCE_URL, timeout=settings.paimana_request_timeout_seconds)
    get.raise_for_status()
    soup = BeautifulSoup(get.text, "lxml")
    token = soup.select_one('input[name="__RequestVerificationToken"]')
    if not token or not token.get("value"):
        raise RuntimeError("PAIMANA anti-forgery token was not found.")
    payload = {
        "__RequestVerificationToken": token["value"],
        "SectorId": "", "PROJ_MINISTRY_ID": "", "StateId": "", "CostRange": "", "MonthYear": month,
    }
    response = session.post(SOURCE_URL, data=payload, headers={"Referer": SOURCE_URL}, timeout=settings.paimana_request_timeout_seconds)
    response.raise_for_status()
    df = _parse_projects(response.text)
    DEFAULT_RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_RAW_DIR / f"paimana_dashboard_{month}.csv"
    df.to_csv(path, index=False)
    return path


def _local_months() -> list[str]:
    return sorted(p.stem.rsplit("_", 1)[-1] for p in DEFAULT_RAW_DIR.glob("paimana_dashboard_*.csv"))


def _months_between(start_exclusive: str | None, end_inclusive: str) -> list[str]:
    end = pd.Period(end_inclusive, freq="M")
    start = pd.Period(start_exclusive, freq="M") + 1 if start_exclusive else pd.Period(settings.paimana_min_month, freq="M")
    if start > end:
        return []
    return [str(p) for p in pd.period_range(start, end, freq="M")]


def _quality_passes(incumbent: dict, challenger: dict) -> tuple[bool, str]:
    c = challenger.get("metrics", {})
    i = incumbent.get("metrics", {})
    if c.get("roc_auc", 0) < settings.paimana_min_roc_auc:
        return False, f"challenger ROC-AUC {c.get('roc_auc', 0):.3f} is below the minimum gate"
    if c.get("recall", 0) < settings.paimana_min_recall:
        return False, f"challenger recall {c.get('recall', 0):.3f} is below the minimum gate"
    if incumbent:
        if c.get("f1", 0) < i.get("f1", 0) - settings.paimana_allowed_metric_drop:
            return False, "challenger F1 dropped beyond the allowed tolerance"
        if c.get("roc_auc", 0) < i.get("roc_auc", 0) - settings.paimana_allowed_metric_drop:
            return False, "challenger ROC-AUC dropped beyond the allowed tolerance"
    return True, "quality gates passed"


def _promote(staging: Path) -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACT_NAMES:
        src = staging / name
        if src.exists():
            shutil.copy2(src, ARTIFACT_DIR / name)
    try:
        from app.services import intelligence_service
        intelligence_service.reset_model_cache()
    except Exception:
        pass


def pipeline_status() -> dict:
    state = _state()
    metadata = _model_metadata()
    local = _local_months()
    quality = _load_json(BACKEND_DIR / "data" / "paimana_panel_quality.json", {})
    metrics = metadata.get("metrics", {})
    return {
        "enabled": settings.paimana_auto_monitor_enabled,
        "source": SOURCE_URL,
        "last_check_at": state.get("last_check_at"),
        "last_success_at": state.get("last_success_at"),
        "latest_published_month": state.get("latest_published_month"),
        "latest_downloaded_month": local[-1] if local else None,
        "latest_labelled_month": quality.get("latest_fully_labelled_snapshot"),
        "latest_model_test_month": _month_from_test_split(metadata.get("test_split")),
        "dataset_rows": quality.get("panel_rows"),
        "new_snapshots_last_run": state.get("new_snapshots_last_run", []),
        "retraining_status": state.get("retraining_status", "idle"),
        "model_promotion_status": state.get("model_promotion_status", "not_checked"),
        "current_model_name": metadata.get("model_name"),
        "current_roc_auc": metrics.get("roc_auc"),
        "current_f1": metrics.get("f1"),
        "message": state.get("message"),
    }


def check_and_update() -> dict:
    state = _state()
    state.update({"last_check_at": _now(), "new_snapshots_last_run": [], "retraining_status": "checking", "model_promotion_status": "not_checked"})
    _save_state(state)
    try:
        session = _session()
        landing = session.get(SOURCE_URL, timeout=settings.paimana_request_timeout_seconds)
        landing.raise_for_status()
        published = _latest_published_month(landing.text)
        local = _local_months()
        latest_local = local[-1] if local else None
        missing = _months_between(latest_local, published)
        downloaded = []
        for month in missing:
            _download_month(session, month)
            downloaded.append(month)

        quality = build_panel()
        latest_labelled = quality.get("latest_fully_labelled_snapshot")
        incumbent = _model_metadata()
        incumbent_test = _month_from_test_split(incumbent.get("test_split"))
        should_retrain = bool(
            latest_labelled and (not incumbent_test or latest_labelled > incumbent_test)
            and quality.get("panel_rows", 0) >= settings.paimana_min_labelled_rows
        )

        promotion_status = "not_needed"
        retraining_status = "waiting_for_mature_labels"
        message = "Source is current; waiting for a newer fully-labelled 3-month horizon."
        if should_retrain:
            retraining_status = "challenger_training"
            with tempfile.TemporaryDirectory(prefix="landguard-paimana-") as tmp:
                staging = Path(tmp)
                challenger = train(DEFAULT_OUTPUT, artifact_dir=staging)
                passed, reason = _quality_passes(incumbent, challenger)
                if passed:
                    _promote(staging)
                    promotion_status = "promoted"
                    retraining_status = "completed"
                    message = f"New challenger promoted after temporal validation: {reason}."
                else:
                    promotion_status = "rejected"
                    retraining_status = "completed"
                    message = f"Current model retained: {reason}."
        elif downloaded:
            message = "New source snapshots were ingested. Retraining is deferred until their 3-month outcomes mature."

        state.update({
            "last_success_at": _now(), "latest_published_month": published,
            "new_snapshots_last_run": downloaded, "retraining_status": retraining_status,
            "model_promotion_status": promotion_status, "message": message,
        })
        _save_state(state)
        return pipeline_status()
    except Exception as exc:
        state.update({"retraining_status": "error", "model_promotion_status": "not_checked", "message": f"Pipeline check failed: {exc}"})
        _save_state(state)
        return pipeline_status()
