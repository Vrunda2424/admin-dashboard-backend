import re

import bcrypt
from werkzeug.security import check_password_hash


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
