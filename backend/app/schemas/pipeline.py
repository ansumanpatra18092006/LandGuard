from pydantic import BaseModel, Field


class PipelineStatus(BaseModel):
    enabled: bool
    source: str
    last_check_at: str | None = None
    last_success_at: str | None = None
    latest_published_month: str | None = None
    latest_downloaded_month: str | None = None
    latest_labelled_month: str | None = None
    latest_model_test_month: str | None = None
    dataset_rows: int | None = None
    new_snapshots_last_run: list[str] = Field(default_factory=list)
    retraining_status: str = "idle"
    model_promotion_status: str = "not_checked"
    current_model_name: str | None = None
    current_roc_auc: float | None = None
    current_f1: float | None = None
    message: str | None = None


class PipelineRunResult(PipelineStatus):
    checked_now: bool = True
