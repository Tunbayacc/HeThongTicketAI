# Bản thiết kế — Hệ thống hỗ trợ khách hàng tích hợp AI

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | DSGN-CSAI-01 |
| Ngày | 02/09/2026 |
| Trạng thái | Đã duyệt — chờ viết implementation plan |
| Nguồn yêu cầu | `documents/SRS.md` v1.0 (SRS-CSAI) |
| Nhóm | La Văn Tuấn, Trần Minh Thuận |
| Cách phát triển | Full-stack theo lát cắt dọc (8 lát), mỗi lát có test xanh + demo chạy được |

Tài liệu này **chốt cách triển khai** trên nền SRS (SRS là nguồn đặc tả yêu cầu chi tiết — từ điển dữ liệu §6, endpoint §8, kiểm thử §13, tiêu chí nghiệm thu §11 giữ nguyên giá trị pháp lý). Mọi quyết định thiết kế dưới đây đều phải giữ nhất quán với **Mục 16 SRS** (không trạng thái Assigned, AI chỉ 3 chức năng, mọi AI result là `pending_review`, Frontend không phải ranh giới bảo mật, v.v.).

---

## 1. Bối cảnh và mục đích

Xây dựng ứng dụng web **hệ thống hỗ trợ khách hàng có tích hợp AI** theo vòng đời ticket, với 4 vai trò (Public User, Support Agent, Team Manager, Administrator) và 3 chức năng AI có Human-in-the-loop (phân loại, tóm tắt, tạo bản nháp).

Ngăn xếp cố định theo SRS: **React + Vite + Vanilla CSS** (cấm Tailwind) · **FastAPI + Pydantic** · **PostgreSQL + SQLAlchemy** · **Gemini API** · **JWT/bcrypt** · **Docker Compose**.

Môi trường máy đã xác nhận: Node v24, Python 3.11.9, Docker 29, PostgreSQL client 18. Người dùng có **Gemini API key thật** nhưng hệ thống vẫn cần một provider interface để chạy mock trong test/offline.

## 2. Phạm vi

**Trong phạm vi:** toàn bộ nhóm yêu cầu **Must** + các **Should** thiết yếu của SRS §4. Cụ thể: xác thực phiên; Public Portal (tạo + tra cứu ticket); quản lý ticket (lọc/tìm/phân trang/chi tiết/lịch sử); vòng đời trạng thái; nhóm & phân công; bình luận công khai + ghi chú nội bộ; tệp đính kèm; AI (phân loại/tóm tắt/bản nháp) + AI Review Panel; SLA; Dashboard & báo cáo; quản trị người dùng/nhóm/chính sách SLA; Audit Log; kiểm thử.

**Ngoài phạm vi** (theo SRS §2.2.2): chatbot, AI tự ra quyết định, RAG/FAQ, phân tích đa phương tiện, email gateway, CAPTCHA (Could), xuất CSV (Could).

**Phạm vi kiểm thử:** bộ unit + integration cho nghiệp vụ cốt lõi (§10 của doc này). Không chạy perf test 50k ticket / 50 user ở giai đoạn này.

## 3. Quyết định thiết kế then chốt

| Chủ đề | Quyết định | Căn cứ SRS |
|---|---|---|
| ORM / DB access | SQLAlchemy 2.0 **async** + asyncpg; Alembic migration | §6, NFR-MAI-04 |
| Auth | Access JWT **15 phút** (payload: `user_id`, `role`, `exp`); Refresh token ngẫu nhiên **băm SHA-256**, lưu DB, 7 ngày, đặt cookie **HttpOnly + Secure + SameSite=Lax** | NFR-SEC-03/04/05 |
| Chống ghi đè | Optimistic locking: mọi PATCH gửi kèm `version`; mismatch → `409 VERSION_CONFLICT` | FR-TIC-12, R-10 |
| Vai trò | `AGENT`, `MANAGER`, `ADMIN` (bảng users); team_role `MEMBER`/`MANAGER` (team_members) | §6.3.1, §6.3.3 |
| Data Scoping | Dependency `get_current_user` + bộ lọc scope cho mọi truy vấn ticket/dashboard theo vai trò | NFR-SEC-06, FR-REP-07..09 |
| AI | Interface `AIProvider`: `GeminiProvider` (httpx async, timeout 30 s, retry ≤1 lỗi tạm thời) + `MockProvider` (kết quả mẫu xác định). Chọn qua env `AI_PROVIDER` | §8.5, NFR-SCA-05 |
| PII Masking | Regex email/SĐT → placeholder `[EMAIL-n]`, `[PHONE-n]` giữ ngữ cảnh | NFR-PRI-02/03 |
| Mã ticket | `TK-` + 8 ký tự base32 in hoa (không tuần tự) | BR-01, FR-PUB-04 |
| Tệp tải lên | Volume local ngoài web root; DB chỉ metadata; allowlist `PDF, PNG, JPG, TXT, DOCX`; ≤10 MB/tệp, ≤5 tệp/lần; tên lưu = UUID | FR-COM-08..12, NFR-SEC-11 |
| XSS | Frontend render mọi nội dung dạng text (React mặc định escape); backend có sanitize dự phòng | NFR-SEC-08, AC-SEC-03 |
| Log / trace | Middleware gán `request_id`; structured JSON log; tách audit-log nghiệp vụ | NFR-OBS-01/02/05 |
| Rate limit | `slowapi` cho /public/*, /auth/login, /api/ai/* | NFR-SEC-10, FR-PUB-08 |
| Múi giờ | Lưu `TIMESTAMPTZ` UTC; hiển thị chuyển đổi client | BR-15, R-11 |
| Dashboard biểu đồ | SVG vẽ tay (không thêm dependency nặng); hỗ trợ 2 theme | FR-REP |

### 3.1 Giá trị mặc định đã chốt cho các mục TBD (SRS §17)

| Mã | Giá trị triển khai |
|---|---|
| TBD-01 Category | `TECHNICAL, ACCOUNT, BILLING, GENERAL, OTHER` |
| TBD-02 Pending pause SLA | Theo từng `sla_policy.pause_on_pending`; mặc định `false` |
| TBD-03 Resolved→Closed tự động | Không (bản cơ sở) |
| TBD-04 Public phản hồi 2 chiều | Không — chỉ tra cứu |
| TBD-05 Loại tệp | `PDF, PNG, JPG, TXT, DOCX` |
| TBD-06 Lưu trữ dữ liệu | 12 tháng |
| TBD-07 Confidence thấp | `< 0.70` → hiển thị cảnh báo |
| TBD-08 Giờ làm việc tính SLA | Liên tục 24/7 |
| TBD-09 Email thông báo | Không thuộc bản cơ sở |

## 4. Cấu trúc repository

```
HeThongHoTroAI/
├── backend/
│   ├── app/
│   │   ├── api/            # routers: auth, public, tickets, ai, admin, dashboard, health
│   │   ├── core/           # config, security (jwt/bcrypt), deps (auth, rbac, scoping), exceptions, logging
│   │   ├── models/         # SQLAlchemy ORM (11 bảng)
│   │   ├── schemas/        # Pydantic request/response + enum chung
│   │   ├── services/       # auth_service, ticket_service, sla_service, ai_service, audit_service, ...
│   │   ├── ai/             # providers/, pii_masker.py, prompts/, schemas.py
│   │   ├── db/             # session, base, seed.py
│   │   └── main.py         # FastAPI app, lifespan (migration+seed), middleware
│   ├── alembic/            # versions/ + env.py
│   ├── tests/              # unit/ + integration/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/            # client.js (fetch + auto refresh), auth store
│   │   ├── components/     # ui/ (Button, Modal, ...) + domain (StatusBadge, AiReviewPanel, ...)
│   │   ├── features/       # portal/, auth/, tickets/, ai/, dashboard/, admin/
│   │   ├── styles/         # tokens.css (CSS variables), base.css
│   │   ├── App.jsx, main.jsx, router
│   └── vite.config.js      # dev proxy /api → backend (chung origin cho cookie)
├── docker-compose.yml      # db, backend, frontend
├── .env.example
├── .gitignore
├── docs/                   # SRS + spec
└── README.md
```

## 5. Kiến trúc Backend

### 5.1 Phân lớp và luồng gọi

`Router` (chỉ parse HTTP + gọi service) → `Service` (nghiệp vụ, giao dịch, ghi history/audit) → `Model/Session`. `Schemas` Pydantic validate ở biên (request đầu vào, response đầu ra). Không truyền `Session` vào router; service nhận dependency.

Dependency chính:
- `get_current_user` — giải mã JWT, nạp user, chặn inactive.
- `require_roles(*roles)` — RBAC.
- `scoped_ticket(ticket_id)` — nạp ticket + kiểm tra quyền đối tượng (agent: nhóm/được gán; manager: nhóm quản lý; admin: tất cả). Không đủ quyền → **404** (chống lộ, nhất quán FR-TIC/UC-05).
- `can_access_ticket_result`, `can_manage_user/team/sla` tương tự.

### 5.2 Quy ước response & lỗi

- Danh sách phân trang: `{items, page, page_size, total, total_pages}`.
- Lỗi: HTTP status (Bảng §8.3 SRS) + body `{error_code, message, details}` (mã theo Bảng §10.2 SRS). Exception handler toàn cục; log chi tiết kỹ thuật kèm `request_id`; **không** trả stack/SQL/token cho client.
- Conflict → client tải lại dữ liệu mới nhất.

### 5.3 Auth (S1)

Luồng: `POST /api/auth/login` → verify bcrypt (so khớp bằng `bcrypt`); sai → tăng `failed_login_count`, khóa tạm khi đạt ngưỡng (5 lần, 15 phút — cấu hình); thành công → reset counter, cấp access token + refresh token (băm lưu `refresh_tokens`), set refresh cookie. `POST /api/auth/refresh` đọc cookie → cấp access mới. `POST /api/auth/logout` → thu hồi bản ghi refresh. `GET /api/auth/me`.

Ghi audit: đăng nhập thành công, thất bại bất thường, đăng xuất (FR-AUTH-10).

## 6. Kiến trúc Frontend

### 6.1 Routing & auth state

- `AuthContext`: giữ user + access token **trong memory**; cookie refresh do trình duyệt quản lý. Khởi động gọi `/auth/me` để phục hồi phiên.
- `apiClient`: fetch wrapper; tự gọi `/auth/refresh` đúng 1 lần khi nhận 401 rồi retry; 401 lần 2 → logout. 409/403 → ném lỗi có mã để UI hiển thị thông báo + nút "tải lại".
- Route guard: công khai (`/`, `/track`), đăng nhập (`/login`), app nội bộ (`/app/...`) yêu cầu phiên; `/app/admin/*` yêu cầu ADMIN. Sau login điều hướng theo vai trò (FR-AUTH-09).

### 6.2 Trang chính (khớp SRS §7.1)

| Route | Nội dung |
|---|---|
| `/` | Public Portal — form tạo ticket (họ tên, email, tiêu đề, mô tả, tệp tùy chọn) + trang kết quả hiện mã tra cứu |
| `/track` | Tra cứu bằng mã + email; chỉ hiện thông tin công khai (không ghi chú nội bộ/AI/audit) |
| `/login` | Đăng nhập |
| `/app/dashboard` | KPI cards + biểu đồ (SVG) + lọc thời gian; scope theo vai trò |
| `/app/tickets` | Danh sách: search, filter (status/priority/category/team/assignee/SLA/time), sort, phân trang; sidebar co gập |
| `/app/tickets/:id` | Chi tiết: tiêu đề/mã/người gửi/status/priority/category, team/assignee/SLA, timeline (comment, note, history, file), composer (public/internal), AI Review Panel, dialogs đổi status + phân công |
| `/app/admin/*` | Users, Teams, SLA policies, Audit Log |

### 6.3 Design system & UX

- **Vanilla CSS + CSS variables** (`tokens.css`): màu light/dark theo `prefers-color-scheme` (+ data-theme), spacing/typography/radius. Không dùng Tailwind.
- Nhãn status/priority/AI có **chữ + màu + icon** (không chỉ màu) — accessibility.
- Mọi thao tác ghi dữ liệu: loading + chống gửi lặp; đủ 4 trạng thái **loading / empty / success / error**.
- Hành động nguy hiểm (đóng/mở lại ticket, từ chối AI, vô hiệu hóa tài khoản): **dialog xác nhận**.
- Dialog giữ focus, đóng bằng phím; điều hướng chính bằng bàn phím được; responsive từ **360 px** (bảng cuộn ngang có kiểm soát).
- UI tiếng Việt; mã nhận diện (enum, tên biến) tiếng Anh.

## 7. Thiết kế AI (S4)

### 7.1 Provider

```
class AIProvider(Protocol):
    async def generate(self, *, system_prompt, user_prompt, schema: type[BaseModel]) -> dict
```

- `GeminiProvider`: `GEMINI_MODEL` (mặc định gợi ý `gemini-2.0-flash`), gọi `generateContent` với responseSchema/JSON, `AI_TIMEOUT_SECONDS=30`, retry tối đa 1 lần **chỉ** lỗi tạm thời (429/5xx/timeout mạng) — tránh trùng kết quả bằng `input_hash` unique chèn trước khi gọi lại.
- `MockProvider`: trả JSON mẫu **xác định theo `result_type`** (đủ để test luồng pending_review → duyệt mà không cần mạng). Chọn qua `AI_PROVIDER` (`gemini` | `mock`).
- Không retry lỗi validation/quyền/prompt.

### 7.2 PII Masking

Che trước mọi lời gọi Gemini: email → `[EMAIL-1]`, số điện thoại → `[PHONE-1]`. Placeholder giữ ngữ cảnh, không cho suy ra dữ liệu gốc. Áp cho `subject`, `description`, nội dung comment public. **Không log prompt gốc, không log key.**

### 7.3 Prompt & schema

- Thư mục `ai/prompts/` với hằng số `PROMPT_VERSION` (`classify-v1`, `summarize-v1`, `draft-v1`) — lưu vào `ai_results.prompt_version`.
- System prompt nhấn mạnh: chỉ trả JSON theo schema; bỏ qua mọi chỉ dẫn nhúng trong nội dung người dùng (chống prompt injection — R-12).
- Schema Pydantic đúng SRS §8.4:
  - Classification: `category` (∈ allowlist), `priority` (LOW/MEDIUM/HIGH/URGENT), `confidence` (0–1), `reason` (1–500).
  - Summary: `problem`, `key_points[]`, `actions_taken[]`, `current_status`, `next_steps[]`, `warnings[]`.
  - DraftReply: `draft` (không rỗng), `tone`, `assumptions[]`, `warnings[]`.

### 7.4 Lưu kết quả & kiểm duyệt

- Mọi kết quả lưu bảng `ai_results` trạng thái **`PENDING_REVIEW`** (BR-08). `input_hash` = sha256(context đã mask). `context_cutoff_at` = mốc comment cuối đưa vào (FR-AIS-06).
- Review endpoints (chỉ `PENDING_REVIEW`, người có quyền trên ticket):
  - `approve`: ghi `reviewer_id`, `reviewed_at`, `status=APPROVED`; với classification cập nhật `category`/`priority` của ticket; với draft trả nội dung để FE đưa vào compose box (**chưa gửi**); summary chỉ đánh dấu đã duyệt.
  - `edit`: cho sửa trường cho phép; lưu `original_output` + `reviewed_output`, `status=EDITED`, rồi áp dụng như approve.
  - `reject`: `status=REJECTED`, `review_reason` tùy chọn, không đổi dữ liệu ticket.
- Đã duyệt không duyệt lại → `409 AI_RESULT_ALREADY_REVIEWED`. Mọi quyết định ghi audit (FR-AIR-09).
- Confidence `< 0.70` → response kèm cờ `low_confidence` để UI hiển thị cảnh báo.
- Lỗi Gemini: tạo record `FAILED` với `error_code` đã làm sạch (`AI_TIMEOUT`/`AI_INVALID_RESPONSE`/…), cho phép gọi lại; không rollback thay đổi ticket không liên quan (NFR-AVL-02).

### 7.5 Ngữ cảnh tối thiểu

- Classification: subject + description (đã mask).
- Summary/Draft: subject + description + các comment **public** (và note nội bộ nếu người yêu cầu có quyền xem — nhưng tóm tắt cho agent mặc định chỉ public để an toàn; chốt: chỉ PUBLIC) + thời điểm cutoff. Giới hạn độ dài có kiểm soát, báo `warnings` khi cắt (FR-AIS-10).

## 8. Mô hình dữ liệu

Nguồn chính: **SRS §6.3**. Triển khai đúng 11 bảng `users, support_teams, team_members, tickets, comments, attachments, ai_results, ticket_history, sla_policies, refresh_tokens, audit_logs` với kiểu UUID PK/FK, `TIMESTAMPTZ` UTC, enum PostgreSQL.

Lưu ý triển khai bổ sung (không mâu thuẫn SRS):
- `tickets.priority` NOT NULL mặc định `MEDIUM` cho ticket public (SRS ghi enum nhưng không nói default khi portal không chọn → chốt mặc định `MEDIUM`).
- `comments.author_id` FK users nullable (public future); phiên bản này mọi comment đều do user nội bộ.
- `sla_policies`: `priority` enum LOW/MEDIUM/HIGH/URGENT; ràng buộc không chồng lấn `effective_from..effective_to` cho cùng priority + `is_active` (FR-SLA, `SLA_POLICY_CONFLICT`).
- Chỉ mục: triển khai đủ 11 nhóm SRS §6.5.
- Optimistic locking: `tickets.version` int default 1, tăng mỗi lần cập nhật ghi.
- Xóa logic: `archived_at` (tickets), `deleted_at` (comments, attachments).

## 9. SLA

- Khi tạo ticket: tìm `sla_policies` active theo `priority`, `effective_from ≤ now < effective_to`; chụp `sla_policy_id` + tính `first_response_due_at` = created + `first_response_minutes`, `resolution_due_at` = created + `resolution_minutes` (24/7 — TBD-08). Nếu `pause_on_pending=true`, thời gian Pending chờ khách sẽ **tạm dừng đồng hồ SLA**, và khi chuyển về `IN_PROGRESS` deadline được bù thêm đúng khoảng đã pause (FR-SLA-07). Logic này triển khai **đầy đủ trong S2** cùng lúc với module tính SLA; cột `pause_on_pending` + chính sách được tạo sẵn từ migration S0, nhưng không có hành vi SLA nào ở S0 (S0 chỉ dựng hạ tầng).
- Comment public đầu tiên của user nội bộ → ghi `first_response_at` (nếu null). Chuyển → RESOLVED → `resolved_at`. → CLOSED → `closed_at`.
- Trạng thái SLA tính tại thời điểm truy vấn: `ON_TIME` / `DUE_SOON` (≤20% thời gian còn lại hoặc <2h — cấu hình) / `OVERDUE`.
- Chính sách SLA đổi không tự sửa deadline ticket cũ.

## 10. Lát cắt triển khai (8 lát)

Mỗi lát = một vòng `write spec? (chỉ lát 1 đủ lớn) → plan → code (TDD) → test xanh → demo`. Các lát kế tiếp nhau; lát sau không phá vỡ test lát trước.

### S0 — Nền tảng & hạ tầng
**Bàn giao:** scaffold 2 app; `docker-compose.yml` (db postgres:16 volume + backend uvicorn + frontend); migration Alembic **toàn bộ** 11 bảng + index; seed idempotent (1 admin + 2 nhóm + mỗi nhóm 1 manager + 2 agent + 4 SLA policy + ~6 ticket mẫu + 1 ai_result mẫu); `/health/live`, `/health/ready` (DB + migration), `/health/ai`; middleware `request_id` + structured logging; `.env.example`, `.gitignore`, README chạy stack.
**Test:** parse/startup smoke; health endpoint; migration khởi tạo DB sạch chạy được.
**Demo:** `docker compose up` → health OK → login admin bằng seed.

### S1 — Auth & RBAC
**Bàn giao:** login/refresh/logout/me; bcrypt + account lock; access/refresh token + cookie; RBAC deps + scope builder; UI login + route theo vai trò; audit đăng nhập.
**Test:** unit (hash/lock/scope builder) + integration (login→refresh→me→logout; tài khoản khóa).
**Demo:** admin/manager/agent đăng nhập vào đúng khu vực.

### S2 — Public Portal + Ticket core (lát lớn nhất)
**Bàn giao:** 
- Public: tạo ticket (validate §10.1, mã `TK-`, status OPEN, tính SLA), tra cứu mã+email (rate limit, chống lộ), upload tệp kèm theo allowlist.
- Nội bộ: list ticket (search/lọc/sort/phân trang server-side, scoping), chi tiết + lịch sử, cập nhật trường cho phép + optimistic lock, chuyển trạng thái (state machine §3.2.2 + mở lại kèm lý do), comments public/internal + `first_response_at`, ghi note nội bộ, attachments (upload/download có kiểm tra quyền), ticket history + audit.
- Frontend: Portal (tạo/track), danh sách ticket, chi tiết ticket (timeline + composer + đổi status).
**Test:** unit (state machine, SLA calc, file validator, code generator) + integration (public create→track AC-01/02/03, chuyển trạng thái hợp lệ/sai, comment→first_response, IDOR ticket).
**Demo:** khách gửi ticket → agent thấy trong scope → bình luận → chuyển RESOLVED.

### S3 — Nhóm & phân công
**Bàn giao:** gán nhóm/agent (FR-ASG-01..10), validate assignee ∈ team & active, Manager chỉ trong nhóm mình, lịch sử phân công, dialog assign UI; scoping danh sách theo nhóm; đánh dấu cần phân công lại khi agent bị vô hiệu hóa.
**Test:** unit + integration (manager ngoài nhóm bị chặn, assignee sai team bị chặn, đổi người phụ trách lưu history).
**Demo:** manager phân công ticket trong nhóm → agent thấy ticket được gán.

### S4 — AI engine
**Bàn giao:** PII masker; providers (gemini + mock); prompts + schema validation; endpoints classify/summarize/draft; results list/detail; approve/edit/reject; AI Review Panel UI; áp dụng vào ticket/compose box theo quy tắc §7.4; cảnh báo confidence thấp; audit.
**Test:** unit (masker, AI schema, prompt version) + integration (MockProvider: pending_review → không đổi ticket → approve cập nhật, edit lưu 2 đầu ra, reject vô hiệu, AI_INVALID_RESPONSE, timeout→FAILED).
**Demo:** agent bấm "Phân loại AI" → panel pending_review → chấp nhận → category/priority đổi; "Tạo bản nháp" → duyệt → vào ô soạn thảo → gửi thủ công.

### S5 — Dashboard & báo cáo
**Bàn giao:** `/dashboard/summary` + `/trends` (scoping theo vai trò, lọc thời gian ≤12 tháng); KPI cards (total/open/in_progress/pending/resolved+closed/overdue SLA); biểu đồ SVG theo status theo thời gian; thời gian TB phản hồi/giải quyết.
**Test:** integration (dashboard khớp dữ liệu nguồn; agent chỉ thấy scope mình).
**Demo:** admin thấy toàn hệ thống; manager thấy nhóm mình.

### S6 — Admin module
**Bàn giao:** quản lý users (tạo/sửa/vô hiệu hóa, role, chặn vô hiệu hóa admin cuối), teams + members (team_role, chặn thêm user inactive), SLA policies CRUD + chống chồng lấn, Audit Log viewer (lọc actor/action/entity/thời gian); UI admin + dialog xác nhận; audit mọi thay đổi quyền/nhóm/SLA.
**Test:** integration (email trùng 409, chặn admin cuối, SLA chồng lấn, audit tạo đủ log).
**Demo:** admin tạo user mới → gán team → đăng nhập user đó.

### S7 — Củng cố & demo
**Bàn giao:** rà soát XSS (text-render + sanitize), test bảo mật cơ bản (IDOR cross-team, XSS payload, SQL injection smoke, AC-SEC-01..06), rate limit thực chiến, responsive 360 px + accessibility sweep, review toàn bộ trạng thái loading/empty/error, sửa lỗi còn sót; kịch bản demo end-to-end viết thành `docs/demo-scenario.md`.
**Test:** security test tập trung + system smoke theo SRS §13.3.
**Demo:** toàn trình Public → Closed + luồng AI đầy đủ.

## 11. Kiểm thử

- **Unit (pytest):** state machine ticket; SLA deadline; PII masker (email/SĐT/chuỗi đặc biệt); RBAC + scope builder; AI schema validation; file validator; sinh mã ticket; tính first_response/resolved. Mục tiêu ≥80% service cốt lõi.
- **Integration:** auth+refresh trên DB thật; public create kèm tệp trong giao dịch; phân công với nhóm thật; comment→`first_response_at`; AI bằng MockProvider (timeout/JSON sai/thành công); duyệt AI → cập nhật ticket + audit; dashboard khớp nguồn; **IDOR và truy cập chéo nhóm** (NFR-SEC-15).
- DB test: PostgreSQL trong Docker (compose profile test) hoặc DB test riêng; fixture dọn giữa test.
- Frontend: unit tối thiểu cho helper/label + verify tay qua `run` skill ở mỗi lát.
- Tổ chức: thư mục `backend/tests/{unit,integration}`; chạy lệnh 1 lệnh cho toàn bộ backend.

## 12. Triển khai & môi trường

- `docker-compose.yml`: `db` (postgres:16, volume named, healthcheck) · `backend` (build từ `backend/Dockerfile`, entrypoint chờ DB → `alembic upgrade head` → seed → `uvicorn`) · `frontend` (build Vite → serve tĩnh qua nginx hoặc chạy dev; chốt: image serve tĩnh, dev dùng Vite proxy).
- Biến môi trường tối thiểu theo SRS §14.1 trong `.env.example`; `.env` không commit. `JWT_SECRET_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`, `AI_PROVIDER`…
- Seed idempotent: không tự xóa dữ liệu khi restart (SRS §14.3). Mật khẩu mặc định chỉ trong seed (đổi sau đăng nhập đầu được khuyến nghị).
- HTTPS: trong môi trường triển khai (NFR-SEC-01) — dev cục bộ HTTP; cookie `Secure` chỉ bật khi HTTPS (qua env `COOKIE_SECURE`).

## 13. Ánh xạ an toàn & điều kiện hoàn thành

- Đối chiếu nghiệm thu: AC-01..AC-10 (nghiệp vụ), AC-AI-01..11 (AI), AC-SEC-01..06 (bảo mật) — SRS §11.
- Mỗi yêu cầu coi là xong khi đủ tiêu chuẩn SRS §18 (code theo AC + RBAC backend + migration + test xanh + OpenAPI + UI đủ 4 trạng thái + không lộ PII/secret + minh chứng demo).
- Ma trận truy vết giữ nguyên theo SRS §12.

## 14. Rủi ro còn lại & giả định

- **Khối lượng lớn:** S2 là lát lớn nhất → khi viết plan có thể tách `2a public`, `2b list/detail`, `2c comments/attachments` để subagent thực thi song song an toàn.
- **Gemini key thật nhưng quota/timeout** → MockProvider + trạng thái FAILED tách biệt đã bao phủ R-04.
- **Không repo git hiện tại** → khởi tạo git ở S0 (spec này chưa commit được cho tới khi init; sẽ commit ngay sau S0).
- **Async stack** mới hơn so với nhiều tài liệu nhóm có thể tham khảo → giữ interface service rõ để viết unit test không cần DB.
