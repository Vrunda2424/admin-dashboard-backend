"""Fills the page tables with the dummy data that used to be hardcoded in React.
Run it once:  python seed.py   (it is safe to run again, it replaces the old rows)."""
import math
from datetime import date, timedelta

from db import cursor
from passwords import hash_password
from schema import create_page_tables, create_users_table

FIRST = ["Asha", "Ravi", "Meera", "Kiran", "Anil", "Sneha", "Rohan", "Divya", "Arjun", "Pooja", "Vikram", "Neha"]
LAST = ["Sharma", "Reddy", "Patel", "Iyer", "Nair", "Gupta", "Rao", "Singh", "Das", "Menon"]
SIGNUPS_PER_MONTH = [1, 1, 1, 2, 2, 2, 2, 3, 3, 3]  # Jan to Oct 2026
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ROLES = ["super_admin", "admin", "manager", "analyst", "support_staff"]
ROLE_CYCLE = ["manager", "analyst", "support_staff", "analyst", "manager", "support_staff", "admin"]
RANGE_KEYS = ["7d", "30d", "3m", "year"]


def build_users():
    users, next_id = [], 0
    for month, count in enumerate(SIGNUPS_PER_MONTH):
        for k in range(count):
            next_id += 1
            name = f"{FIRST[next_id % len(FIRST)]} {LAST[(next_id * 3) % len(LAST)]}"
            users.append({
                "id": next_id, "name": name,
                "email": f"{name.lower().replace(' ', '.')}{next_id}@example.com",
                "status": "Inactive" if next_id % 4 == 0 else "Active",
                "role": "super_admin" if next_id == 1 else ROLE_CYCLE[(next_id - 1) % len(ROLE_CYCLE)],
                "registered": date(2026, month + 1, ((k * 5 + next_id) % 27) + 1),
            })
    return users


def round_half_up(x):
    return math.floor(x + 0.5)


def day_label(d):
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def get_range(key, ref):
    if key == "7d":
        start = ref - timedelta(days=6)
    elif key == "30d":
        start = ref - timedelta(days=29)
    elif key == "3m":
        year, month = (ref.year, ref.month - 3) if ref.month > 3 else (ref.year - 1, ref.month + 9)
        start = date(year, month, min(ref.day, 28)) + timedelta(days=1)
    else:
        start = date(ref.year, 1, 1)
    return start, ref


def build_buckets(start, end, days):
    """Short ranges are shown day by day, longer ones month by month."""
    if days <= 31:
        return [(f"{d.day} {MONTHS[d.month - 1]}", lambda u, d=d: u["registered"] == d) for d in (start + timedelta(days=i) for i in range(days))]
    buckets, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        buckets.append((MONTHS[month - 1], lambda u, y=year, m=month: (u["registered"].year, u["registered"].month) == (y, m)))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return buckets


def compute(users, key, ref):
    start, end = get_range(key, ref)
    days = (end - start).days + 1
    in_range = [u for u in users if start <= u["registered"] <= end]
    previous = sum(1 for u in users if start - timedelta(days=days) <= u["registered"] <= start - timedelta(days=1))
    buckets = build_buckets(start, end, days)
    counts = [(label, [u for u in in_range if match(u)]) for label, match in buckets]
    monthly, running = [], 0
    for label, members in counts:
        running += len(members)
        monthly.append((label, len(members), running))
    active = sum(1 for u in in_range if u["status"] == "Active")
    peak = max(monthly, key=lambda m: m[1])
    return {
        "label": f"{day_label(start)} to {day_label(end)}", "start": start, "end": end,
        "total": len(in_range), "active": active, "inactive": len(in_range) - active,
        "new": sum(1 for u in in_range if (u["registered"].year, u["registered"].month) == (end.year, end.month)),
        "monthly": monthly,
        "trend": [(label, sum(1 for u in m if u["status"] == "Active"), sum(1 for u in m if u["status"] == "Inactive")) for label, m in counts],
        "roles": [(role, sum(1 for u in in_range if u["role"] == role)) for role in ROLES],
        "recent": sorted(in_range, key=lambda u: u["registered"], reverse=True)[:5],
        "average": round(len(in_range) / (days / 30.44), 1),
        "peak": peak,
        "growth": None if previous == 0 else round_half_up((len(in_range) - previous) / previous * 100),
        "active_rate": round_half_up(active / len(in_range) * 100) if in_range else 0,
    }


BANKING = {
    "internet_banking": {
        "meta": {"name": "Internet Banking", "subtitle": "Web banking activity across the bank's online portal.",
                 "trend_title": "Monthly logins", "trend_type": "line", "trend_series": "Logins",
                 "split_title": "Login results", "split_donut": "true", "bar_title": "Transactions by type", "bar_series": "Transactions"},
        "cards": [("Active sessions", "1,284"), ("Transactions today", "3,962"), ("Failed logins", "87"), ("Average session time", "8m 24s")],
        "trend": [("Jan", 4200), ("Feb", 4600), ("Mar", 5100), ("Apr", 4900), ("May", 5600), ("Jun", 6100), ("Jul", 6400), ("Aug", 6900), ("Sep", 7300), ("Oct", 7800)],
        "split": [("Success", 92), ("Failed", 5), ("Locked", 3)],
        "bar": [("Fund transfer", 1450), ("Bill payment", 980), ("Statements", 720), ("Cheque request", 340), ("Loan enquiry", 472)],
        "users_table": "internet_banking_users",
        "users": [
            (1, "IB-10021", "Anita Verma", "Savings", "26 Oct 2026, 10:42 am", "Active"),
            (2, "IB-10034", "Rahul Mehta", "Current", "26 Oct 2026, 9:15 am", "Active"),
            (3, "IB-10047", "Sunita Rao", "Savings", "24 Oct 2026, 6:30 pm", "Inactive"),
            (4, "IB-10052", "Vikash Kumar", "Salary", "25 Oct 2026, 2:05 pm", "Active"),
            (5, "IB-10068", "Deepa Nair", "Current", "21 Oct 2026, 11:50 am", "Inactive"),
            (6, "IB-10073", "Manoj Pillai", "Savings", "26 Oct 2026, 8:20 am", "Active"),
            (7, "IB-10089", "Farah Khan", "Salary", "25 Oct 2026, 7:45 pm", "Active"),
            (8, "IB-10095", "Girish Shetty", "Current", "19 Oct 2026, 4:10 pm", "Inactive"),
        ],
        "users_sql": "INSERT INTO internet_banking_users (id, customer_id, name, account_type, last_login, status) VALUES (%s, %s, %s, %s, %s, %s)",
    },
    "mobile_banking": {
        "meta": {"name": "Mobile Banking", "subtitle": "App usage and payments from the bank's mobile app.",
                 "trend_title": "Daily active devices (last 7 days)", "trend_type": "area", "trend_series": "Devices",
                 "split_title": "Platform share (%)", "split_donut": "false", "bar_title": "Payments by method", "bar_series": "Payments"},
        "cards": [("App installs", "48,210"), ("Active devices", "22,730"), ("Mobile payments", "9,846"), ("Crash rate", "0.8%")],
        "trend": [("Mon", 18200), ("Tue", 19100), ("Wed", 20400), ("Thu", 19800), ("Fri", 22300), ("Sat", 24100), ("Sun", 22730)],
        "split": [("Android", 68), ("iOS", 29), ("Other", 3)],
        "bar": [("UPI", 5400), ("QR code", 2100), ("Wallet", 1300), ("Card", 1046)],
        "users_table": "mobile_banking_users",
        "users": [
            (1, "MB-5001", "Kavya Iyer", "Pixel 8 (Android 15)", "4.2.1", "Active"),
            (2, "MB-5014", "Arjun Desai", "iPhone 15 (iOS 18)", "4.2.1", "Active"),
            (3, "MB-5022", "Nisha Patel", "Galaxy S23 (Android 14)", "4.1.7", "Inactive"),
            (4, "MB-5037", "Sameer Joshi", "OnePlus 12 (Android 15)", "4.2.0", "Active"),
            (5, "MB-5043", "Lakshmi Menon", "iPhone 13 (iOS 17)", "4.0.9", "Inactive"),
            (6, "MB-5058", "Tarun Bhatt", "Redmi Note 13 (Android 14)", "4.2.1", "Active"),
            (7, "MB-5066", "Ishita Roy", "iPhone 14 (iOS 18)", "4.2.0", "Active"),
            (8, "MB-5071", "Harish Gowda", "Galaxy A54 (Android 13)", "3.9.5", "Inactive"),
        ],
        "users_sql": "INSERT INTO mobile_banking_users (id, user_id, name, device, app_version, status) VALUES (%s, %s, %s, %s, %s, %s)",
    },
}


# User logs. Columns: id, username, action, ip_address, device, browser, timestamp, status, os, location, session_id, details
LOGS = {
    "user_logs_internet_banking": [
        (1, "anita.verma", "Login", "103.21.58.14", "Windows PC", "Chrome 130", "2026-10-26 10:42:15", "Success", "Windows 11", "Hyderabad, IN", "IB-S-80412", "Signed in with password and OTP."),
        (2, "rahul.mehta", "Fund Transfer", "49.37.201.8", "MacBook Air", "Safari 18", "2026-10-26 09:58:40", "Success", "macOS 15", "Mumbai, IN", "IB-S-80377", "Transferred 25,000 INR to a saved beneficiary."),
        (3, "sunita.rao", "Failed Login", "117.200.41.99", "Windows PC", "Edge 130", "2026-10-26 09:31:02", "Failed", "Windows 10", "Chennai, IN", "IB-S-80351", "Wrong password entered 3 times in a row."),
        (4, "vikash.kumar", "Bill Payment", "152.58.19.220", "Linux PC", "Firefox 132", "2026-10-25 19:12:33", "Success", "Ubuntu 24.04", "Pune, IN", "IB-S-80290", "Paid an electricity bill of 1,840 INR."),
        (5, "deepa.nair", "Password Change", "106.51.77.31", "MacBook Pro", "Chrome 130", "2026-10-25 17:45:09", "Success", "macOS 14", "Kochi, IN", "IB-S-80266", "Password changed after verifying the old password."),
        (6, "manoj.pillai", "Statement Download", "103.21.58.77", "Windows PC", "Chrome 129", "2026-10-25 14:05:51", "Success", "Windows 11", "Bengaluru, IN", "IB-S-80231", "Downloaded the last 3 months statement as PDF."),
        (7, "farah.khan", "Add Beneficiary", "49.205.12.140", "Windows PC", "Edge 130", "2026-10-25 11:20:18", "Failed", "Windows 11", "Delhi, IN", "IB-S-80198", "Beneficiary IFSC code was not valid."),
        (8, "girish.shetty", "Login", "182.73.104.6", "MacBook Air", "Safari 17", "2026-10-24 18:30:47", "Success", "macOS 14", "Mangaluru, IN", "IB-S-80150", "Signed in with password and OTP."),
        (9, "anita.verma", "Logout", "103.21.58.14", "Windows PC", "Chrome 130", "2026-10-24 12:10:05", "Success", "Windows 11", "Hyderabad, IN", "IB-S-80112", "Session ended by the user."),
        (10, "rahul.mehta", "Failed Login", "223.188.9.52", "Linux PC", "Firefox 131", "2026-10-23 22:48:29", "Failed", "Fedora 40", "Ahmedabad, IN", "IB-S-80077", "Account locked after 5 wrong attempts."),
        (11, "sunita.rao", "Fund Transfer", "117.200.41.99", "Windows PC", "Edge 130", "2026-10-23 16:02:11", "Success", "Windows 10", "Chennai, IN", "IB-S-80041", "Transferred 8,500 INR to a saved beneficiary."),
        (12, "vikash.kumar", "Cheque Request", "152.58.19.220", "Linux PC", "Firefox 132", "2026-10-22 10:15:36", "Success", "Ubuntu 24.04", "Pune, IN", "IB-S-79988", "Requested a new cheque book."),
    ],
    "user_logs_mobile_banking": [
        (1, "kavya.iyer", "UPI Payment", "49.36.88.201", "Pixel 8", "App WebView", "2026-10-26 11:05:22", "Success", "Android 15", "Bengaluru, IN", "MB-S-52031", "Paid 450 INR to a merchant using UPI."),
        (2, "arjun.desai", "Biometric Login", "106.208.14.77", "iPhone 15", "App WebView", "2026-10-26 10:48:09", "Success", "iOS 18", "Mumbai, IN", "MB-S-52017", "Signed in with Face ID."),
        (3, "nisha.patel", "OTP Failed", "27.61.205.9", "Galaxy S23", "Mobile Chrome", "2026-10-26 10:12:44", "Failed", "Android 14", "Surat, IN", "MB-S-51990", "The OTP expired before it was entered."),
        (4, "sameer.joshi", "QR Payment", "152.57.30.118", "OnePlus 12", "App WebView", "2026-10-25 20:33:57", "Success", "Android 15", "Nagpur, IN", "MB-S-51944", "Scanned a shop QR code and paid 1,200 INR."),
        (5, "lakshmi.menon", "Mobile Recharge", "117.246.18.64", "iPhone 13", "App WebView", "2026-10-25 18:21:30", "Success", "iOS 17", "Thiruvananthapuram, IN", "MB-S-51902", "Recharged a prepaid number with 299 INR."),
        (6, "tarun.bhatt", "App Login", "49.43.160.33", "Redmi Note 13", "App WebView", "2026-10-25 15:09:12", "Success", "Android 14", "Jaipur, IN", "MB-S-51871", "Signed in with a 6-digit PIN."),
        (7, "ishita.roy", "Add Payee", "106.220.5.147", "iPhone 14", "App WebView", "2026-10-25 12:47:58", "Failed", "iOS 18", "Kolkata, IN", "MB-S-51833", "The payee account number was not found."),
        (8, "harish.gowda", "App Update", "27.59.72.201", "Galaxy A54", "Mobile Chrome", "2026-10-24 21:15:40", "Success", "Android 13", "Mysuru, IN", "MB-S-51790", "Updated the app from 3.9.5 to 4.0.2."),
        (9, "kavya.iyer", "Failed Login", "49.36.88.201", "Pixel 8", "App WebView", "2026-10-24 09:02:16", "Failed", "Android 15", "Bengaluru, IN", "MB-S-51742", "Wrong PIN entered twice."),
        (10, "arjun.desai", "UPI Payment", "106.208.14.77", "iPhone 15", "App WebView", "2026-10-23 19:40:05", "Success", "iOS 18", "Mumbai, IN", "MB-S-51705", "Sent 2,000 INR to a friend using UPI."),
        (11, "nisha.patel", "Biometric Login", "27.61.205.9", "Galaxy S23", "App WebView", "2026-10-23 08:55:21", "Success", "Android 14", "Surat, IN", "MB-S-51668", "Signed in with a fingerprint."),
        (12, "tarun.bhatt", "QR Payment", "49.43.160.33", "Redmi Note 13", "App WebView", "2026-10-22 17:28:49", "Failed", "Android 14", "Jaipur, IN", "MB-S-51630", "The payment was declined because of low balance."),
    ],
}
LOG_COLUMNS = "id, username, action, ip_address, device, browser, timestamp, status, os, location, session_id, details"


def seed():
    create_users_table()
    create_page_tables()
    users = build_users()
    ref = max(u["registered"] for u in users)
    with cursor() as cur:
        cur.execute(
            "TRUNCATE date_ranges, users_page_data, overview_stats, monthly_registrations, user_distribution, "
            "recent_registrations, analytics_data, analytics_trend, analytics_roles, internet_banking_dashboard, "
            "internet_banking_users, mobile_banking_dashboard, mobile_banking_users, user_logs_internet_banking, user_logs_mobile_banking RESTART IDENTITY CASCADE"
        )
        cur.executemany(
            "INSERT INTO users_page_data (id, name, email, role, status, registered_at) VALUES (%s, %s, %s, %s, %s, %s)",
            [(u["id"], u["name"], u["email"], u["role"], u["status"], u["registered"]) for u in users],
        )
        for key in RANGE_KEYS:
            s = compute(users, key, ref)
            cur.execute("INSERT INTO date_ranges VALUES (%s, %s, %s, %s)", (key, s["label"], s["start"], s["end"]))
            cur.execute("INSERT INTO overview_stats VALUES (%s, %s, %s, %s, %s)", (key, s["total"], s["active"], s["inactive"], s["new"]))
            cur.executemany("INSERT INTO monthly_registrations VALUES (%s, %s, %s, %s, %s)", [(key, i, *m) for i, m in enumerate(s["monthly"])])
            cur.executemany("INSERT INTO user_distribution VALUES (%s, %s, %s)", [(key, "Active", s["active"]), (key, "Inactive", s["inactive"])])
            cur.executemany(
                "INSERT INTO recent_registrations VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [(key, i, u["id"], u["name"], u["email"], u["status"], u["registered"]) for i, u in enumerate(s["recent"])],
            )
            cur.execute("INSERT INTO analytics_data VALUES (%s, %s, %s, %s, %s, %s)", (key, s["average"], s["peak"][0], s["peak"][1], s["growth"], s["active_rate"]))
            cur.executemany("INSERT INTO analytics_trend VALUES (%s, %s, %s, %s, %s)", [(key, i, *t) for i, t in enumerate(s["trend"])])
            cur.executemany("INSERT INTO analytics_roles VALUES (%s, %s, %s, %s)", [(key, i, *r) for i, r in enumerate(s["roles"])])

        for prefix, cfg in BANKING.items():
            table = f"{prefix}_dashboard"
            rows = [("meta", i, k, None, v) for i, (k, v) in enumerate(cfg["meta"].items())]
            rows += [("card", i, label, None, text) for i, (label, text) in enumerate(cfg["cards"])]
            for section in ("trend", "split", "bar"):
                rows += [(section, i, label, value, None) for i, (label, value) in enumerate(cfg[section])]
            cur.executemany(f"INSERT INTO {table} (section, sort_order, label, item_value, display_value) VALUES (%s, %s, %s, %s, %s)", rows)
            cur.executemany(cfg["users_sql"], cfg["users"])

        for table, rows in LOGS.items():
            cur.executemany(f"INSERT INTO {table} ({LOG_COLUMNS}) VALUES ({', '.join(['%s'] * 12)})", rows)

        # A starter profile for the admin account (other accounts get defaults from the users table).
        cur.execute("INSERT INTO user_profiles VALUES ('admin', 'Admin User', '9876543210') ON CONFLICT DO NOTHING")

        # The first Super Admin. There is no public sign-up, so this account creates everyone else.
        # An existing account with this name is left as it is, so a changed password is never reset.
        cur.execute(
            "INSERT INTO users (username, email, password, role, status) VALUES (%s, %s, %s, 'super_admin', 'Active') "
            "ON CONFLICT (username) DO NOTHING",
            ("superadmin", "superadmin@dashboard.com", hash_password("Super@123")),
        )
    print(f"Seeded {len(users)} users and {len(RANGE_KEYS)} date ranges.")
    print("Super Admin account: superadmin / Super@123 (change the password after the first login)")


if __name__ == "__main__":
    seed()
