# Admin Dashboard Backend (Flask + PostgreSQL)

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
Runs at http://localhost:5001. On start it creates the `users` table, or upgrades an older table
(adds email, role, status, and renames password_hash to password and created_at to registration_date).

Passwords are hashed with bcrypt. Accounts made before bcrypt was added can still log in.

## 3. View the data in pgAdmin
Host `localhost`, Port `5433`, Database `admin_dashboard`, User `postgres`, Password `dashboard_dev_pw`.

## Endpoints
| Method | URL | Body |
|---|---|---|
| POST | /api/register | `{"username", "email", "password", "role", "status"}` (role: Admin, Editor, Viewer; status: Active, Inactive) |
| POST | /api/login | `{"username", "password"}` (inactive users are refused) |
| POST | /api/change-password | `{"username", "current_password", "new_password"}` |
| GET | /api/users | none. Returns id, username, email, role, status, registration_date (never the password) |
