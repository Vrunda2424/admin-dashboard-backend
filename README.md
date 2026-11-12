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
Runs at http://localhost:5001. On start it creates or upgrades the `users` table (older accounts move to the new roles).

## 3. Fill the tables and create the Super Admin (once)
```bash
python seed.py
```
It is safe to run again. If an API answers "Run python seed.py", this step was skipped.

### First login
| Username | Password | Role |
|---|---|---|
| `superadmin` | `Super@123` | Super Admin |

There is **no public registration**. Sign in as the Super Admin and create every other user from the **User Access Management** page. Change this password after the first login (profile menu, Change Password).

## 4. View the data in pgAdmin
Host `localhost`, Port `5433`, Database `admin_dashboard`, User `postgres`, Password `dashboard_dev_pw`.

## Roles
| Label | Stored value | Opens UAM | Can create, edit, and delete |
|---|---|---|---|
| Super Admin | `super_admin` | Yes | Every role, except their own row |
| Admin | `admin` | Yes | Manager, Analyst, and Support Staff only |
| Manager | `manager` | No | Nobody |
| Analyst | `analyst` | No | Nobody |
| Support Staff | `support_staff` | No | Nobody |

All roles see every sidebar tab and every dashboard page. Older accounts moved to the new roles like this: Admin to `admin`, Editor to `manager`, Viewer to `support_staff`.

The React app hides what a role cannot use, but **the API enforces the same rules**, so calling it directly does not bypass them.

## Authentication
`POST /api/login` returns a signed token (valid for 8 hours) and the user's role. Send the token with every other request: `Authorization: Bearer <token>`. Set `SECRET_KEY` in the environment for anything beyond local practice.

## Endpoints
| Method | URL | Who | Body or notes |
|---|---|---|---|
| POST | /api/login | Anyone | `{"username", "password"}`. Returns `token` and `user` (id, username, role). Inactive users are refused |
| POST | /api/change-password | Anyone with the current password | `{"username", "current_password", "new_password"}` |
| GET | /api/users | Super Admin, Admin | All users (never the password) |
| POST | /api/users | Super Admin, Admin | `{"username", "email", "password", "role", "status"}`. Admin can only create manager, analyst, support_staff |
| PUT | /api/users/<id> | Super Admin, Admin | `{"role", "status"}`. Not on your own row, and not above what you may assign |
| DELETE | /api/users/<id> | Super Admin, Admin | Same rules as PUT |
| GET | /api/overview?range=7d\|30d\|3m\|year | Any signed-in user | Overview cards, charts, and table |
| GET | /api/analytics?range=... | Any signed-in user | Analytics statistics and charts |
| GET | /api/internet-banking/dashboard, /users, /user-logs, /user-logs/<id> | Any signed-in user | Internet Banking pages |
| GET | /api/mobile-banking/dashboard, /users, /user-logs, /user-logs/<id> | Any signed-in user | Mobile Banking pages |
| GET | /api/users-page | Any signed-in user | Users page table |
| GET, PUT | /api/settings | Any signed-in user | The signed-in user's own profile |
| GET | /api/mobile-banking/face-users | Any signed-in user | Face Users table (user id, username, name, email, mobile number, registration date, status) |
| GET | /api/mobile-banking/face-logs, /api/mobile-banking/face-logs/<id> | Any signed-in user | Face activity logs, and the full details of one entry (including match score and liveness check) |
