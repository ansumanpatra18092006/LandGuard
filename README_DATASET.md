# LandGuard AI - Real PAIMANA Data Pipeline

This starter pipeline builds a **real-source** project-monitoring dataset from official
MoSPI / PAIMANA Flash Reports.

## Why this source

PAIMANA's public project-monitoring reports contain project code/name, state,
approval/start dates, original and revised completion dates, original/revised cost,
cumulative expenditure and physical progress for central-sector infrastructure
projects.

This is useful for establishing a real project-delay baseline. It is **not by itself
a complete land-acquisition dataset**. Land-acquisition-specific features should later
be enriched from DoLR/LACRRIS and state RFCTLARR/SIA records.

## Install

```powershell
pip install pandas pdfplumber requests python-dateutil
```

## Build

```powershell
python paimana_dataset_builder.py --download
```

If an official server rejects automated download, download the PDFs manually using
`paimana_sources.json` and put them under:

```text
data/raw/paimana/
```

Then run:

```powershell
python paimana_dataset_builder.py
```

Outputs:

- `data/processed/paimana_project_snapshots.csv`
- `data/processed/paimana_latest_projects.csv`
- `data/processed/dataset_quality.json`

## Transparent labels

The script creates two candidate labels:

### `currently_delayed`

`1` only when the monthly report snapshot is later than the project's original target
completion month and reported physical progress is below 100%.

This is a **current schedule-delay state**, not a future prediction label.

### `schedule_revised_later`

`1` when the reported revised completion month is later than the original target
completion month.

This can be useful for analysis, but do not include `revised_end_date` or
`schedule_revision_delay_days` as model inputs when this label is the target, because
that would be target leakage.

## Better future-prediction target

For LandGuard AI's final model, build monthly project snapshots and use a forward
outcome, for example:

`will_be_delayed_180d = 1` if the project ultimately misses its original target by
more than 180 days.

Train only on features that would have been known at the snapshot date.

## Important

Do not claim this dataset predicts land-acquisition delay specifically until you enrich
it with acquisition-stage information such as SIA, notification, award, payment and
possession timelines from DoLR/LACRRIS or state land-acquisition records.
