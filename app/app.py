from fastapi import FastAPI

from api import alerts, patients, rules, telemetry

app = FastAPI(
    title="Health Grid — Módulo 9: Monitoreo de Pacientes",
    description=(
        "API de monitoreo de pacientes en tiempo real.\n\n"
        "## Funcionalidades\n\n"
        "- **Ingesta de Telemetría**: Recepción de datos de sensores (frecuencia cardíaca, SpO2, presión arterial).\n"
        "- **Motor de Reglas**: Evaluación en tiempo real de los datos recibidos contra reglas configurables.\n"
        "- **Panel de Monitoreo**: Dashboard para enfermería con el estado de los pacientes.\n"
        "- **Alertas de Emergencia**: Envío de eventos de alta prioridad al Módulo de Internación (M6).\n\n"
        "## Integración con otros módulos\n\n"
        "- **M6 (Internación)**: Consume eventos `monitoring.code_red` vía SNS/SQS.\n"
        "- **M8 (Portal del Paciente)**: Consume eventos de alerta y consulta el dashboard.\n"
        "- **M10 (Core)**: Provee autenticación JWT para todos los endpoints.\n"
    ),
    version="0.1.0",
    contact={"name": "Grupo M9"},
)

app.include_router(telemetry.router)
app.include_router(patients.router)
app.include_router(alerts.router)
app.include_router(rules.router)


@app.get("/health", summary="Health check", tags=["system"])
def health_check():
    return {"status": "ok"}
