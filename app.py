import os
import re
from contextlib import contextmanager

import psycopg2
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Defaults match the Docker container from the README.
DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5433"),
    "dbname": os.getenv("DB_NAME", "admin_dashboard"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "dashboard_dev_pw"),
}
ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


def password_problem(password):
    """Same rules as the React forms: 6+ characters, upper, lower, and a special character."""
    missing = []
    if len(password) < 6:
        missing.append("at least 6 characters")
    if not re.search(r"[A-Z]", password):
        missing.append("an uppercase letter")
    if not re.search(r"[a-z]", password):
        missing.append("a lowercase letter")
    if not re.search(r"[^A-Za-z0-9\s]", password):
        missing.append("a special character")
    return f"Password needs {', '.join(missing)}." if missing else None


@contextmanager
def cursor():
    """Open a connection, commit on success, roll back on error, always close."""
    conn = psycopg2.connect(**DB_SETTINGS)
    try:
        with conn, conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def init_db():
    with cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
            """
        )


@app.after_request
def add_cors_headers(response):
    # Lets the React app (a different port) call this API from the browser.
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


def read_credentials():
    data = request.get_json(silent=True) or {}
    return str(data.get("username", "")).strip(), str(data.get("password", ""))


@app.post("/api/register")
def register():
    username, password = read_credentials()
    if len(username) < 3:
        return jsonify(success=False, message="Username must be at least 3 characters."), 400
    problem = password_problem(password)
    if problem:
        return jsonify(success=False, message=problem), 400

    try:
        with cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
                (username, generate_password_hash(password)),  # never store the plain password
            )
            user_id = cur.fetchone()[0]
    except psycopg2.errors.UniqueViolation:
        return jsonify(success=False, message="Username is already taken."), 409
    return jsonify(success=True, message="Account created.", user={"id": user_id, "username": username}), 201


@app.post("/api/login")
def login():
    username, password = read_credentials()
    with cursor() as cur:
        cur.execute("SELECT id, username, password_hash FROM users WHERE username = %s", (username,))
        row = cur.fetchone()

    if row is None or not check_password_hash(row[2], password):
        return jsonify(success=False, message="Incorrect username or password."), 401
    return jsonify(success=True, message="Login successful.", user={"id": row[0], "username": row[1]}), 200


@app.get("/api/users")
def list_users():
    with cursor() as cur:
        cur.execute("SELECT id, username, created_at FROM users ORDER BY id")
        rows = cur.fetchall()
    # The password hash is never sent to the browser. "Z" marks the time as UTC.
    users = [{"id": r[0], "username": r[1], "created_at": r[2].isoformat() + "Z"} for r in rows]
    return jsonify(users), 200


if __name__ == "__main__":
    init_db()
    # Port 5001: macOS uses port 5000 for AirPlay Receiver.
    app.run(debug=True, port=5001)
