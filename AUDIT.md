# PAIMANA May 2026 — LandGuard data audit

## What we have
- **Rows:** 1,987
- **Unique projects:** 1,987
- **Rows with a known revised completion date:** 1,635
- **Rows with a usable retrospective schedule-revision label:** 1,635
- **Label = revised later than original:** 1,287
- **Label = revised same/earlier:** 348
- **Rows conservatively eligible for a retrospective baseline:** 1,634

## Important limitation
This single May 2026 snapshot is **not yet a proper future-delay prediction dataset**.

If we use `schedule_revised_later` as the target, we must exclude:
- `revised_date`
- `delay_days`
- `schedule_revised_later` itself
- preferably `revised_cost_crore` in the first baseline because it may reflect a later project revision

A safe first baseline can use:
- `sector_name`
- `line_ministry`
- `original_cost_crore`
- `expenditure_crore`
- `days_to_original_deadline`
- `original_deadline_passed`
- `expenditure_to_original_cost_pct`

But because the May 2026 snapshot occurs after many schedule revisions, this is still retrospective classification, not early prediction.

## Serious next step
Download **every monthly PAIMANA snapshot from July 2025 through May 2026**.

Then create one row per:
`project_code × snapshot_month`

For each project, define a forward target such as:

`will_receive_later_revision_within_180_days`

using only information that was known at the earlier snapshot.

That converts this from a static classification problem into a genuine early-warning dataset.

## Source-quality flags
- Original completion date more than 10 years after May 2026: 3
- Revised date earlier than original date: 63
- Missing expenditure: 277
- Missing revised cost: 918

These rows were flagged rather than silently corrected.
