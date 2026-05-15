from pydantic import BaseSettings, AnyUrl
import os

class Settings(BaseSettings):
    app_name: str = "Patient Monitoring"
    debug: bool = True
    version: str = "0.1.0"

    database_url: AnyUrl = os.getenv("DATABASE_URL")

    class Config:
        env_prefix = "PM_"


settings = Settings()
