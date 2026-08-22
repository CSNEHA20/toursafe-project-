import os
import sys
from typing import List, Optional
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    # Application & Environment Identification
    app_name: str = Field(default="TourSafe Backend", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    build_sha: str = Field(default="unknown", alias="BUILD_SHA")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    debug: bool = Field(default=False, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Database Configuration (MongoDB)
    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_database: str = Field(default="toursafe", alias="MONGODB_DATABASE")
    mongodb_max_pool_size: int = Field(default=100, alias="MONGODB_MAX_POOL_SIZE")
    mongodb_min_pool_size: int = Field(default=10, alias="MONGODB_MIN_POOL_SIZE")
    mongodb_timeout_ms: int = Field(default=5000, alias="MONGODB_TIMEOUT_MS")
    mongodb_tls: bool = Field(default=False, alias="MONGODB_TLS")

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_max_connections: int = Field(default=50, alias="REDIS_MAX_CONNECTIONS")
    redis_socket_timeout: float = Field(default=0.5, alias="REDIS_SOCKET_TIMEOUT")

    # JWT & Authentication Security
    jwt_secret_key: str = Field(default="toursafe-default-secret-key-32bytes-min-change-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_EXPIRE_MINUTES")
    jwt_refresh_expire_days: int = Field(default=7, alias="JWT_REFRESH_EXPIRE_DAYS")
    jwt_issuer: str = Field(default="toursafe-auth-service", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="toursafe-client-applications", alias="JWT_AUDIENCE")

    # CORS & Gateway Security
    cors_origins: list[str] = Field(default=["http://localhost:8081", "http://127.0.0.1:8081"])
    ws_ping_interval_seconds: int = Field(default=30, alias="WS_PING_INTERVAL_SECONDS")
    ws_max_payload_bytes: int = Field(default=65536, alias="WS_MAX_PAYLOAD_BYTES")
    max_request_body_bytes: int = Field(default=52428800, alias="MAX_REQUEST_BODY_BYTES") # 50MB (KYC/Files)

    # Telemetry Pipeline Settings
    telemetry_retention_days: int = Field(default=30, alias="TELEMETRY_RETENTION_DAYS")
    telemetry_window_duration_sec: float = Field(default=3.0, alias="TELEMETRY_WINDOW_DURATION_SEC")
    telemetry_window_stride_sec: float = Field(default=1.0, alias="TELEMETRY_WINDOW_STRIDE_SEC")
    telemetry_nominal_frequency_hz: float = Field(default=50.0, alias="TELEMETRY_NOMINAL_FREQUENCY_HZ")
    telemetry_min_completeness_ratio: float = Field(default=0.6, alias="TELEMETRY_MIN_COMPLETENESS_RATIO")
    telemetry_max_time_gap_ms: float = Field(default=250.0, alias="TELEMETRY_MAX_TIME_GAP_MS")
    telemetry_max_queue_depth: int = Field(default=5000, alias="TELEMETRY_MAX_QUEUE_DEPTH")
    telemetry_redis_ttl_seconds: int = Field(default=120, alias="TELEMETRY_REDIS_TTL_SECONDS")

    # ML Pipeline Settings
    ml_model_version: str = Field(default="v1.0.0", alias="ML_MODEL_VERSION")
    ml_artifacts_dir: str = Field(default="app/ml/artifacts", alias="ML_ARTIFACTS_DIR")
    ml_window_samples: int = Field(default=150, alias="ML_WINDOW_SAMPLES")
    ml_feature_count: int = Field(default=8, alias="ML_FEATURE_COUNT")

    # Copilot & AI Intelligence Settings
    copilot_llm_provider: str = Field(default="gemini", alias="COPILOT_LLM_PROVIDER")
    copilot_model: str = Field(default="gemini-2.0-flash", alias="COPILOT_MODEL")
    copilot_temperature: float = Field(default=0.1, alias="COPILOT_TEMPERATURE")
    copilot_max_tokens: int = Field(default=2048, alias="COPILOT_MAX_TOKENS")
    copilot_timeout_seconds: float = Field(default=30.0, alias="COPILOT_TIMEOUT_SECONDS")
    copilot_max_tool_calls_per_turn: int = Field(default=8, alias="COPILOT_MAX_TOOL_CALLS_PER_TURN")
    copilot_action_token_ttl_seconds: int = Field(default=300, alias="COPILOT_ACTION_TOKEN_TTL_SECONDS")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    bedrock_region: str = Field(default="us-east-1", alias="BEDROCK_REGION")

    # Storage & Object Storage Configuration
    storage_provider: str = Field(default="local", alias="STORAGE_PROVIDER")
    storage_bucket_kyc: str = Field(default="toursafe-kyc-vault-private", alias="STORAGE_BUCKET_KYC")
    storage_bucket_backups: str = Field(default="toursafe-backups-dr", alias="STORAGE_BUCKET_BACKUPS")
    storage_kms_key_id: str = Field(default="", alias="STORAGE_KMS_KEY_ID")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        """
        Enforce critical security parameters if running in production mode.
        Fails fast with descriptive error messages.
        """
        if self.environment.lower() in ("production", "prod"):
            # 1. Reject default or weak JWT secrets
            if (
                "default-secret" in self.jwt_secret_key
                or len(self.jwt_secret_key) < 32
                or self.jwt_secret_key == "change-this-to-a-secure-random-string"
            ):
                raise ValueError(
                    "CRITICAL PRODUCTION CONFIGURATION ERROR: JWT_SECRET must be at least 32 characters "
                    "and cannot use default placeholder keys in production."
                )

            # 2. Reject Wildcard CORS in production
            if "*" in self.cors_origins:
                raise ValueError(
                    "CRITICAL PRODUCTION CONFIGURATION ERROR: Wildcard '*' CORS is strictly prohibited "
                    "in production when handling authenticated tourist safety sessions."
                )

            # 3. Disallow debug mode
            if self.debug:
                raise ValueError(
                    "CRITICAL PRODUCTION CONFIGURATION ERROR: DEBUG mode cannot be enabled in production."
                )
        return self


settings = Settings()