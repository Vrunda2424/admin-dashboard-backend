import os
from functools import wraps

from flask import g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from db import cursor

# Set SECRET_KEY in the environment for anything beyond local practice.
SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-secret-change-me")
TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60
_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="dashboard-auth")


def make_token(user_id):
    return _serializer.dumps({"uid": user_id})


def current_user():
    """Reads 'Authorization: Bearer <token>'. The role is read from the database every time,
    so a role change or a deactivated account takes effect immediately."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        data = _serializer.loads(header[7:], max_age=TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None
    with cursor() as cur:
        cur.execute("SELECT id, username, role, status FROM users WHERE id = %s", (data["uid"],))
        row = cur.fetchone()
    if row is None or row[3] != "Active":
        return None
    return {"id": row[0], "username": row[1], "role": row[2]}


def require_login():
    """Use as a blueprint's before_request: every route in it needs a signed-in user."""
    if request.method == "OPTIONS":  # the browser's CORS pre-check carries no token
        return None
    user = current_user()
    if user is None:
        return jsonify(success=False, message="Please sign in."), 401
    g.user = user
    return None


def roles_required(*roles):
    """Only the listed roles may call the route: 401 when signed out, 403 for any other role."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify(success=False, message="Please sign in."), 401
            if user["role"] not in roles:
                return jsonify(success=False, message="You do not have permission to do this."), 403
            g.user = user
            return view(*args, **kwargs)
        return wrapper
    return decorator
