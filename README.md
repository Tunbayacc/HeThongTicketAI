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

### S3 — Nhóm & phân công

Luồng phân công được làm đầy trên nền tối thiểu của S2 (FR-ASG):

- **Người được gán phải hợp lệ**: khi gán cho một người, người đó phải là **Support Agent đang hoạt động** thuộc nhóm được chọn (`role=AGENT`, chưa bị vô hiệu hóa, còn trong nhóm). Gán sai → `400 ASSIGNEE_NOT_IN_TEAM`.
- **Phạm vi phân công**: Quản lý chỉ gán trong nhóm mình quản lý; Admin gán được toàn hệ thống; Nhân viên không được gán. Vé gán ngoài nhóm của Quản lý → `403`. Phân công **không** làm đổi trạng thái/`resolved_at` (FR-ASG-10).
- **Đổi người phụ trách**: mỗi lần gán/đổi đều ghi một dòng lịch sử `ASSIGNED` (ai gán, ai/nhóm nhận, lúc nào, lý do), giữ nguyên quá khứ (FR-ASG-07/08).
- **"Cần phân công lại"** (FR-ASG-09): nếu người phụ trách của một vé đang mở bị **vô hiệu hóa**, vé hiển thị cờ *cần phân công lại* ở danh sách + chi tiết. Cờ được **tính động** (dựa trên trạng thái người phụ trách), tự hết khi gán cho một agent đang hoạt động.
- Danh sách/detail hiển thị **tên nhóm + người phụ trách**; danh sách thêm bộ lọc **theo nhóm** (Quản lý/Admin) trong phạm vi được xem.

Demo nhanh: đăng nhập `hung.manager@example.com` (mật khẩu seed ở bảng S1) → mở vé trong `/app/tickets` → "Phân công" → chọn nhóm + agent → xem lịch sử trong "Hoạt động" → thử gán sang nhóm khác để thấy `403`. Chi tiết kỹ thuật: `docs/superpowers/plans/2026-09-02-s3-teams-assignment.md`.

### S4 — Trợ lý AI (đề xuất, con người duyệt)

Từ S4, nhân viên/quản lý/admin có **AI hỗ trợ soạn nội dung** ngay trong trang chi tiết vé — nhưng AI chỉ **đề xuất**, mọi kết quả đều phải có người duyệt trước khi áp dụng (human-in-the-loop):

- **Ba loại kết quả**: Phân loại (nhóm + ưu tiên), Tóm tắt (bối cảnh cho nhân viên), Nháp trả lời (soạn phản hồi cho khách). Nút nằm trong khối "Trợ lý AI" dưới ô phản hồi.
- **Không bao giờ tự hành động**: AI không tự gửi phản hồi, không tự phân công, không tự đổi trạng thái/đóng vé. Kết quả mới luôn ở trạng thái *Chờ duyệt*.
- **Duyệt / chỉnh sửa / từ chối**: Duyệt đề xuất thì áp dụng phân loại (ghi lịch sử + audit, tăng `version`); có thể chỉnh nhóm/ưu tiên rồi "Lưu chỉnh sửa"; từ chối thì không thay đổi gì. Với bản nháp, bấm "Đưa vào ô trả lời" để đưa nội dung xuống ô phản hồi rồi con người gửi.
- **Độ tin cậy thấp**: khi AI tự đánh giá độ tin cậy dưới ngưỡng (`AI_LOW_CONFIDENCE_THRESHOLD`, mặc định 0.70), vé gắn cảnh báo *độ tin cậy thấp* để nhân viên kiểm tra kỹ.
- **Quyền riêng tư**: trước khi gửi tới model, email/SĐT trong mô tả và bình luận công khai được **che** thành `[EMAIL-n]`/`[PHONE-n]`; bình luận nội bộ không bao giờ gửi đi. Lịch sử quá dài bị cắt kèm ghi chú.
- **Chống bùng nổ**: các endpoint tạo kết quả có giới hạn tần suất (`AI_RATE`; mặc định 30/phút). Lỗi hết thời gian/phản hồi không hợp lệ được lưu thành kết quả `Lỗi` (có mã lỗi) thay vì nuốt im.

Demo nhanh: tạo một vé ở `/` với tiêu đề về "đăng nhập/mật khẩu" → đăng nhập `hung.manager@example.com` (mật khẩu seed ở bảng S1) → mở vé → khối "Trợ lý AI" → **Phân loại tự động** → **Duyệt đề xuất** → nhóm/ưu tiên được áp dụng (xem trong "Hoạt động"). Thử **Tóm tắt AI** và **Nháp trả lời AI** → "Đưa vào ô trả lời" → Gửi. Khi có key Gemini: đặt `AI_PROVIDER=gemini` + `GEMINI_API_KEY=...` trong `.env` rồi chạy lại stack. Chi tiết kỹ thuật: `docs/superpowers/plans/2026-09-02-s4-ai-engine.md`.

### S5 — Bảng điều khiển & báo cáo

Từ S5, nhân viên/quản lý/admin mở **"Bảng điều khiển"** tại `/app/dashboard` để xem KPI, SLA và xu hướng — mỗi vai trò thấy đúng phạm vi của mình (giống danh sách vé, FR-REP-11):

| Vai trò | Phạm vi dữ liệu |
|---|---|
| Nhân viên | Vé được gán cho mình + vé của nhóm mình |
| Quản lý | Vé các nhóm mình quản lý + vé chưa gán nhóm |
| Quản trị viên | Toàn hệ thống |

- **API**: `GET /api/dashboard/summary` (Tổng + theo trạng thái · SLA: trong hạn / sắp quá hạn / quá hạn · trung bình thời gian phản hồi đầu tiên và giải quyết) và `GET /api/dashboard/trends` (số vé tạo mới theo ngày/tháng, tách theo trạng thái). Cả hai nhận `?from=YYYY-MM-DD&to=YYYY-MM-DD`; bỏ trống = 30 ngày gần nhất; `from > to` trả về `422 VALIDATION_ERROR "Khoảng thời gian không hợp lệ."`.
- **Mọi phép đếm chạy trong PostgreSQL** (GROUP BY theo ngày/tháng theo múi giờ báo cáo `Asia/Ho_Chi_Minh`), không tải vé về để đếm. Backend luôn trả về **đủ các bucket** trong khoảng đã chọn (bucket rỗng có 5 trạng thái = 0), nên biểu đồ không bị "lỗ hổng".
- **Trên giao diện**: nút nhanh 7/30/90/180/365 ngày (mặc định 30) + chọn ngày thủ công; hàng thẻ KPI; dải SLA; hàng trung bình — khi chưa có dữ liệu hiển thị **"Chưa có dữ liệu"** (giá trị `null`); biểu đồ cột chồng theo trạng thái. Lưu ý biểu đồ ghi chú rõ số vé được tính **theo trạng thái hiện tại** — không phải trạng thái tại thời điểm tạo.
- **Thông số hiệu năng (NFR-PER-06, P95 ≤ 5 s với 12 tháng dữ liệu) chưa được kiểm chứng**: hiện chỉ có smoke test chức năng (functional), chưa có performance test — đây **không phải** bằng chứng về NFR.

Demo nhanh: đăng nhập `admin@example.com` (mật khẩu seed ở bảng S1), hoặc `hung.manager@example.com` / `lan.agent@example.com` (mật khẩu seed ở bảng S1) → mở **"Bảng điều khiển"** → đổi preset khoảng thời gian hoặc chọn ngày → xem KPI/SLA/trung bình và biểu đồ xu hướng theo phạm vi của vai trò. Chi tiết kỹ thuật: `docs/superpowers/plans/2026-09-03-s5-dashboard.md`.

## Chạy backend khi đang phát triển

- DB: `docker compose up -d db`
- Backend: `cd backend; python -m venv .venv; .venv/Scripts/python -m pip install -e ".[dev]"`
- Unit test (không cần DB): `cd backend && .venv/Scripts/python -m pytest tests/unit -q`
- Integration test (cần DB đang chạy): 
  `DATABASE_URL=postgresql+asyncpg://ai_support:ai_support@localhost:5432/ai_support INTEGRATION=1 .venv/Scripts/python -m pytest tests/integration -q`

## Frontend dev

`cd frontend && npm install && npm run dev` → http://localhost:5173 (proxy `/api` → backend :8000).
