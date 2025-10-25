# MoreeHoney backend (development)

This folder contains a small Express backend that uses MariaDB to store dummy users and admin accounts for local development.

Contents:

- `index.js` - Express server, creates tables and inserts dummy users/admins if missing.
- `docker-compose.yml` - brings up a MariaDB instance and runs the API (binds ports 3306 and 4000).
- `.env.example` - sample environment variables.

Quick start (uses Docker Compose):

1. Copy `.env.example` to `.env` in this folder if you want to override values.

2. From this `Website/backend` folder run:

```bash
docker compose up --build
```

This will start a MariaDB container and the API container. The API will create the database schema and insert dummy accounts if necessary.

API endpoints:

- `POST /api/login` - body: `{ username?, email?, password }` - checks `users` table.
- `POST /api/admin/login` - body: `{ username?, email?, password }` - checks `admins` table.
- `GET /api/health` - returns `{ status: 'ok' }`.
- `GET /api/users` - debug listing of users (dev only).

Dummy accounts inserted by default:

- users: `johndoe` / `john@example.com` with password `password123`
- users: `janedoe` / `jane@example.com` with password `password123`
- admin: `admin` / `admin@example.com` with password `adminpass`

Integration with the frontend:

Update your frontend login calls to POST to `http://localhost:4000/api/login` or `.../api/admin/login` while developing locally.
