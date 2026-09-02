# Hệ thống hỗ trợ khách hàng có tích hợp AI

Full-stack: React + Vite + Vanilla CSS · FastAPI + SQLAlchemy (async) · PostgreSQL · Gemini API.

Yêu cầu đặc tả: [`documents/SRS.md`](documents/SRS.md). Bản thiết kế:
[`docs/superpowers/specs/2026-09-02-ai-customer-support-design.md`](docs/superpowers/specs/2026-09-02-ai-customer-support-design.md).

## Chạy toàn bộ stack (Docker)

1. `copy .env.example .env` và điền các giá trị bí mật (đặc biệt `SEED_ADMIN_PASSWORD`, `JWT_SECRET_KEY`; nếu có key Gemini thì đặt `AI_PROVIDER=gemini` và `GEMINI_API_KEY=...`).
2. `docker compose up --build`
3. Frontend: http://localhost:8080 · Backend docs: http://localhost:8000/api/docs · Health: http://localhost:8000/health/live, `/health/ready`, `/health/ai`

Backend tự chạy `alembic upgrade head` + seed (idempotent) trước khi khởi động.

## Chạy backend khi đang phát triển

- DB: `docker compose up -d db`
- Backend: `cd backend; python -m venv .venv; .venv/Scripts/python -m pip install -e ".[dev]"`
- Unit test (không cần DB): `cd backend && .venv/Scripts/python -m pytest tests/unit -q`
- Integration test (cần DB đang chạy): 
  `DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support INTEGRATION=1 .venv/Scripts/python -m pytest tests/integration -q`

## Frontend dev

`cd frontend && npm install && npm run dev` → http://localhost:5173 (proxy `/api` → backend :8000).
