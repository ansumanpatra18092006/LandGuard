from pathlib import Path
from urllib.parse import urlparse
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'landguard.db').as_posix()}"
    frontend_origin: str = "http://127.0.0.1:5173"
    public_app_url: str = "http://127.0.0.1:5173"
    supabase_url: str = ""
    supabase_service_role_key: SecretStr = SecretStr("")
    brevo_api_key: SecretStr = SecretStr("")
    brevo_sender_email: str = ""
    brevo_sender_name: str = "LandGuard AI"
    session_minutes: int = Field(default=120, ge=5, le=1440)
    compensation_threshold_pct: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    possession_threshold_pct: float = Field(default=50, ge=0, le=100, allow_inf_nan=False)
    slow_response_days: int = Field(default=30, ge=0)
    paimana_auto_monitor_enabled: bool = True
    paimana_check_interval_hours: int = Field(default=6, ge=1, le=168)
    paimana_startup_delay_seconds: int = Field(default=60, ge=0, le=3600)
    paimana_verify_ssl: bool = False
    paimana_request_timeout_seconds: int = Field(default=120, ge=10, le=600)
    paimana_min_month: str = "2025-07"
    paimana_min_labelled_rows: int = Field(default=1000, ge=100)
    paimana_min_roc_auc: float = Field(default=0.75, ge=0.5, le=1.0)
    paimana_min_recall: float = Field(default=0.70, ge=0.0, le=1.0)
    paimana_allowed_metric_drop: float = Field(default=0.03, ge=0.0, le=0.2)
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    @model_validator(mode="after")
    def validate_urls(self):
        for value in (self.public_app_url, self.frontend_origin):
            parsed = urlparse(value)
            if not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
                raise ValueError("Application URLs must be origins without paths or credentials")
            if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")):
                raise ValueError("HTTPS is required outside localhost")
        return self

    @property
    def cookie_secure(self):
        return self.public_app_url.startswith("https://")

    @property
    def allowed_origins(self):
        return list({self.frontend_origin.rstrip("/"), self.public_app_url.rstrip("/")})

settings = Settings()
