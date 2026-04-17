# Módulo 9 - Next Steps

## Current State

The core business logic is implemented: telemetry ingestion via REST, rule evaluation engine, patient status tracking, alert generation, and CRUD for rules and alerts. All data is stored in-memory with 10 mock patients seeded from CSV.

---

## Gaps to Address

### 1. Message Queue Integration (Telemetry Ingestion)

**Requirement:** Telemetry data should arrive via message queues ("colas de mensajes"), not just REST.

- [ ] Add an SQS consumer (or equivalent) that polls for sensor readings from a `telemetry-ingest` queue
- [ ] Reuse the existing `ingest_telemetry` logic so both REST and queue paths share the same processing pipeline
- [ ] Define the SNS topic and SQS subscription for telemetry events
- [ ] Add configuration for queue URLs and credentials in `core/config.py`
- [ ] Consider using `aiobotocore` or `boto3` with a background task for async polling

### 2. Event Bus for Emergency Alerts

**Requirement:** Emergency alerts (CODE_RED) must publish a high-priority event to the Internación module (M6).

- [ ] Implement SNS publishing in `POST /alerts/emergency` (replace the `# TODO` in `api/alerts.py`)
- [ ] Define the `monitoring-events` SNS topic and message envelope format:
  ```json
  {
    "event_type": "monitoring.code_red",
    "source": "M9",
    "payload": { ... }
  }
  ```
- [ ] Create SQS subscriptions for M6 (Internación) and M8 (Portal del Paciente)
- [ ] Add retry/dead-letter queue configuration for failed deliveries
- [ ] Add integration tests that verify the event is published with correct payload

### 3. Real-Time Dashboard Support (WebSocket/SSE)

**Requirement:** Nursing dashboard should display patient state in real time.

- [ ] Add a WebSocket endpoint (e.g., `GET /ws/monitoring`) for real-time patient status updates
- [ ] Broadcast telemetry updates and alert events to connected clients when new data arrives
- [ ] Support filtering by ward so nurses only receive updates for their assigned patients
- [ ] Consider Server-Sent Events (SSE) as a simpler alternative if bidirectional communication is not needed
- [ ] Add connection management (heartbeat, reconnection handling)

### 4. Database Persistence

**Requirement:** Implied by production readiness — all in-memory stores need durable storage.

- [ ] Set up PostgreSQL connection (SQLAlchemy + asyncpg or similar)
- [ ] Create database models/tables for:
  - `patients` (demographics, bed assignment)
  - `telemetry_readings` (time-series sensor data)
  - `alerts` (generated alerts with acknowledgement state)
  - `rules` (monitoring rule definitions)
- [ ] Add Alembic migrations
- [ ] Replace in-memory stores in `src/services/repository.py` with DB queries
- [ ] Add connection pooling and health checks

### 5. Authentication & Authorization

**Requirement:** Architecture specifies JWT from M10 Core.

- [ ] Replace the `fake-token` stub in `core/security.py` with real JWT validation
- [ ] Add role-based access control (nurse, doctor, admin)
- [ ] Protect all endpoints with appropriate auth dependencies
- [ ] Integrate with M10 Core identity provider

### 6. API Path Alignment

**Issue:** Architecture doc specifies `/api/v1/monitoring` prefix but routes use bare paths.

- [ ] Add `/api/v1/monitoring` prefix to all route registrations in `app.py`
- [ ] Clean up or remove the unused `api/v1/` alternate router layer
- [ ] Update any documentation or client references

### 7. Infrastructure & Deployment

- [ ] Create `Dockerfile` for containerized deployment
- [ ] Create `docker-compose.yml` for local development (app + PostgreSQL + LocalStack for SNS/SQS)
- [ ] Add environment variable configuration (`.env.example`)
- [ ] Add health check endpoint that verifies DB and queue connectivity
- [ ] Fix README startup command (`app.main:app` → `app.app:app`)

---

## Suggested Priority Order

| Priority | Task | Effort |
|----------|------|--------|
| 1 | Database persistence | High |
| 2 | Emergency alert event publishing (SNS) | Medium |
| 3 | Message queue consumer for telemetry | Medium |
| 4 | WebSocket/SSE for real-time dashboard | Medium |
| 5 | API path alignment | Low |
| 6 | Authentication & authorization | Medium |
| 7 | Infrastructure & deployment | Medium |
