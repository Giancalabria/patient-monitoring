# Patient Monitoring API Template

## Overview

Plantilla FastAPI para un sistema de monitoreo de pacientes con:

- Ingesta de telemetría (simulada)
- Motor de reglas en tiempo real
- APIs de panel de monitoreo
- Alertas de emergencia

## Run

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `POST /telemetry` - Ingesta de telemetría por paciente
- `GET /patients` - Listado de pacientes y estados
- `GET /patients/{patient_id}/status` - Estado de un paciente
- `GET /alerts` - Listado de alertas generadas
- `GET /rules` - Reglas activas
- `POST /rules/evaluate` - Forzar evaluación de regla
- `POST /emergency` - Emitir evento emergencia (código rojo)
