# Hệ thống hỗ trợ khách hàng có tích hợp AI

Full-stack: React + Vite + Vanilla CSS · FastAPI + SQLAlchemy (async) · PostgreSQL · Gemini API.

Yêu cầu đặc tả: [`documents/SRS.md`](documents/SRS.md). Bản thiết kế:
[`docs/superpowers/specs/2026-09-02-ai-customer-support-design.md`](docs/superpowers/specs/2026-09-02-ai-customer-support-design.md).

## Chạy toàn bộ stack (Docker)

1. `copy .env.example .env` và điền các giá trị bí mật (đặc biệt `SEED_ADMIN_PASSWORD`, `JWT_SECRET_KEY`; nếu có key Gemini thì đặt `AI_PROVIDER=gemini` và `GEMINI_API_KEY=...`).
2. `docker compose up --build`
3. Frontend: http://localhost:8080 · Backend docs: http://localhost:8000/api/docs · Health: http://localhost:8000/health/live, `/health/ready`, `/health/ai`

Backend tự chạy `alembic upgrade head` + seed (idempotent) trước khi khởi động.

### S1 — Đăng nhập & phân quyền

Từ S1, hệ thống có đăng nhập (JWT access 15 phút + refresh token 7 ngày trong cookie HttpOnly `refresh_token`). Mở `http://localhost:8080` và đăng nhập bằng một tài khoản seed:

| Vai trò | Email | Mật khẩu (seed) | Vùng sau đăng nhập |
|---|---|---|---|
| Quản trị viên | `admin@example.com` | giá trị `SEED_ADMIN_PASSWORD` trong `.env` | `/app/admin` |
| Quản lý | `hung.manager@example.com` | `hung.manager@Dev123` | `/app/dashboard` |
| Quản lý | `ha.manager@example.com` | `ha.manager@Dev123` | `/app/dashboard` |
| Nhân viên | `lan.agent@example.com` | `lan.agent@Dev123` | `/app/tickets` |
| Nhân viên | `minh.agent@example.com` | `minh.agent@Dev123` | `/app/tickets` |

Sai mật khẩu 5 lần trong 15 phút sẽ khóa tạm thời tài khoản (`AUTH_ACCOUNT_LOCKED`). Chi tiết kỹ thuật: `docs/superpowers/plans/2026-09-02-s1-auth-rbac.md`.

### S2 — Public Portal & Ticket core

Từ S2, khách hàng **không cần đăng nhập** để gửi yêu cầu hỗ trợ và tra cứu tiến độ:

- **`/`** — Biểu mẫu gửi yêu cầu (họ tên, email, tiêu đề, mô tả, phân loại, tệp đính kèm tối đa 5 tệp). Vé được tạo ở trạng thái `OPEN`, ưu tiên `MEDIUM`, kèm hạn SLA.
- **`/track`** — Tra cứu bằng mã vé + email. Chỉ hiển thị thông tin công khai (không lộ ghi chú nội bộ, phân công hay audit). Nhập sai mã/email trả về cùng một thông báo (chống dò vé).
- **`/app/tickets`** và **`/app/tickets/:id`** — Nhân viên/quản lý/admin: danh sách có lọc (trạng thái, tìm kiếm, "vé của tôi"), chi tiết vé với dòng thời gian (phản hồi, lịch sử, tệp), đổi trạng thái theo state machine, bình luận công khai/nội bộ, đính kèm + tải tệp.
- **Phân công tối thiểu** (S2): Quản lý/Admin gán vé vào nhóm + người phụ trách. Quản lý chỉ gán được vào nhóm mình quản lý; người được gán phải thuộc nhóm và còn hoạt động.
- Truy cập theo scope: Admin xem tất cả; Quản lý xem vé nhóm mình quản lý + vé chưa gán nhóm; Nhân viên xem vé nhóm mình + vé được gán cho mình. Vé ngoài scope trả về `404` (không lộ thông tin).
- Mọi thao tác ghi đều dùng **optimistic lock**: body kèm `version`; ghi sai phiên bản trả về `409 VERSION_CONFLICT`.

Demo nhanh: gửi vé tại `/` → đăng nhập `lan.agent@example.com` (mật khẩu seed ở bảng S1) → mở vé trong `/app/tickets` → phản hồi → chuyển `RESOLVED`. Chi tiết kỹ thuật: `docs/superpowers/plans/2026-09-02-s2-ticket-core.md`.

## Chạy backend khi đang phát triển

- DB: `docker compose up -d db`
- Backend: `cd backend; python -m venv .venv; .venv/Scripts/python -m pip install -e ".[dev]"`
- Unit test (không cần DB): `cd backend && .venv/Scripts/python -m pytest tests/unit -q`
- Integration test (cần DB đang chạy): 
  `DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support INTEGRATION=1 .venv/Scripts/python -m pytest tests/integration -q`

## Frontend dev

`cd frontend && npm install && npm run dev` → http://localhost:5173 (proxy `/api` → backend :8000).
