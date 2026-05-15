from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from api import telemetry, patients, alerts, rules
from src.services.repository import initialize_default_rules
from src.db.db import init_db

app = FastAPI(
    title="Patient Monitoring API",
    description="Monitoreo de pacientes: telemetría, reglas, dashboard y alertas de emergencia.",
    version="0.1.0",
)

app.include_router(telemetry.router)
app.include_router(patients.router)
app.include_router(alerts.router)
app.include_router(rules.router)


@app.on_event("startup")
def startup_event():
    init_db()
    initialize_default_rules()


@app.get("/health", summary="Health check")
def health_check():
    return {"status": "ok"}
