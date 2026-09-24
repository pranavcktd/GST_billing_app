from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Railway exposes DATABASE_URL as postgresql://user:pass@host:port/db
    database_url: str = "sqlite:///./dev.db"
    jwt_secret: str = "dev-only-secret-change-me-in-production-0000"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:3000"

    cloudinary_url: str | None = None  # cloudinary://<api_key>:<api_secret>@<cloud_name>
    cloudinary_folder: str = "gst-billing"

    # e-mail for backups (any SMTP provider: Gmail app password, SendGrid, Brevo, SES...)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        # Use the psycopg (v3) driver for plain postgres URLs.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
