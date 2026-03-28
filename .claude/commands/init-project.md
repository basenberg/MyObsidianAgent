Initialize and start the project from scratch. Run each step in sequence and report results.

## 1. Install Dependencies

```bash
uv sync
```

**Expected:** Virtual environment created, all packages installed successfully.

## 2. Create Environment File

```bash
cp .env.example .env
```

**Expected:** `.env` file created. Skip if it already exists.

## 3. Start Docker Services (PostgreSQL)

```bash
docker-compose up -d
```

**Expected:** PostgreSQL container starts and becomes healthy.

## 4. Run Database Migrations

```bash
uv run alembic upgrade head
```

**Expected:** Migrations applied successfully with no errors.

## 5. Start Development Server

```bash
uv run uvicorn app.main:app --reload --port 8123
```

**Expected:** Server running on http://127.0.0.1:8123

## 6. Validate

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8123/health
```

**Expected:** `200`

## 7. Summary

Report the result of each step (pass/fail) and confirm the app is accessible at:
- API: http://localhost:8123
- Swagger UI: http://localhost:8123/docs
