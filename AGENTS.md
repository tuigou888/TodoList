# AGENTS.md
## 交互要求

- Thinking思考过程用中文表述
- Reply回答也要用中文回复
## Commands

| Action       | Command                                                                      |
| ------------ | ---------------------------------------------------------------------------- |
| Dev server   | `python app.py` (port 5145, debug mode)                                      |
| Production   | `gunicorn -c gunicorn.conf.py app:app` (4 workers)                           |
| Docker       | `docker-compose up -d`                                                       |
| DB migration | `python migrate_db.py` (adds missing columns, creates default admin if none) |
| Install deps | `pip install -r requirements.txt`                                            |

## Setup

1. `cp .env.example .env` → set `SECRET_KEY` (required)
2. `python -m venv venv` + activate
3. `pip install -r requirements.txt`
4. `python app.py` → DB auto-creates on first run

## Architecture

- **Single-file app**: All logic in `app.py` (\~1368 lines). No blueprints, no package structure.
- **DB**: SQLite `todos.db` at project root. Auto-created by `init_db()`. Uses `sqlite3.Row` for dict-style access.
- **Templates**: `templates/` — 6 HTML files (index, login, register, admin, forgot/reset password). Inline CSS, no build step.
- **Session**: Flask-Session, filesystem storage in `flask_session/`.
- **Timezone**: `Asia/Shanghai` (set via `os.environ["TZ"]` and Docker).

## Key Quirks

- **Password hashing**: SHA-256 only (`hashlib.sha256`). Not bcrypt/argon2.
- **Password reset tokens**: Stored in-memory (`RESET_TOKENS` dict). Lost on app restart. 1-hour expiry.
- **Email reminders**: Background daemon thread, checks hourly at 7:30–21:30 Beijing time. Uses `time.sleep()` to wait for next hour.
- **Gunicorn hooks**: `when_ready()` in `gunicorn.conf.py` calls `init_db()` and `start_reminder_scheduler()`. The `on_starting`/`when_ready` functions are also defined at module level in `app.py` (duplicate — Gunicorn uses the config file version).
- **CORS + security headers**: Applied via `cors_response()` helper, attached to every response through `@app.after_request`.
- **`migrate_db.py`**: Idempotent migration script — only adds columns that don't exist. Creates default admin (`admin`/`admin123`) if no admincommand 'markdown.extension.onBackspaceKey' not found
## File Boundaries

| Path               | Role                                                   |
| ------------------ | ------------------------------------------------------ |
| `app.py`           | All routes, DB logic, email, scheduler                 |
| `config.py`        | `Config` class — reads env vars via `os.environ.get()` |
| `gunicorn.conf.py` | Prod server config + startup hooks                     |
| `migrate_db.py`    | Standalone DB migration (run manually)                 |
| `todos.db`         | SQLite database (gitignored, volume-mounted in Docker) |
| `flask_session/`   | Session files (gitignored, Docker volume)              |

## Docker Notes

- Port: `5145`
- `todos.db` bind-mounted from host: `./todos.db:/app/todos.db`
- `flask_session` uses named volume `flask_session_data`
- Healthcheck: `curl -f http://localhost:5145/` every 30s
- Dockerfile sets `TZ=Asia/Shanghai`

## Conventions

- No test framework, no linter, no formatter, no type checker.
- All API routes return JSON. Page routes return `render_template()`.
- Auth via `@login_required` and `@admin_required` decorators.
- SQL uses parameterized queries (`?` placeholders).
- Error responses: `jsonify({"error": "message"}), <status_code>`.

<br />

<br />

