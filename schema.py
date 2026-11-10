from db import cursor

# range_key is one of: 7d, 30d, 3m, year. Each range has its own pre-calculated rows.
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS date_ranges (
    range_key TEXT PRIMARY KEY, label TEXT NOT NULL, start_date DATE NOT NULL, end_date DATE NOT NULL
);
CREATE TABLE IF NOT EXISTS users_page_data (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL,
    status TEXT NOT NULL, registered_at DATE NOT NULL
);
CREATE TABLE IF NOT EXISTS overview_stats (
    range_key TEXT PRIMARY KEY REFERENCES date_ranges ON DELETE CASCADE,
    total_users INT NOT NULL, active_users INT NOT NULL, inactive_users INT NOT NULL, new_registrations INT NOT NULL
);
CREATE TABLE IF NOT EXISTS monthly_registrations (
    range_key TEXT NOT NULL REFERENCES date_ranges ON DELETE CASCADE, sort_order INT NOT NULL,
    label TEXT NOT NULL, registrations INT NOT NULL, cumulative_users INT NOT NULL,
    PRIMARY KEY (range_key, sort_order)
);
CREATE TABLE IF NOT EXISTS user_distribution (
    range_key TEXT NOT NULL REFERENCES date_ranges ON DELETE CASCADE, name TEXT NOT NULL, item_value INT NOT NULL,
    PRIMARY KEY (range_key, name)
);
CREATE TABLE IF NOT EXISTS recent_registrations (
    range_key TEXT NOT NULL REFERENCES date_ranges ON DELETE CASCADE, rank_no INT NOT NULL, user_id INT NOT NULL,
    name TEXT NOT NULL, email TEXT NOT NULL, status TEXT NOT NULL, registered_at DATE NOT NULL,
    PRIMARY KEY (range_key, rank_no)
);
CREATE TABLE IF NOT EXISTS analytics_data (
    range_key TEXT PRIMARY KEY REFERENCES date_ranges ON DELETE CASCADE,
    average_per_month NUMERIC(8,1) NOT NULL, peak_label TEXT NOT NULL, peak_value INT NOT NULL,
    growth_rate INT, active_rate INT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics_trend (
    range_key TEXT NOT NULL REFERENCES date_ranges ON DELETE CASCADE, sort_order INT NOT NULL,
    label TEXT NOT NULL, active_count INT NOT NULL, inactive_count INT NOT NULL,
    PRIMARY KEY (range_key, sort_order)
);
CREATE TABLE IF NOT EXISTS analytics_roles (
    range_key TEXT NOT NULL REFERENCES date_ranges ON DELETE CASCADE, sort_order INT NOT NULL,
    role TEXT NOT NULL, item_value INT NOT NULL, PRIMARY KEY (range_key, role)
);
CREATE TABLE IF NOT EXISTS internet_banking_dashboard (
    id SERIAL PRIMARY KEY, section TEXT NOT NULL, sort_order INT NOT NULL, label TEXT NOT NULL,
    item_value NUMERIC, display_value TEXT
);
CREATE TABLE IF NOT EXISTS internet_banking_users (
    id INTEGER PRIMARY KEY, customer_id TEXT NOT NULL, name TEXT NOT NULL, account_type TEXT NOT NULL,
    last_login TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mobile_banking_dashboard (
    id SERIAL PRIMARY KEY, section TEXT NOT NULL, sort_order INT NOT NULL, label TEXT NOT NULL,
    item_value NUMERIC, display_value TEXT
);
CREATE TABLE IF NOT EXISTS mobile_banking_users (
    id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, device TEXT NOT NULL,
    app_version TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_logs_internet_banking (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL, action TEXT NOT NULL, ip_address TEXT NOT NULL,
    device TEXT NOT NULL, browser TEXT NOT NULL, timestamp TIMESTAMP NOT NULL, status TEXT NOT NULL,
    os TEXT NOT NULL, location TEXT NOT NULL, session_id TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_logs_mobile_banking (
    id INTEGER PRIMARY KEY, username TEXT NOT NULL, action TEXT NOT NULL, ip_address TEXT NOT NULL,
    device TEXT NOT NULL, browser TEXT NOT NULL, timestamp TIMESTAMP NOT NULL, status TEXT NOT NULL,
    os TEXT NOT NULL, location TEXT NOT NULL, session_id TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_profiles (
    username TEXT PRIMARY KEY, full_name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT ''
);
"""


USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(120),
    password TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'support_staff',
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
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'support_staff';
ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'Active';
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'support_staff';
-- Older accounts used three roles. They move to the new five-role system.
UPDATE users SET role = CASE role WHEN 'Admin' THEN 'admin' WHEN 'Editor' THEN 'manager' WHEN 'Viewer' THEN 'support_staff' ELSE role END
WHERE role IN ('Admin', 'Editor', 'Viewer');
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON users (email);
"""


def create_users_table():
    """Creates the users table, or upgrades an older one (new columns, new role names)."""
    with cursor() as cur:
        cur.execute(USERS_SQL)


def create_page_tables():
    with cursor() as cur:
        cur.execute(SCHEMA_SQL)
