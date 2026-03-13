from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Patient Monitoring"
    debug: bool = True
    version: str = "0.1.0"


settings = Settings()
