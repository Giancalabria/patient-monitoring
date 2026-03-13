---
name: Patient Monitoring Module
overview: Build a full-stack Patient Monitoring module with a Python/FastAPI backend, React frontend, AWS SQS for telemetry ingestion, PostgreSQL for persistence, a rules engine for real-time alerting, and Docker Compose for deployment.
todos:
  - id: project-scaffold
    content: "Scaffold project structure: create directories, docker-compose.yml, Dockerfiles, .env.example, requirements.txt, and Vite+React frontend skeleton"
    status: pending
  - id: database-models
    content: Define SQLAlchemy models (Patient, TelemetryReading, Alert, Rule), set up async DB session, and create Alembic migrations
    status: pending
  - id: sqs-setup
    content: Configure LocalStack SQS in Docker Compose, write SQS client helper (boto3 async) with queue creation on startup
    status: pending
  - id: telemetry-simulator
    content: Build the telemetry simulator service that generates synthetic patient sensor data and publishes to SQS
    status: pending
  - id: sqs-consumer
    content: Build the SQS consumer background worker that polls messages, persists to DB, and forwards to the rules engine
    status: pending
  - id: rules-engine
    content: Implement the rules engine with sliding time-window evaluation and configurable alert thresholds
    status: pending
  - id: alert-service
    content: Implement the emergency alert service that dispatches red-code events to a separate SQS queue
    status: pending
  - id: rest-api
    content: Build REST API endpoints (patients CRUD, telemetry history, alerts list/acknowledge) with FastAPI routers
    status: pending
  - id: websocket-endpoint
    content: Implement WebSocket endpoint for real-time telemetry and alert broadcasting to connected dashboard clients
    status: pending
  - id: frontend-dashboard
    content: "Build React frontend: patient grid with status cards, vitals charts (Recharts), alert panel, and WebSocket integration"
    status: pending
  - id: docker-deploy
    content: Finalize Docker Compose setup, Nginx config for frontend, health checks, and write README with setup instructions
    status: pending
isProject: false
---

# Patient Monitoring Module

## Architecture Overview

```mermaid
flowchart LR
    subgraph sim [Telemetry Simulator]
        SimService["simulator service"]
    end

    subgraph queue [Message Queue]
        SQS["AWS SQS / LocalStack"]
    end

    subgraph backend [Backend - FastAPI]
        Consumer["SQS Consumer Worker"]
        RulesEngine["Rules Engine"]
        API["REST API"]
        WS["WebSocket Server"]
        AlertService["Emergency Alert Service"]
    end

    subgraph data [Data Layer]
        PG["PostgreSQL"]
    end

    subgraph frontend [Frontend - React]
        Dashboard["Monitoring Dashboard"]
    end

    SimService -->|"publish telemetry"| SQS
    SQS -->|"poll messages"| Consumer
    Consumer --> PG
    Consumer --> RulesEngine
    RulesEngine -->|"trigger alert"| AlertService
    RulesEngine -->|"broadcast"| WS
    API -->|"query"| PG
    WS -->|"real-time updates"| Dashboard
    API -->|"REST"| Dashboard
    AlertService -->|"high-priority event"| SQS
```



## Technology Stack


| Layer | Technology |
| ----- | ---------- |


- **Backend Framework**: FastAPI (async, WebSocket support, auto-generated OpenAPI docs)
- **Task/Worker**: Background asyncio tasks consuming SQS
- **Message Queue**: AWS SQS (LocalStack for local development)
- **Database**: PostgreSQL 16 with SQLAlchemy (async) + Alembic for migrations
- **Real-time**: WebSockets via FastAPI for pushing live telemetry and alerts to the dashboard
- **Frontend**: React 18 + TypeScript + Vite
- **UI Library**: Material UI (MUI) for medical-grade dashboard look
- **Charting**: Recharts for vital signs graphs
- **State Management**: Zustand (lightweight) + React Query for server state
- **Deployment**: Docker Compose with 4 services (postgres, localstack, backend, frontend)

## Project Structure

```
dapi2/
  backend/
    app/
      main.py                  # FastAPI app entry point
      config.py                # Settings via pydantic-settings
      models/                  # SQLAlchemy ORM models
        patient.py
        telemetry.py
        alert.py
      schemas/                 # Pydantic request/response schemas
        patient.py
        telemetry.py
        alert.py
      api/                     # REST route handlers
        patients.py
        telemetry.py
        alerts.py
        websocket.py           # WebSocket endpoint
      services/
        sqs_consumer.py        # Background SQS polling worker
        rules_engine.py        # Configurable rule evaluation
        alert_service.py       # Emergency alert dispatching
        simulator.py           # Telemetry data simulator
      db/
        session.py             # Async SQLAlchemy session
        migrations/             # Alembic migrations
    requirements.txt
    Dockerfile
    alembic.ini
  frontend/
    src/
      components/
        Dashboard/             # Main monitoring panel
        PatientCard/           # Individual patient status card
        VitalsChart/           # Real-time vitals chart
        AlertBanner/           # Emergency alert banner
      hooks/
        useWebSocket.ts        # WebSocket connection hook
        usePatients.ts         # React Query hooks
      services/
        api.ts                 # Axios API client
      store/
        alertStore.ts          # Zustand alert state
      types/
        index.ts               # TypeScript interfaces
      App.tsx
      main.tsx
    package.json
    Dockerfile
    vite.config.ts
  docker-compose.yml
  .env.example
  README.md
```

## Core Components Detail

### 1. Telemetry Simulator (`backend/app/services/simulator.py`)

- Generates synthetic sensor data for N configurable patients
- Produces heart rate (60-180 bpm), SpO2 (85-100%), blood pressure, temperature
- Publishes JSON messages to an SQS queue every 1-5 seconds per patient
- Runs as a FastAPI background task (or standalone script via CLI)

### 2. SQS Consumer (`backend/app/services/sqs_consumer.py`)

- Long-polls the SQS telemetry queue in a background asyncio loop
- Deserializes messages, persists readings to PostgreSQL
- Forwards each reading to the Rules Engine for evaluation
- Broadcasts the reading via WebSocket to all connected dashboard clients

### 3. Rules Engine (`backend/app/services/rules_engine.py`)

- Configurable rules stored in a `rules` DB table or a YAML/JSON config
- Example rules:
  - `HR > 120 for 2 minutes` -> generate WARNING alert
  - `SpO2 < 90` -> generate CRITICAL alert (red code)
  - `Temperature > 39.5` -> generate WARNING alert
- Maintains a sliding time window per patient (in-memory with Redis-like TTL dict)
- When a rule triggers, creates an Alert record and invokes the Alert Service

### 4. Emergency Alert Service (`backend/app/services/alert_service.py`)

- Receives triggered alerts from the Rules Engine
- For red-code alerts, publishes a high-priority message to a separate SQS queue (simulating the Hospitalization Module integration)
- Broadcasts alerts via WebSocket to the dashboard in real-time

### 5. REST API Endpoints

- `GET /api/patients` - list all monitored patients
- `GET /api/patients/{id}` - patient detail with latest vitals
- `GET /api/patients/{id}/telemetry` - historical telemetry readings (paginated)
- `GET /api/alerts` - list alerts (filterable by severity, patient, date)
- `POST /api/alerts/{id}/acknowledge` - acknowledge an alert
- `POST /api/patients` - register a new patient for monitoring
- `WS /ws/monitoring` - WebSocket stream for real-time telemetry + alerts

### 6. Frontend Dashboard

- **Header**: Hospital branding, active alert count badge
- **Patient Grid**: Cards showing each patient's current vitals (HR, SpO2, BP, Temp) with color-coded status (green/yellow/red)
- **Detail View**: Click a patient to see historical vitals charts (Recharts line graphs)
- **Alert Panel**: Side panel or top banner showing active alerts sorted by severity, with acknowledge button
- **Real-time**: WebSocket hook keeps all data live without polling

## Database Schema (PostgreSQL)

```mermaid
erDiagram
    Patient {
        uuid id PK
        string name
        string room
        string bed
        string status
        timestamp created_at
    }
    TelemetryReading {
        uuid id PK
        uuid patient_id FK
        float heart_rate
        float spo2
        float systolic_bp
        float diastolic_bp
        float temperature
        timestamp recorded_at
    }
    Alert {
        uuid id PK
        uuid patient_id FK
        string severity
        string rule_name
        string message
        boolean acknowledged
        timestamp triggered_at
        timestamp acknowledged_at
    }
    Rule {
        uuid id PK
        string name
        string metric
        string operator
        float threshold
        int duration_seconds
        string severity
        boolean active
    }
    Patient ||--o{ TelemetryReading : "has many"
    Patient ||--o{ Alert : "has many"
```



## Deployment (Docker Compose)

Four services in `docker-compose.yml`:

- **postgres**: PostgreSQL 16 with a health check, persistent volume
- **localstack**: LocalStack (SQS emulation) for local dev; in production, swap for real AWS SQS via env vars
- **backend**: FastAPI app (uvicorn), depends on postgres + localstack, runs Alembic migrations on startup
- **frontend**: Nginx serving the Vite production build, proxies `/api` and `/ws` to the backend

A `.env.example` file will document all required environment variables (DB URL, SQS queue URL, AWS credentials, etc.).

## Implementation Order

Tasks are ordered by dependency -- each step builds on the previous one.