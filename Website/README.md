# Website

The honeypot site. It presents as a fake movie streaming service called "MovieStream" to attract real attackers. There are two separate layers to it: a set of static HTML pages that were deployed first, and a React frontend backed by a small Express/SQLite API that was built later on.

Every login form on the site sends credentials to an AWS Lambda function for capture regardless of whether authentication succeeds or fails.

---

## Structure

```
Website/
├── Index.html          # Static home page (honey theme)
├── login.html          # Static login honeypot
├── admin.html          # Static admin panel honeypot
├── products.html       # Static honey products page
│
├── backend/            # Node.js + Express + SQLite API (port 3000)
│   ├── index.js        # All routes
│   └── db.js           # SQLite setup and schema
│
└── frontend/           # React + Vite + Tailwind app (port 8080)
    └── src/
        ├── App.tsx     # Router
        ├── pages/      # Login, Register, AdminLogin, Movies, etc.
        └── components/ # Navbar, Hero, Products, Contact, Footer
```

---

## Static HTML pages

These four pages were the first version of the honeypot, served directly by nginx. They are self-contained with no framework dependencies.

### Index.html

The landing page. Styled with a warm honey/beige gradient and a bee logo. Has navigation links to login, admin, and products. The cover story is a sustainable beekeeping brand, which is deliberately mismatched with the site's actual branding elsewhere (MovieStream) to see if attackers notice or care.

### login.html

A fake user login form. On submit it captures the username, password, timestamp, and browser metadata (userAgent, platform, language) and sends them to the Lambda function, then shows an "invalid credentials" alert. The form never authenticates anyone.

### admin.html

A more elaborate trap. It has a two-column layout with a login form on the right and a fake "active services" panel on the left. The panel includes clickable links to commonly probed endpoints like `/config.php`, `/backup.zip`, `/wp-admin`, and `/api/upload`. The form includes a fake CSRF token field and a file upload input. On submit it logs the username, password, CSRF token, and any file metadata to Lambda.

### products.html

A simple product catalog page showing four honey products with prices. No honeypot behaviour, just part of the cover story.

---

## Backend

A minimal Express API that provides real authentication backed by SQLite. It was added so that the React frontend would have something to actually talk to, making the site look and behave like a real application under deeper inspection.

**Start it:**

```bash
cd backend
npm install
npm start        # runs on port 3000
```

### Routes

| Method | Path | What it does |
|--------|------|-------------|
| POST | `/api/auth/register` | Creates a new user. Hashes the password with bcrypt (10 rounds). Returns 409 if the email is already taken. |
| POST | `/api/auth/login` | Verifies email + password against the database. Returns user info on success, 401 on failure. |
| GET | `/api/users` | Returns the last 100 registered users (id, username, email, created_at). No auth required, intentionally exposed. |

### Database

SQLite file at `backend/honeystream.db`. Single table:

```sql
CREATE TABLE users (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  email      TEXT UNIQUE NOT NULL,
  password   TEXT NOT NULL,
  username   TEXT UNIQUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
```

### Dependencies

- `express` — web framework
- `sqlite3` — database
- `bcryptjs` — password hashing
- `body-parser` — JSON parsing
- `cors` — open CORS (`*`) so the frontend can reach it from any origin

---

## Frontend

A React application built with Vite and TypeScript. Branded as "MovieStream" rather than the honey theme, continuing the misdirection. All login and registration actions send credentials to Lambda in addition to whatever the actual backend response is.

**Start it:**

```bash
cd frontend
bun install      # or npm install
bun run dev      # runs on port 8080
```

**Build for production:**

```bash
bun run build    # outputs to dist/
```

### Pages

| Route | Page | What it does |
|-------|------|-------------|
| `/` | Index | Landing page with Hero, Products, and Contact sections |
| `/login` | Login | Email + password form. Calls `/api/auth/login`. Logs to Lambda on both success and failure. |
| `/register` | Register | Username + email + password form. Calls `/api/auth/register`. Logs all attempts to Lambda. |
| `/admin` | AdminLogin | Admin login form. Intentionally fails the first two attempts before showing success on the third. Logs every attempt to Lambda. |
| `/movies` | Movies | Static catalog of five movies (Inception, The Matrix, Interstellar, The Dark Knight, Avatar). |
| `/movies/:id` | MovieDetail | Individual movie detail page. |
| `*` | NotFound | 404 page. |

### Honeypot behaviour in the React pages

Every page that has a form sends a POST to the Lambda endpoint with the captured credentials and metadata before or alongside the actual API call. The Lambda URL is also embedded as a hidden link in the Login page and as a visible link in the Contact component (this is intentional, to attract automated scanners that follow all links on a page).

The `AdminLogin` page is worth noting: it always rejects the first two login attempts regardless of what is entered, then accepts on the third. This is to encourage attackers to try multiple credential combinations, giving the honeypot more data points.

### Tech stack

- React 18 + React Router v6
- Vite + TypeScript
- Tailwind CSS + shadcn/ui (Radix UI components)
- TanStack React Query for API calls
- react-hook-form + Zod for form validation
- Recharts for any chart components
- Sonner for toast notifications
- Lucide React for icons

### Environment variables

Create a `.env` file in `frontend/` if you need to point at a different backend:

```
VITE_API_URL=http://localhost:3000
VITE_LAMBDA_URL=https://rlvfmp3gt2.execute-api.us-east-1.amazonaws.com/default/HoneyPot1
```

Both have sensible defaults so the app works without a `.env` in local development.

---

## Lambda integration

All honeypot capture goes to a single AWS Lambda endpoint via API Gateway. The payload structure varies slightly per page but always includes:

```json
{
  "event_type": "login_attempt | admin_login_attempt | register_attempt | adminLoginAttempt",
  "username": "...",
  "password": "...",
  "timestamp": "ISO8601",
  "client": {
    "userAgent": "...",
    "platform": "...",
    "language": "..."
  }
}
```

The admin page additionally captures the fake CSRF token value and file upload metadata if a file was selected.

See `Lambda/lambda_function.py` in the root of the repo for what happens to these payloads on the other side.

---

## Running locally

The static HTML pages can be opened directly in a browser or served by nginx. They do not depend on the backend or frontend being running.

For the full React app + backend:

```bash
# Terminal 1
cd Website/backend && npm install && npm start

# Terminal 2
cd Website/frontend && bun install && bun run dev
```

The frontend dev server proxies nothing by default, so make sure `VITE_API_URL` points to wherever the backend is running.
