import psycopg2
from psycopg2.extras import RealDictCursor

from src.core.config import settings

_connection = None
_db_available = None


def get_db_connection():
    global _connection, _db_available
    if _db_available is False:
        raise psycopg2.OperationalError("Database unavailable")

    if settings.database_url is None:
        _db_available = False
        raise psycopg2.OperationalError("DATABASE_URL is not set")

    if _connection is None:
        try:
            _connection = psycopg2.connect(str(settings.database_url), cursor_factory=RealDictCursor)
            _connection.autocommit = True
            _db_available = True
        except psycopg2.OperationalError:
            _db_available = False
            raise
    return _connection


def is_db_available() -> bool:
    global _db_available
    if _db_available is None:
        try:
            get_db_connection()
            _db_available = True
        except psycopg2.OperationalError:
            _db_available = False
    return _db_available


def init_db():
    if not is_db_available():
        print("WARNING: PostgreSQL not available, running in in-memory fallback mode")
        return

    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                expression TEXT NOT NULL,
                severity TEXT NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                last_seen TIMESTAMPTZ NOT NULL,
                heart_rate INT NOT NULL,
                spo2 DOUBLE PRECISION NOT NULL,
                status TEXT NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_history (
                id SERIAL PRIMARY KEY,
                patient_id TEXT NOT NULL,
                timestamp TIMESTAMPTZ NOT NULL,
                heart_rate INT NOT NULL,
                spo2 DOUBLE PRECISION NOT NULL,
                systolic_bp INT,
                diastolic_bp INT,
                device_type TEXT,
                metadata JSONB,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                observed_at TIMESTAMPTZ NOT NULL,
                rule TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                tags TEXT[],
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
            );
            """
        )
