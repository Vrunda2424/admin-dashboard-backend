from flask import Flask, jsonify, request

from auth import make_token
from db import cursor
from pages import pages_bp
from passwords import hash_password, password_problem, verify_password
from schema import create_page_tables, create_users_table
from users_api import users_bp

app = Flask(__name__)
app.register_blueprint(pages_bp)  # dashboard page data (needs a signed-in user)
app.register_blueprint(users_bp)  # user management (Super Admin and Admin only)

ALLOWED_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


@app.after_request
def add_cors_headers(response):
    # Lets the React app (a different port) call this API from the browser.
    origin = request.headers.get("Origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response


@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    with cursor() as cur:
        cur.execute("SELECT id, username, password, role, status FROM users WHERE username = %s", (username,))
        row = cur.fetchone()

    if row is None or not verify_password(row[2], password):
        return jsonify(success=False, message="Incorrect username or password."), 401
    if row[4] != "Active":
        return jsonify(success=False, message="This account is inactive. Contact an administrator."), 403
    return jsonify(
        success=True,
        message="Login successful.",
        token=make_token(row[0]),
        user={"id": row[0], "username": row[1], "role": row[3]},
    )


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
    return jsonify(success=True, message="Password changed.")


if __name__ == "__main__":
    create_users_table()
    create_page_tables()
    # Port 5001: macOS uses port 5000 for AirPlay Receiver.
    app.run(debug=True, port=5001)
