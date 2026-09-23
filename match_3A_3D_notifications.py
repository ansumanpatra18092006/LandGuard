#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd


def clean(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def normalize_project_id(series: pd.Series) -> pd.Series:
    return (
        series.astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )


def normalize_notification(value) -> str:
    """
    Normalize Gazette/notification numbers so forms such as:

        1419
        1419E
        1419 (E)
        1419-E
        1419 - E

    become comparable.
    """
    value = clean(value).upper()

    if not value:
        return ""

    value = value.replace("S.NO.", "")
    value = value.replace("S.NO", "")
    value = value.replace("NOTIFICATION", "")
    value = value.replace("NOTIFI", "")

    # Remove spaces / punctuation but preserve alphanumerics.
    value = re.sub(r"[^A-Z0-9]", "", value)

    return value


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--notifications",
        default="bhoomirashi_notifications.csv",
    )

    parser.add_argument(
        "--projects",
        default="bhoomirashi_projects.csv",
    )

    parser.add_argument(
        "--output",
        default="bhoomirashi_notification_pairs_clean.csv",
    )

    parser.add_argument(
        "--rejected-output",
        default="bhoomirashi_notification_pairs_rejected.csv",
    )

    parser.add_argument(
        "--max-days",
        type=int,
        default=1095,
        help=(
            "Maximum allowed chronology-match gap. "
            "Default 1095 days (3 years). "
            "Longer unmatched cases are retained separately."
        ),
    )

    args = parser.parse_args()

    npath = Path(args.notifications)
    ppath = Path(args.projects)

    if not npath.exists():
        raise SystemExit(
            f"Missing notifications file: {npath}"
        )

    if not ppath.exists():
        raise SystemExit(
            f"Missing projects file: {ppath}"
        )

    n = pd.read_csv(
        npath,
        low_memory=False,
    )

    p = pd.read_csv(
        ppath,
        low_memory=False,
    )

    # ---------------------------------------------------------
    # Normalize
    # ---------------------------------------------------------

    n["project_id"] = normalize_project_id(
        n["project_id"]
    )

    p["project_id"] = normalize_project_id(
        p["project_id"]
    )

    n["stage"] = (
        n["stage"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    n["publish_date"] = pd.to_datetime(
        n["publish_date"],
        errors="coerce",
    )

    n["notification_number"] = (
        n["notification_number"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    n["notification_normalized"] = (
        n["notification_number"]
        .apply(normalize_notification)
    )

    # ---------------------------------------------------------
    # Keep only usable 3A / 3D records
    # ---------------------------------------------------------

    n = n[
        n["stage"].isin(
            ["3A", "3D"]
        )
        & n["publish_date"].notna()
    ].copy()

    before = len(n)

    # ---------------------------------------------------------
    # Deduplicate source notification rows
    #
    # Key:
    # project + stage + date + normalized notification number
    #
    # ---------------------------------------------------------

    n = (
        n.sort_values(
            [
                "project_id",
                "stage",
                "publish_date",
                "notification_normalized",
            ]
        )
        .drop_duplicates(
            subset=[
                "project_id",
                "stage",
                "publish_date",
                "notification_normalized",
            ],
            keep="first",
        )
        .reset_index(drop=True)
    )

    after = len(n)

    print("=" * 70)
    print("BHOOMI RASHI CLEAN CHRONOLOGICAL MATCHER")
    print("=" * 70)

    print(
        f"Usable notification rows before dedupe : {before}"
    )

    print(
        f"Usable notification rows after dedupe  : {after}"
    )

    print(
        f"Duplicate source rows removed           : {before-after}"
    )

    print()

    print("Stages after dedupe:")

    print(
        n["stage"].value_counts()
    )

    # ---------------------------------------------------------
    # Matching
    # ---------------------------------------------------------

    accepted = []
    rejected = []

    groups = list(
        n.groupby(
            "project_id",
            sort=False,
        )
    )

    for position, (
        project_id,
        g,
    ) in enumerate(
        groups,
        start=1,
    ):

        three_a = (
            g[g["stage"] == "3A"]
            .sort_values(
                [
                    "publish_date",
                    "notification_normalized",
                ]
            )
            .copy()
        )

        three_d = (
            g[g["stage"] == "3D"]
            .sort_values(
                [
                    "publish_date",
                    "notification_normalized",
                ]
            )
            .copy()
        )

        if three_a.empty or three_d.empty:
            continue

        used_d = set()

        for a_idx, a in three_a.iterrows():

            a_date = a["publish_date"]

            candidates = three_d[
                (three_d["publish_date"] >= a_date)
                & (~three_d.index.isin(used_d))
            ].copy()

            if candidates.empty:
                continue

            # Closest subsequent unused 3D.
            candidates["gap"] = (
                candidates["publish_date"]
                - a_date
            ).dt.days

            candidates = candidates.sort_values(
                [
                    "gap",
                    "publish_date",
                ]
            )

            d_idx = candidates.index[0]
            d = candidates.loc[d_idx]

            days = int(d["gap"])

            result = {
                "project_id":
                    project_id,

                "three_A_date":
                    a_date.date().isoformat(),

                "three_A_notification":
                    clean(
                        a["notification_number"]
                    ),

                "three_A_notification_normalized":
                    clean(
                        a["notification_normalized"]
                    ),

                "three_D_date":
                    d["publish_date"]
                    .date()
                    .isoformat(),

                "three_D_notification":
                    clean(
                        d["notification_number"]
                    ),

                "three_D_notification_normalized":
                    clean(
                        d["notification_normalized"]
                    ),

                "days_3A_to_3D":
                    days,

                "delay_over_365d":
                    int(days > 365),

                "match_method":
                    "deduped_nearest_subsequent_3D",

                "geography_verified":
                    False,

                "research_label":
                    True,
            }

            # -------------------------------------------------
            # Conservative chronology-quality gate
            # -------------------------------------------------

            if days > args.max_days:

                result["rejection_reason"] = (
                    f"gap_over_{args.max_days}_days"
                )

                rejected.append(
                    result
                )

                # IMPORTANT:
                # Do not consume this 3D.
                # Another later 3A may be a better match.
                continue

            used_d.add(
                d_idx
            )

            accepted.append(
                result
            )

        if (
            position % 50 == 0
            or position == len(groups)
        ):
            print(
                f"[{position}/{len(groups)}] "
                f"accepted={len(accepted)} "
                f"rejected={len(rejected)}"
            )

    # ---------------------------------------------------------
    # DataFrames
    # ---------------------------------------------------------

    pairs = pd.DataFrame(
        accepted
    )

    rejected_df = pd.DataFrame(
        rejected
    )

    # ---------------------------------------------------------
    # Project metadata
    # ---------------------------------------------------------

    p = (
        p.drop_duplicates(
            subset=["project_id"],
            keep="first",
        )
    )

    if not pairs.empty:

        pairs = pairs.merge(
            p,
            on="project_id",
            how="left",
        )

    if not rejected_df.empty:

        rejected_df = rejected_df.merge(
            p,
            on="project_id",
            how="left",
        )

    # ---------------------------------------------------------
    # Derived project feature
    # ---------------------------------------------------------

    if (
        not pairs.empty
        and {
            "land_required_ha",
            "land_available_ha",
        }.issubset(pairs.columns)
    ):

        pairs[
            "land_required_ha"
        ] = pd.to_numeric(
            pairs["land_required_ha"],
            errors="coerce",
        )

        pairs[
            "land_available_ha"
        ] = pd.to_numeric(
            pairs["land_available_ha"],
            errors="coerce",
        )

        denominator = (
            pairs["land_required_ha"]
            .replace(
                0,
                np.nan,
            )
        )

        pairs[
            "land_available_ratio"
        ] = (
            pairs[
                "land_available_ha"
            ]
            / denominator
        )

    # ---------------------------------------------------------
    # Final duplicate guard
    # ---------------------------------------------------------

    if not pairs.empty:

        final_before = len(
            pairs
        )

        pairs = (
            pairs.drop_duplicates(
                subset=[
                    "project_id",
                    "three_A_date",
                    "three_A_notification_normalized",
                    "three_D_date",
                    "three_D_notification_normalized",
                ],
                keep="first",
            )
            .reset_index(
                drop=True
            )
        )

        final_removed = (
            final_before
            - len(pairs)
        )

    else:
        final_removed = 0

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    pairs.to_csv(
        args.output,
        index=False,
    )

    rejected_df.to_csv(
        args.rejected_output,
        index=False,
    )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print()

    print("=" * 70)
    print("MATCHING COMPLETE")
    print("=" * 70)

    print(
        f"Accepted pairs        : {len(pairs)}"
    )

    print(
        f"Rejected long gaps    : {len(rejected_df)}"
    )

    print(
        f"Final duplicates gone : {final_removed}"
    )

    if not pairs.empty:

        print(
            f"Projects represented  : "
            f"{pairs['project_id'].nunique()}"
        )

        print()

        print(
            "Class distribution:"
        )

        print(
            pairs[
                "delay_over_365d"
            ]
            .value_counts()
            .sort_index()
        )

        print()

        print(
            "Duration statistics:"
        )

        print(
            pairs[
                "days_3A_to_3D"
            ].describe()
        )

        print()

        print(
            "Gap buckets:"
        )

        days = (
            pairs[
                "days_3A_to_3D"
            ]
        )

        print(
            "<=365     :",
            int(
                (days <= 365).sum()
            ),
        )

        print(
            "366-730   :",
            int(
                (
                    (days > 365)
                    & (days <= 730)
                ).sum()
            ),
        )

        print(
            "731-1095  :",
            int(
                (
                    (days > 730)
                    & (days <= 1095)
                ).sum()
            ),
        )

    print()

    print(
        f"Accepted dataset : "
        f"{Path(args.output).resolve()}"
    )

    print(
        f"Rejected review  : "
        f"{Path(args.rejected_output).resolve()}"
    )

    print()

    print(
        "NOTE: Accepted rows remain chronology-based "
        "research pairs, not geography-verified legal matches."
    )

    print("=" * 70)


if __name__ == "__main__":
    main()