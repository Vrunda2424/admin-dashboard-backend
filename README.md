# Admin Dashboard Backend (Flask + PostgreSQL)

Simple Register and Login API. Passwords are stored as hashes, never as plain text.

## 1. Start PostgreSQL in Docker (once)
```bash
docker run --name admin-dashboard-db -e POSTGRES_PASSWORD=dashboard_dev_pw -e POSTGRES_DB=admin_dashboard -p 5433:5432 -v admin-dashboard-pgdata:/var/lib/postgresql/data -d postgres:16
```
Later: `docker start admin-dashboard-db` / `docker stop admin-dashboard-db`.

## 2. Run the backend
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```
Runs at http://localhost:5001 and creates the `users` table automatically.

## 3. View the data in pgAdmin
Host `localhost`, Port `5433`, Database `admin_dashboard`, User `postgres`, Password `dashboard_dev_pw`.
Then: Databases > admin_dashboard > Schemas > public > Tables > users.

## Endpoints
| Method | URL | Body |
|---|---|---|
| POST | /api/register | `{"username": "...", "password": "..."}` |
| POST | /api/login | `{"username": "...", "password": "..."}` |
| GET | /api/users | none. Returns id, username, created_at (never the password hash) |
