from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    PUBLIC_BASE_URL: str = "http://localhost:8000"
    DATABASE_URL: str = "sqlite:///./pontosense.db"
    ESCALATION_TIMEOUT_SECONDS: int = 50
    DEMO_MODE: bool = True

    model_config = {"env_file": ".env"}


settings = Settings()
