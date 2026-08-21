from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="")

    mongodb_uri: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URI")
    mongodb_database: str = Field(default="toursafe", alias="MONGODB_DATABASE")
    jwt_secret_key: str = Field(default="dev-secret-change-me", alias="JWT_SECRET")
    jwt_access_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_EXPIRE_MINUTES")
    jwt_refresh_expire_days: int = Field(default=7, alias="JWT_REFRESH_EXPIRE_DAYS")
    cors_origins: list[str] = Field(default=["http://localhost:8081", "http://127.0.0.1:8081"])

    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


settings = Settings()