from typing import Optional
from pydantic import AnyUrl
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    app_name: str = "Patient Monitoring"
    debug: bool = True
    version: str = "0.1.0"

    database_url: Optional[AnyUrl] = None

    model_config = {
        "env_prefix": "PM_",
    }


settings = Settings()
