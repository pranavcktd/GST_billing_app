from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def to_sqlalchemy_url(url: str) -> str:
    """Use the psycopg (v3) driver for plain postgres URLs (Railway gives postgresql://...)."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "development" enables local conveniences (simulated subscription payments). Set "production" when live.
    app_env: str = "development"
    # comma-separated emails that get Super Admin (platform owner) access when they sign in
    superadmin_emails: str = ""
    # public address of the web app, used in e-mailed links (reset password, invoice links)
    app_url: str | None = None

    # Railway exposes DATABASE_URL as postgresql://user:pass@host:port/db
    database_url: str = "sqlite:///./dev.db"
    test_database_url: str | None = None  # pytest uses this database (wiped on every test)
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

    # subscriptions (Razorpay dashboard -> Settings -> API keys / Webhooks)
    razorpay_key_id: str | None = None
    razorpay_key_secret: str | None = None
    razorpay_webhook_secret: str | None = None

    # e-invoice / e-way bill: "sandbox" issues test IRNs locally; "gsp" calls your GSP's API
    einvoice_provider: str = "sandbox"
    gsp_base_url: str | None = None
    gsp_client_id: str | None = None
    gsp_client_secret: str | None = None

    @property
    def superadmins(self) -> set[str]:
        return {e.strip().lower() for e in self.superadmin_emails.split(",") if e.strip()}

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() != "production"

    @property
    def sqlalchemy_url(self) -> str:
        return to_sqlalchemy_url(self.database_url)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
