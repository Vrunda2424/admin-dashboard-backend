import re

import psycopg2
from flask import Blueprint, g, jsonify, request

from auth import require_login
from db import cursor

pages_bp = Blueprint("pages", __name__)
pages_bp.before_request(require_login)  # every page endpoint needs a signed-in user

RANGES = ("7d", "30d", "3m", "year")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
BANKING = {
    "internet-banking": {
        "dashboard": "internet_banking_dashboard",
        "users": "internet_banking_users",
        "name": "Internet Banking",
        "logs": "user_logs_internet_banking",
        "columns": [("customer_id", "Customer ID"), ("name", "Name"), ("account_type", "Account type"), ("last_login", "Last login"), ("status", "Status")],
    },
    "mobile-banking": {
        "dashboard": "mobile_banking_dashboard",
        "users": "mobile_banking_users",
        "name": "Mobile Banking",
        "logs": "user_logs_mobile_banking",
        "columns": [("user_id", "User ID"), ("name", "Name"), ("device", "Device"), ("app_version", "App version"), ("status", "Status")],
    },
}


def fail(message, status):
    return jsonify(success=False, message=message), status


def selected_range(cur):
    """Reads ?range=... and returns (key, label), or (None, error response)."""
    key = request.args.get("range", "year")
    if key not in RANGES:
        return None, fail(f"Range must be one of: {', '.join(RANGES)}.", 400)
    cur.execute("SELECT label FROM date_ranges WHERE range_key = %s", (key,))
    row = cur.fetchone()
    if row is None:
        return None, fail("No data found. Run python seed.py once to fill the database.", 503)
    return (key, row[0]), None


@pages_bp.get("/api/overview")
def overview():
    with cursor() as cur:
        chosen, error = selected_range(cur)
        if error:
            return error
        key, label = chosen
        cur.execute("SELECT total_users, active_users, inactive_users, new_registrations FROM overview_stats WHERE range_key = %s", (key,))
        total, active, inactive, new = cur.fetchone()
        cur.execute("SELECT label, registrations, cumulative_users FROM monthly_registrations WHERE range_key = %s ORDER BY sort_order", (key,))
        monthly = cur.fetchall()
        cur.execute("SELECT name, item_value FROM user_distribution WHERE range_key = %s ORDER BY name", (key,))
        distribution = cur.fetchall()
        cur.execute("SELECT user_id, name, email, status, registered_at FROM recent_registrations WHERE range_key = %s ORDER BY rank_no", (key,))
        recent = cur.fetchall()
    return jsonify(
        range=key,
        label=label,
        summary={"total": total, "active": active, "inactive": inactive, "newThisMonth": new},
        monthlyRegistrations=[{"month": m[0], "registrations": m[1]} for m in monthly],
        userGrowth=[{"month": m[0], "users": m[2]} for m in monthly],
        statusBreakdown=[{"name": d[0], "value": d[1]} for d in distribution],
        recentUsers=[{"id": r[0], "name": r[1], "email": r[2], "status": r[3], "registeredAt": r[4].isoformat()} for r in recent],
    )


@pages_bp.get("/api/analytics")
def analytics():
    with cursor() as cur:
        chosen, error = selected_range(cur)
        if error:
            return error
        key, label = chosen
        cur.execute("SELECT average_per_month, peak_label, peak_value, growth_rate, active_rate FROM analytics_data WHERE range_key = %s", (key,))
        average, peak_label, peak_value, growth, active_rate = cur.fetchone()
        cur.execute("SELECT label, active_count, inactive_count FROM analytics_trend WHERE range_key = %s ORDER BY sort_order", (key,))
        trend = cur.fetchall()
        cur.execute("SELECT role, item_value FROM analytics_roles WHERE range_key = %s ORDER BY sort_order", (key,))
        roles = cur.fetchall()
    return jsonify(
        range=key,
        label=label,
        analytics={
            "averagePerMonth": f"{float(average):.1f}",
            "peak": {"month": peak_label, "registrations": peak_value},
            "growthRate": growth,
            "activeRate": active_rate,
        },
        registrationsByStatus=[{"month": t[0], "Active": t[1], "Inactive": t[2]} for t in trend],
        roleDistribution=[{"name": r[0], "value": r[1]} for r in roles],
    )


@pages_bp.get("/api/users-page")
def users_page():
    with cursor() as cur:
        cur.execute("SELECT id, name, email, role, status, registered_at FROM users_page_data ORDER BY id")
        rows = cur.fetchall()
    return jsonify(users=[
        {"id": r[0], "name": r[1], "email": r[2], "role": r[3], "status": r[4], "registeredAt": r[5].isoformat()} for r in rows
    ])


def dashboard_view(table):
    def view():
        with cursor() as cur:
            cur.execute(f"SELECT section, label, item_value, display_value FROM {table} ORDER BY section, sort_order")
            rows = cur.fetchall()
        if not rows:
            return fail("No data found. Run python seed.py once to fill the database.", 503)
        meta = {label: text for section, label, _, text in rows if section == "meta"}
        points = lambda section: [{"label": l, "value": int(v)} for s, l, v, _ in rows if s == section]
        return jsonify(
            name=meta["name"],
            subtitle=meta["subtitle"],
            cards=[{"label": l, "value": text} for s, l, _, text in rows if s == "card"],
            trend={"title": meta["trend_title"], "type": meta["trend_type"], "seriesName": meta["trend_series"], "data": points("trend")},
            split={"title": meta["split_title"], "donut": meta["split_donut"] == "true",
                   "data": [{"name": l, "value": int(v)} for s, l, v, _ in rows if s == "split"]},
            bar={"title": meta["bar_title"], "seriesName": meta["bar_series"], "data": points("bar")},
        )
    return view


def users_view(table, name, columns):
    def view():
        names = [c[0] for c in columns]
        with cursor() as cur:
            cur.execute(f"SELECT id, {', '.join(names)} FROM {table} ORDER BY id")
            rows = cur.fetchall()
        return jsonify(
            name=name,
            columns=[{"key": key, "label": label} for key, label in columns],
            users=[dict(zip(["id"] + names, r)) for r in rows],
        )
    return view


LOG_SUMMARY = ["id", "username", "action", "ip_address", "device", "browser", "timestamp", "status"]
LOG_DETAIL = LOG_SUMMARY + ["os", "location", "session_id", "details"]


def log_to_dict(columns, row):
    item = dict(zip(columns, row))
    item["timestamp"] = item["timestamp"].isoformat()
    return item


def logs_list_view(table, name, title=None):
    def view():
        with cursor() as cur:
            cur.execute(f"SELECT {', '.join(LOG_SUMMARY)} FROM {table} ORDER BY timestamp DESC, id DESC")
            rows = cur.fetchall()
        return jsonify(name=name, title=title or f"{name} User Logs", logs=[log_to_dict(LOG_SUMMARY, r) for r in rows])
    return view


def log_detail_view(table, extra=()):
    columns = LOG_DETAIL + list(extra)  # extra: columns only this table has

    def view(log_id):
        with cursor() as cur:
            cur.execute(f"SELECT {', '.join(columns)} FROM {table} WHERE id = %s", (log_id,))
            row = cur.fetchone()
        if row is None:
            return fail("Log entry not found.", 404)
        return jsonify(log=log_to_dict(columns, row))
    return view


# Table names come from the fixed BANKING dictionary above, never from the request.
for slug, cfg in BANKING.items():
    pages_bp.add_url_rule(f"/api/{slug}/dashboard", f"{slug}-dashboard", dashboard_view(cfg["dashboard"]))
    pages_bp.add_url_rule(f"/api/{slug}/users", f"{slug}-users", users_view(cfg["users"], cfg["name"], cfg["columns"]))
    pages_bp.add_url_rule(f"/api/{slug}/user-logs", f"{slug}-logs", logs_list_view(cfg["logs"], cfg["name"]))
    pages_bp.add_url_rule(f"/api/{slug}/user-logs/<int:log_id>", f"{slug}-log-detail", log_detail_view(cfg["logs"]))


FACE_USER_COLUMNS = [
    ("user_id", "User ID", None), ("username", "Username", None), ("name", "Name", None), ("email", "Email", None),
    ("mobile_number", "Mobile Number", None), ("registration_date", "Registration Date", "datetime"), ("status", "Status", None),
]


@pages_bp.get("/api/mobile-banking/face-users")
def face_users():
    names = [c[0] for c in FACE_USER_COLUMNS]
    with cursor() as cur:
        cur.execute(f"SELECT id, {', '.join(names)} FROM face_users ORDER BY id")
        rows = cur.fetchall()
    users = [dict(zip(["id"] + names, r)) for r in rows]
    for u in users:
        u["registration_date"] = u["registration_date"].isoformat()
    return jsonify(
        name="Face Users",
        columns=[{"key": k, "label": label, **({"type": kind} if kind else {})} for k, label, kind in FACE_USER_COLUMNS],
        users=users,
    )


pages_bp.add_url_rule("/api/mobile-banking/face-logs", "face-logs", logs_list_view("face_logs", "Mobile Banking", "Face Logs"))
pages_bp.add_url_rule("/api/mobile-banking/face-logs/<int:log_id>", "face-log-detail", log_detail_view("face_logs", ("match_score", "liveness")))


def profile_from_row(row):
    username, email, role, full_name, phone = row
    return {"username": username, "name": full_name or username, "email": email or "", "phone": phone or "", "role": role}


@pages_bp.get("/api/settings")
def get_settings():
    username = g.user["username"]  # always the signed-in user, never a name sent in the request
    with cursor() as cur:
        cur.execute(
            "SELECT u.username, u.email, u.role, p.full_name, p.phone FROM users u "
            "LEFT JOIN user_profiles p ON p.username = u.username WHERE u.username = %s",
            (username,),
        )
        row = cur.fetchone()
    if row is None:
        return fail("User not found.", 404)
    return jsonify(profile=profile_from_row(row))


@pages_bp.put("/api/settings")
def save_settings():
    data = request.get_json(silent=True) or {}
    username = g.user["username"]
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    phone = str(data.get("phone", "")).strip()
    if len(name) < 3:
        return fail("Name must be at least 3 characters.", 400)
    if not EMAIL_RE.match(email):
        return fail("Enter a valid email address.", 400)
    if not re.fullmatch(r"\d{10}", phone):
        return fail("Phone number must be exactly 10 digits.", 400)

    try:
        with cursor() as cur:
            cur.execute("UPDATE users SET email = %s WHERE username = %s RETURNING role", (email, username))
            row = cur.fetchone()
            if row is None:
                return fail("User not found.", 404)
            cur.execute(
                "INSERT INTO user_profiles (username, full_name, phone) VALUES (%s, %s, %s) "
                "ON CONFLICT (username) DO UPDATE SET full_name = EXCLUDED.full_name, phone = EXCLUDED.phone",
                (username, name, phone),
            )
    except psycopg2.errors.UniqueViolation:
        return fail("Email is already registered.", 409)
    return jsonify(success=True, message="Profile updated.",
                   profile={"username": username, "name": name, "email": email, "phone": phone, "role": row[0]})
