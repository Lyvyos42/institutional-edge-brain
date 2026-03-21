from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url:          str = "sqlite+aiosqlite:///./ieb.db"
    jwt_secret:            str = "change-me-in-production"
    jwt_algorithm:         str = "HS256"
    access_token_minutes:  int = 15
    refresh_token_days:    int = 30
    environment:           str = "development"
    resend_api_key:        str = ""
    frontend_url:          str = "http://localhost:3000"
    from_email:            str = "noreply@quantneuraledge.com"
    free_daily_limit:      int = 10
    google_client_id:      str = ""
    admin_secret:          str = ""
    # Supabase — set SUPABASE_URL + SUPABASE_JWT_SECRET in Render env vars
    supabase_url:          str = ""   # e.g. https://xxxx.supabase.co
    supabase_jwt_secret:   str = ""   # optional legacy HS256 secret

    # kept for backward compat
    @property
    def jwt_expire_minutes(self) -> int:
        return self.access_token_minutes

    class Config:
        env_file = ".env"


settings = Settings()
