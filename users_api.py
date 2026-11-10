import re

import psycopg2
from flask import Blueprint, g, jsonify, request

from auth import roles_required
from db import cursor
from passwords import hash_password, password_problem
from roles import MANAGEABLE, ROLES, STATUSES

users_bp = Blueprint("users", __name__)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
COLUMNS = "id, username, email, role, status, registration_date"


def fail(message, status):
    return jsonify(success=False, message=message), status


def row_to_user(r):
    return {"id": r[0], "username": r[1], "email": r[2], "role": r[3], "status": r[4], "registration_date": r[5].isoformat() + "Z"}


def may_manage(actor, target_id, target_role):
    """Nobody manages their own row, and nobody manages a role above what they may assign."""
    return target_id != actor["id"] and target_role in MANAGEABLE[actor["role"]]


@users_bp.get("/api/users")
@roles_required(*MANAGEABLE)
def list_users():
    with cursor() as cur:
        cur.execute(f"SELECT {COLUMNS} FROM users ORDER BY id")
        rows = cur.fetchall()
    return jsonify([row_to_user(r) for r in rows])  # the password is never sent


@users_bp.post("/api/users")
@roles_required(*MANAGEABLE)
def create_user():
    data = request.get_json(silent=True) or {}
    user = {
        "username": str(data.get("username", "")).strip(),
        "email": str(data.get("email", "")).strip().lower(),
        "password": str(data.get("password", "")),
        "role": data.get("role"),
        "status": data.get("status", "Active"),
    }
    if len(user["username"]) < 3:
        return fail("Username must be at least 3 characters.", 400)
    if not EMAIL_RE.match(user["email"]):
        return fail("Enter a valid email address.", 400)
    if password_problem(user["password"]):
        return fail(password_problem(user["password"]), 400)
    if user["role"] not in ROLES:
        return fail("Choose a valid role.", 400)
    if user["status"] not in STATUSES:
        return fail(f"Status must be one of: {', '.join(STATUSES)}.", 400)
    if user["role"] not in MANAGEABLE[g.user["role"]]:
        return fail("You are not allowed to create a user with this role.", 403)

    try:
        with cursor() as cur:
            cur.execute(
                f"INSERT INTO users (username, email, password, role, status) VALUES (%s, %s, %s, %s, %s) RETURNING {COLUMNS}",
                (user["username"], user["email"], hash_password(user["password"]), user["role"], user["status"]),
            )
            created = cur.fetchone()
    except psycopg2.errors.UniqueViolation as exc:
        return fail("Email is already registered." if "email" in (exc.diag.constraint_name or "") else "Username is already taken.", 409)
    return jsonify(success=True, message="User created.", user=row_to_user(created)), 201


def load_target(cur, user_id):
    cur.execute("SELECT id, role FROM users WHERE id = %s", (user_id,))
    return cur.fetchone()


@users_bp.put("/api/users/<int:user_id>")
@roles_required(*MANAGEABLE)
def update_user(user_id):
    """Change only the role and status of one user."""
    data = request.get_json(silent=True) or {}
    role, status = data.get("role"), data.get("status")
    if role not in ROLES:
        return fail("Choose a valid role.", 400)
    if status not in STATUSES:
        return fail(f"Status must be one of: {', '.join(STATUSES)}.", 400)

    with cursor() as cur:
        target = load_target(cur, user_id)
        if target is None:
            return fail("User not found.", 404)
        if not may_manage(g.user, target[0], target[1]):
            return fail("You are not allowed to change this user.", 403)
        if role not in MANAGEABLE[g.user["role"]]:
            return fail("You are not allowed to give a user this role.", 403)
        cur.execute(f"UPDATE users SET role = %s, status = %s WHERE id = %s RETURNING {COLUMNS}", (role, status, user_id))
        row = cur.fetchone()
    return jsonify(success=True, message="User updated.", user=row_to_user(row))


@users_bp.delete("/api/users/<int:user_id>")
@roles_required(*MANAGEABLE)
def delete_user(user_id):
    with cursor() as cur:
        target = load_target(cur, user_id)
        if target is None:
            return fail("User not found.", 404)
        if not may_manage(g.user, target[0], target[1]):
            return fail("You are not allowed to delete this user.", 403)
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    return jsonify(success=True, message="User deleted.")
