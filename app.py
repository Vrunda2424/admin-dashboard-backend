import os
import re
from contextlib import contextmanager

import bcrypt
import psycopg2
from flask import Flask, jsonify, request
from werkzeug.security import check_password_hash

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
ROLES = ("Admin", "Editor", "Viewer")
STATUSES = ("Active", "Inactive")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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
    """Create the users table, or upgrade an older one that only had username and password."""
    with cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(120),
                password TEXT NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'Viewer',
                status VARCHAR(20) NOT NULL DEFAULT 'Active',
                registration_date TIMESTAMP NOT NULL DEFAULT NOW()
            );
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'password_hash') THEN
                    ALTER TABLE users RENAME COLUMN password_hash TO password;
                END IF;
                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'created_at') THEN
                    ALTER TABLE users RENAME COLUMN created_at TO registration_date;
                END IF;
            END $$;
            ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(120);
            ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'Viewer';
            ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'Active';
            CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON users (email);
            """
        )


def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(stored, password):
    raw = password.encode()
    if len(raw) > 72:  # bcrypt only reads the first 72 bytes
        return False
    if stored.startswith("$2"):
        return bcrypt.checkpw(raw, stored.encode())
    return check_password_hash(stored, password)  # accounts created before bcrypt was added


def password_problem(password):
    """Same rules as the React forms: 6+ characters, upper, lower, and a special character."""
    if len(password.encode()) > 72:
        return "Password must be 72 characters or fewer."
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


def user_problem(user):
    if len(user["username"]) < 3:
        return "Username must be at least 3 characters."
    if not EMAIL_RE.match(user["email"]):
        return "Enter a valid email address."
    problem = password_problem(user["password"])
    if problem:
        return problem
    if user["role"] not in ROLES:
        return f"Role must be one of: {', '.join(ROLES)}."
    if user["status"] not in STATUSES:
        return f"Status must be one of: {', '.join(STATUSES)}."
    return None


@app.after_request
def add_cors_headers(response):
    # Lets the React app (a different port) call this API from the browser.
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


def iso(value):
    return value.isoformat() + "Z"  # stored in UTC


@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    user = {
        "username": str(data.get("username", "")).strip(),
        "email": str(data.get("email", "")).strip().lower(),
        "password": str(data.get("password", "")),
        "role": data.get("role", "Viewer"),
        "status": data.get("status", "Active"),
    }
    problem = user_problem(user)
    if problem:
        return jsonify(success=False, message=problem), 400

    try:
        with cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, email, password, role, status) VALUES (%s, %s, %s, %s, %s) "
                "RETURNING id, registration_date",
                (user["username"], user["email"], hash_password(user["password"]), user["role"], user["status"]),
            )
            user_id, registered = cur.fetchone()
    except psycopg2.errors.UniqueViolation as exc:
        taken = "Email is already registered." if "email" in (exc.diag.constraint_name or "") else "Username is already taken."
        return jsonify(success=False, message=taken), 409

    created = {"id": user_id, "username": user["username"], "email": user["email"], "role": user["role"],
               "status": user["status"], "registration_date": iso(registered)}
    return jsonify(success=True, message="Account created.", user=created), 201


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    with cursor() as cur:
        cur.execute("SELECT id, username, password, status FROM users WHERE username = %s", (username,))
        row = cur.fetchone()

    if row is None or not verify_password(row[2], password):
        return jsonify(success=False, message="Incorrect username or password."), 401
    if row[3] != "Active":
        return jsonify(success=False, message="This account is inactive. Contact an administrator."), 403
    return jsonify(success=True, message="Login successful.", user={"id": row[0], "username": row[1]}), 200


@app.post("/api/change-password")
def change_password():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    current = str(data.get("current_password", ""))
    new = str(data.get("new_password", ""))

    with cursor() as cur:
        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        if row is None or not verify_password(row[0], current):
            return jsonify(success=False, message="Current password is incorrect."), 401
        problem = password_problem(new)
        if problem:
            return jsonify(success=False, message=problem), 400
        if new == current:
            return jsonify(success=False, message="New password must be different from the current password."), 400
        cur.execute("UPDATE users SET password = %s WHERE username = %s", (hash_password(new), username))
    return jsonify(success=True, message="Password changed."), 200


@app.get("/api/users")
def list_users():
    with cursor() as cur:
        cur.execute("SELECT id, username, email, role, status, registration_date FROM users ORDER BY id")
        rows = cur.fetchall()
    # The password is never sent to the browser.
    users = [
        {"id": r[0], "username": r[1], "email": r[2], "role": r[3], "status": r[4], "registration_date": iso(r[5])}
        for r in rows
    ]
    return jsonify(users), 200


def row_to_user(r):
    return {"id": r[0], "username": r[1], "email": r[2], "role": r[3], "status": r[4], "registration_date": iso(r[5])}


@app.put("/api/users/<int:user_id>")
def update_user(user_id):
    """Change only the role and status of one user. Every other field stays as it is."""
    data = request.get_json(silent=True) or {}
    role, status = data.get("role"), data.get("status")
    if role not in ROLES:
        return jsonify(success=False, message=f"Role must be one of: {', '.join(ROLES)}."), 400
    if status not in STATUSES:
        return jsonify(success=False, message=f"Status must be one of: {', '.join(STATUSES)}."), 400

    with cursor() as cur:
        cur.execute(
            "UPDATE users SET role = %s, status = %s WHERE id = %s "
            "RETURNING id, username, email, role, status, registration_date",
            (role, status, user_id),
        )
        row = cur.fetchone()
    if row is None:
        return jsonify(success=False, message="User not found."), 404
    return jsonify(success=True, message="User updated.", user=row_to_user(row)), 200


@app.delete("/api/users/<int:user_id>")
def delete_user(user_id):
    with cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
        row = cur.fetchone()
    if row is None:
        return jsonify(success=False, message="User not found."), 404
    return jsonify(success=True, message="User deleted."), 200


if __name__ == "__main__":
    init_db()
    # Port 5001: macOS uses port 5000 for AirPlay Receiver.
    app.run(debug=True, port=5001)
