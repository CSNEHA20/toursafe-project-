from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_database: str = Field(default="toursafe", alias="MONGODB_DATABASE")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    jwt_secret_key: str = Field(default="dev-secret-change-me", alias="JWT_SECRET")
    jwt_access_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_EXPIRE_MINUTES")
    jwt_refresh_expire_days: int = Field(default=7, alias="JWT_REFRESH_EXPIRE_DAYS")
    cors_origins: list[str] = Field(default=["http://localhost:8081", "http://127.0.0.1:8081"])
    ws_ping_interval_seconds: int = Field(default=30, alias="WS_PING_INTERVAL_SECONDS")
    ws_max_payload_bytes: int = Field(default=65536, alias="WS_MAX_PAYLOAD_BYTES")

    # Telemetry Pipeline Settings
    telemetry_retention_days: int = Field(default=30, alias="TELEMETRY_RETENTION_DAYS")
    telemetry_window_duration_sec: float = Field(default=3.0, alias="TELEMETRY_WINDOW_DURATION_SEC")
    telemetry_window_stride_sec: float = Field(default=1.0, alias="TELEMETRY_WINDOW_STRIDE_SEC")
    telemetry_nominal_frequency_hz: float = Field(default=50.0, alias="TELEMETRY_NOMINAL_FREQUENCY_HZ")
    telemetry_min_completeness_ratio: float = Field(default=0.6, alias="TELEMETRY_MIN_COMPLETENESS_RATIO")
    telemetry_max_time_gap_ms: float = Field(default=250.0, alias="TELEMETRY_MAX_TIME_GAP_MS")
    telemetry_max_queue_depth: int = Field(default=5000, alias="TELEMETRY_MAX_QUEUE_DEPTH")
    telemetry_redis_ttl_seconds: int = Field(default=120, alias="TELEMETRY_REDIS_TTL_SECONDS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()