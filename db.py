import os
from contextlib import contextmanager

import psycopg2

# Defaults match the Docker container from the README.
DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "admin_dashboard"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "dashboard_dev_pw"),
}


@contextmanager
def cursor():
    """Open a connection, commit on success, roll back on error, always close."""
    conn = psycopg2.connect(**DB_SETTINGS)
    try:
        with conn, conn.cursor() as cur:
            yield cur
    finally:
        conn.close()
