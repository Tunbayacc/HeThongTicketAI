# ĐẶC TẢ YÊU CẦU HỆ THỐNG (SYSTEM REQUIREMENTS)

> **Hệ thống hỗ trợ khách hàng có tích hợp AI (Customer Support System with AI Assistant)**  
> Phiên bản tài liệu: **1.0**  
> Nguồn căn cứ: [`documents/SRS.md`](../documents/SRS.md) & [`docs/superpowers/specs/2026-09-02-ai-customer-support-design.md`](./superpowers/specs/2026-09-02-ai-customer-support-design.md)

---

## 1. Giới thiệu & Bối cảnh hệ thống

### 1.1 Mục đích
Tài liệu này tổng hợp toàn bộ các yêu cầu nghiệp vụ, yêu cầu chức năng (**FR**), yêu cầu phi chức năng (**NFR**) và ma trận phân quyền của hệ thống Helpdesk quản lý vé hỗ trợ khách hàng tích hợp trợ lý AI theo cơ chế **Human-in-the-loop**.

### 1.2 Công nghệ cốt lõi
* **Frontend**: React 18, Vite, React Router v6, Vanilla CSS (Design Tokens, Dark/Light Theme).
* **Backend**: Python 3.11+, FastAPI (async), Pydantic v2, Uvicorn, SlowAPI.
* **Cơ sở dữ liệu & ORM**: PostgreSQL 16+, SQLAlchemy 2.0 (asyncio + asyncpg), Alembic migration.
* **AI Provider**: Google Gemini API (`v1beta/models/...:generateContent`) & MockProvider chạy offline.
* **Bảo mật**: JWT (Access Token 15 phút, Refresh Token 7 ngày HttpOnly Cookie), bcrypt băm mật khẩu, PII Regex Masking.
* **Đóng gói**: Docker & Docker Compose.

---

## 2. Phạm vi hệ thống (System Scope)

### 2.1 Trong phạm vi (In-Scope)
1. **Xác thực & phân quyền (Auth & RBAC)**: Đăng nhập nội bộ, bảo vệ chống brute-force (khóa 15 phút khi sai 5 lần), thu hồi token khi đăng xuất.
2. **Cổng công khai (Public Portal)**: Khách hàng gửi yêu cầu hỗ trợ (không cần tài khoản) và tra cứu tiến độ bằng mã vé + email xác thực.
3. **Quản lý vòng đời vé (Ticket Lifecycle)**: Tiếp nhận, xem chi tiết, phân trang, tìm kiếm, lọc đa tiêu chí, dòng thời gian (timeline), khóa lạc quan (`version`).
4. **Quy trình chuyển trạng thái vé (State Machine)**: Kiểm soát nghiêm ngặt các bước chuyển: `OPEN` → `IN_PROGRESS` / `PENDING` → `RESOLVED` → `CLOSED`.
5. **Nhóm & Phân công (Teams & Assignment)**: Quản lý nhóm hỗ trợ, phân công vé theo phạm vi quyền hạn (Data Scoping), tự động cảnh báo vé cần phân công lại khi nhân viên bị vô hiệu hóa.
6. **Trao đổi & Đính kèm (Comments & Attachments)**: Bình luận công khai gửi khách, ghi chú nội bộ, tải lên và tải xuống tệp đính kèm an toàn (PDF, PNG, JPG, WEBP, DOCX, TXT tối đa 10 MB/tệp).
7. **Trợ lý AI (AI Assistant with Human-in-the-loop)**:
   * Phân loại danh mục và mức độ ưu tiên vé.
   * Tóm tắt lịch sử trao đổi.
   * Tạo bản nháp phản hồi cho khách.
   * Kiểm duyệt kết quả: Duyệt (Approve), Chỉnh sửa (Edit), Từ chối (Reject).
8. **Quản lý cam kết dịch vụ (SLA)**: Tính toán hạn phản hồi đầu tiên và giải quyết, cảnh báo sắp quá hạn, hỗ trợ tạm dừng hạn khi chờ khách hàng (`pause_on_pending`).
9. **Bảng điều khiển & Báo cáo (Dashboard & KPI)**: Thống kê số lượng, tỷ lệ đạt SLA, thời gian phản hồi trung bình, biểu đồ xu hướng theo ngày/tháng với Data Scoping.
10. **Quản trị hệ thống (Admin Area)**: Quản lý người dùng, phân vai trò, quản trị nhóm & thành viên, cấu hình chính sách SLA, xem nhật ký kiểm toán (Audit Logs).

### 2.2 Ngoài phạm vi (Out-of-Scope)
* Chatbot tự động nhắn tin hai chiều trực tiếp với khách hàng.
* AI tự động gửi email/phản hồi mà không qua nhân viên kiểm duyệt.
* RAG, Knowledge Base, tìm kiếm tài liệu tri thức bổ sung.
* Phân tích âm thanh, video, xử lý ảnh thị giác máy tính bằng AI.
* Tổng đài thoại (Call center / VoIP), ứng dụng di động native.
* Cổng thanh toán trực tuyến, hóa đơn thương mại điện tử, quản lý giao hàng.
* Hệ thống CRM chuyên sâu (quản lý Leads, Sales Pipeline, Marketing).

---

## 3. Nhóm người dùng & Ma trận phân quyền (RBAC Matrix)

### 3.1 Các Actor trong hệ thống
* **Public User (Khách hàng)**: Không có tài khoản nội bộ; chỉ thao tác gửi yêu cầu tại Portal và tra cứu vé của chính mình.
* **Support Agent (Nhân viên hỗ trợ)**: Xử lý các vé được gán trực tiếp hoặc thuộc nhóm mình tham gia.
* **Team Manager (Quản lý nhóm)**: Quản lý thành viên trong nhóm, phân công vé, xem Dashboard và vé của nhóm mình quản lý.
* **Administrator (Quản trị viên)**: Toàn quyền quản trị hệ thống, người dùng, nhóm, chính sách SLA và xem Audit Logs.

### 3.2 Ma trận quyền chi tiết

| Chức năng | Khách hàng (Public) | Nhân viên (Agent) | Quản lý (Manager) | Quản trị viên (Admin) |
|---|:---:|:---:|:---:|:---:|
| Gửi vé qua Public Portal | ✅ | ✅ | ✅ | ✅ |
| Tra cứu tiến độ vé công khai | ✅ (Chỉ vé của mình) | ✅ | ✅ | ✅ |
| Xem danh sách vé nội bộ | ❌ | ✅ (Trong nhóm/được gán) | ✅ (Nhóm quản lý + chưa gán) | ✅ (Toàn hệ thống) |
| Xem chi tiết & lịch sử vé | ❌ | ✅ (Trong phạm vi) | ✅ (Trong phạm vi) | ✅ (Toàn hệ thống) |
| Bình luận công khai gửi khách | ❌ (Chỉ xem qua portal) | ✅ | ✅ | ✅ |
| Ghi chú nội bộ (Internal Note) | ❌ | ✅ | ✅ | ✅ |
| Chuyển trạng thái vé | ❌ | ✅ | ✅ | ✅ |
| Phân công vé cho nhóm / Agent | ❌ | ❌ | ✅ (Chỉ trong nhóm quản lý) | ✅ (Toàn hệ thống) |
| Sử dụng Trợ lý AI (Classify, Summarize, Draft) | ❌ | ✅ | ✅ | ✅ |
| Duyệt / Chỉnh sửa kết quả AI | ❌ | ✅ | ✅ | ✅ |
| Xem Dashboard & Báo cáo | ❌ | ✅ (Phạm vi cá nhân/nhóm) | ✅ (Phạm vi nhóm quản lý) | ✅ (Toàn hệ thống) |
| Quản trị người dùng & phân vai trò | ❌ | ❌ | ❌ | ✅ |
| Quản lý nhóm hỗ trợ & thành viên | ❌ | ❌ | ❌ | ✅ |
| Cấu hình chính sách SLA | ❌ | ❌ | ❌ | ✅ |
| Xem nhật ký kiểm toán (Audit Logs) | ❌ | ❌ | ❌ | ✅ |

---

## 4. Danh mục yêu cầu chức năng (Functional Requirements)

### 4.0 Xác thực & Phân quyền (Auth & RBAC)
* **FR-AUTH-01 (Must)**: Cho phép người dùng nội bộ (`AGENT, MANAGER, ADMIN`) đăng nhập bằng email hợp lệ và mật khẩu bảo mật.
* **FR-AUTH-02 (Must)**: Từ chối đăng nhập đối với tài khoản không tồn tại, bị vô hiệu hóa (`is_active = false`) hoặc đang bị tạm khóa.
* **FR-AUTH-03 (Must)**: Cấp cặp mã xác thực sau khi đăng nhập thành công: Access Token (JWT 15 phút mang `user_id, role`) và Refresh Token (7 ngày lưu mã băm SHA-256 trong Database và truyền qua HttpOnly Cookie).
* **FR-AUTH-04 (Must)**: Hỗ trợ làm mới Access Token tự động qua Refresh Token còn hiệu lực và hỗ trợ đăng xuất an toàn (thu hồi ngay Refresh Token).
* **FR-AUTH-05 (Must)**: Cơ chế chống tấn công brute-force: Tự động khóa tài khoản tạm thời 15 phút sau 5 lần đăng nhập thất bại liên tiếp; giới hạn tần suất gọi API đăng nhập (Rate Limit).
* **FR-AUTH-06 (Must)**: Kiểm soát truy cập và điều hướng giao diện chặt chẽ theo vai trò và phạm vi dữ liệu (Data Scoping), chặn triệt để hành vi leo quyền hoặc truy cập trái phép.

### 4.1 Cổng công khai (Public Portal)
* **FR-PUB-01 (Must)**: Biểu mẫu gửi vé tiếp nhận họ tên, email hợp lệ, tiêu đề, mô tả chi tiết, phân loại ban đầu và tối đa 5 tệp đính kèm.
* **FR-PUB-02 (Must)**: Vé gửi thành công được tạo ở trạng thái `OPEN`, mức ưu tiên mặc định `MEDIUM`, tính toán thời hạn SLA ngay lập tức.
* **FR-PUB-03 (Must)**: Trả về mã vé công khai ngẫu nhiên không tuần tự định dạng `TK-` + 8 ký tự Base32 (chống đoán mã vé).
* **FR-PUB-04 (Must)**: Tra cứu vé công khai bắt buộc cung cấp đúng cả mã vé (`ticket_code`) và email người gửi (`requester_email`).
* **FR-PUB-05 (Must)**: Kết quả tra cứu công khai chỉ hiển thị tiêu đề, trạng thái, thời gian tạo, phân loại, hạn giải quyết và bình luận công khai. Tuyệt đối không để lộ ghi chú nội bộ, phân công, kết quả AI hay audit logs.
* **FR-PUB-06 (Must)**: Nếu nhập sai mã vé hoặc email, hệ thống trả về thông báo lỗi chung đồng nhất để chống rò rỉ sự tồn tại của vé.
* **FR-PUB-07 (Must)**: Giới hạn tần suất (Rate Limiting) trên các endpoint gửi vé và tra cứu để chống spam/brute-force.

### 4.2 Quản lý Ticket & Vòng đời
* **FR-TIC-01 (Must)**: Danh sách ticket hỗ trợ phân trang phía máy chủ (server-side pagination), tìm kiếm theo từ khóa (mã vé, tiêu đề, tên/email khách hàng).
* **FR-TIC-02 (Must)**: Bộ lọc danh sách theo trạng thái, mức ưu tiên, phân loại, nhóm hỗ trợ, và cờ "Vé của tôi".
* **FR-TIC-03 (Must)**: Chi tiết ticket hiển thị đầy đủ thông tin khách hàng, SLA, nhóm, người phụ trách, cùng dòng thời gian (timeline) kết hợp bình luận, thay đổi trạng thái và tệp đính kèm.
* **FR-TIC-04 (Must)**: Áp dụng cơ chế khóa lạc quan (**Optimistic Locking**): Mỗi yêu cầu cập nhật hoặc chuyển trạng thái phải gửi kèm `version`, nếu không khớp trả về lỗi `409 VERSION_CONFLICT`.
* **FR-TIC-05 (Must)**: Quản lý quy trình chuyển trạng thái theo máy trạng thái (**State Machine**):
  * `OPEN` → `IN_PROGRESS`, `PENDING`
  * `IN_PROGRESS` → `PENDING`, `RESOLVED`
  * `PENDING` → `IN_PROGRESS`
  * `RESOLVED` → `CLOSED`, `IN_PROGRESS` (Mở lại vé)
  * `CLOSED` → `IN_PROGRESS` (Mở lại vé)
* **FR-TIC-06 (Must)**: Khi mở lại vé từ trạng thái `RESOLVED` hoặc `CLOSED` sang `IN_PROGRESS`, bắt buộc người dùng phải nhập lý do mở lại.

### 4.3 Phân công xử lý (Assignment)
* **FR-ASG-01 (Must)**: Quản lý và Quản trị viên có quyền phân công vé cho nhóm và nhân viên trong nhóm.
* **FR-ASG-02 (Must)**: Nhân viên được gán phải là tài khoản có vai trò `AGENT`, đang hoạt động (`is_active = true`), và là thành viên chính thức của nhóm được gán.
* **FR-ASG-03 (Must)**: Quản lý chỉ được phân công trong phạm vi các nhóm mình quản lý. Phân công trái phép trả về `403 ACCESS_DENIED`.
* **FR-ASG-04 (Must)**: Mọi thao tác gán hoặc đổi người phụ trách đều ghi một dòng lịch sử `ASSIGNED` lưu rõ ai gán, gán cho ai, vào nhóm nào, thời điểm và lý do.
* **FR-ASG-05 (Should)**: Cờ tự động **Cần phân công lại** (`needs_reassignment`): Nếu nhân viên đang phụ trách vé mở bị vô hiệu hóa tài khoản, vé tự động gắn cờ cảnh báo trên giao diện và tự biến mất khi vé được gán cho nhân viên khác đang hoạt động.

### 4.4 Trao đổi, Ghi chú & Đính kèm file
* **FR-COM-01 (Must)**: Phân biệt rõ hai loại phản hồi: **Bình luận công khai** (`PUBLIC` - gửi tới khách hàng) và **Ghi chú nội bộ** (`INTERNAL` - chỉ nhân viên/quản lý thấy).
* **FR-COM-02 (Must)**: Phản hồi công khai đầu tiên của nhân viên sẽ tự động ghi nhận mốc thời gian `first_response_at` trên vé để chốt KPI phản hồi đầu tiên của SLA.
* **FR-COM-03 (Must)**: Giới hạn tối đa 5 tệp đính kèm mỗi lần gửi, dung lượng tối đa 10 MB/tệp.
* **FR-COM-04 (Must)**: Kiểm soát chặt chẽ định dạng tệp cho phép (`PDF, PNG, JPG, JPEG, WEBP, GIF, TXT, DOCX`), từ chối tệp thực thi độc hại (`.exe, .sh, .bat...`). Lưu trữ tệp bằng tên mã hóa UUID ngoài web root, kiểm tra quyền truy cập trước khi cho phép tải về.

### 4.5 Trợ lý AI (AI Engine & Human-in-the-loop)
* **FR-AIC-01 (Must)**: **Phân loại tự động**: AI phân tích tiêu đề và mô tả vé, đề xuất nhóm danh mục (`category`), mức ưu tiên (`priority`), độ tin cậy (`confidence` từ 0.0 đến 1.0) và lý do phân tích.
* **FR-AIS-01 (Must)**: **Tóm tắt lịch sử**: AI tóm tắt nội dung trao đổi gồm vấn đề chính, điểm cốt lõi, các bước đã xử lý, trạng thái hiện tại và hướng giải quyết tiếp theo.
* **FR-AID-01 (Must)**: **Soạn bản nháp phản hồi**: AI gợi ý nội dung thư phản hồi khách hàng theo giọng điệu chuẩn mực và lưu ý kiểm tra trước khi gửi.
* **FR-AI-REV (Must)**: **Human-in-the-loop**:
  * Kết quả AI sinh ra luôn ở trạng thái **Chờ duyệt** (`PENDING_REVIEW`).
  * AI không bao giờ tự động gửi phản hồi, tự phân công hay tự đóng vé.
  * Nhân viên có quyền: **Duyệt** (`APPROVED` - áp dụng dữ liệu), **Chỉnh sửa** (`EDITED` - sửa trước khi lưu), hoặc **Từ chối** (`REJECTED`).
* **FR-AI-PRI (Must)**: Che giấu thông tin định danh cá nhân (**PII Masking**): Tự động thay thế email, số điện thoại trong nội dung bằng các thẻ định danh ẩn danh (`[EMAIL-1]`, `[PHONE-1]`) trước khi gửi sang Google Gemini API. Ghi chú nội bộ tuyệt đối không gửi sang AI.
* **FR-AI-CFD (Should)**: Cảnh báo độ tin cậy thấp nếu AI tự đánh giá `confidence < 0.70`.

### 4.6 Quản lý SLA & Báo cáo Dashboard
* **FR-SLA-01 (Must)**: Cấu hình chính sách thời hạn phản hồi đầu tiên và giải quyết theo từng mức ưu tiên (`LOW, MEDIUM, HIGH, URGENT`).
* **FR-SLA-02 (Must)**: Chặn chồng lấn thời gian hiệu lực giữa các chính sách cùng mức ưu tiên đang hoạt động (`409 SLA_POLICY_CONFLICT`).
* **FR-SLA-03 (Must)**: Tính toán tự động hạn giải quyết khi tạo vé. Hỗ trợ bù thêm thời gian khi vé ở trạng thái `PENDING` nếu chính sách có bật `pause_on_pending`.
* **FR-REP-01 (Must)**: Dashboard cung cấp các thẻ chỉ số KPI: Tổng số vé, theo trạng thái, tình trạng SLA (trong hạn, sắp quá hạn, quá hạn), thời gian xử lý trung bình.
* **FR-REP-02 (Must)**: Biểu đồ xu hướng vé theo ngày/tháng với các bộ lọc thời gian (7 ngày, 30 ngày, 90 ngày, 180 ngày, 365 ngày hoặc tùy chọn ngày).
* **FR-REP-03 (Must)**: Dữ liệu thống kê được tính toán trực tiếp trong PostgreSQL theo múi giờ `Asia/Ho_Chi_Minh` và tuân thủ chặt chẽ phân quyền dữ liệu (Data Scoping).

### 4.7 Quản trị hệ thống (Admin Module)
* **FR-ADM-01 (Must)**: Quản lý người dùng: Tạo tài khoản, đặt mật khẩu khởi tạo, chỉnh sửa thông tin, phân quyền vai trò (`AGENT, MANAGER, ADMIN`), kích hoạt hoặc vô hiệu hóa.
* **FR-ADM-02 (Must)**: Cơ chế bảo vệ quản trị viên cuối cùng: Chặn vô hiệu hóa hoặc hạ quyền tài khoản Admin duy nhất còn hoạt động trong hệ thống.
* **FR-ADM-03 (Must)**: Quản lý nhóm hỗ trợ: Tạo nhóm, thêm/xóa thành viên, phân vai trò trong nhóm (`MEMBER` hoặc `MANAGER`). Chặn thêm người dùng đang bị vô hiệu hóa vào nhóm.
* **FR-ADM-04 (Must)**: Quản lý nhật ký kiểm toán (Audit Logs): Giao diện tra cứu bất biến, lọc theo đối tượng (`USER, TEAM, SLA_POLICY, TICKET, AI, AUTH`), hành động, khoảng ngày và xem chi tiết metadata JSON.

---

## 5. Danh mục yêu cầu phi chức năng (Non-Functional Requirements)

### 5.1 Hiệu năng (Performance - NFR-PER)
* **NFR-PER-01**: Thời gian phản hồi API tra cứu, danh sách và chi tiết vé đạt P95 ≤ 500 ms trong điều kiện mạng nội bộ tiêu chuẩn.
* **NFR-PER-02**: Thời gian gọi Gemini API có timeout tối đa 30 giây; nếu vượt quá sẽ ghi nhận lỗi quá hạn (`AI_TIMEOUT`).
* **NFR-PER-03**: Truy vấn thống kê Dashboard tối ưu bằng các câu lệnh `GROUP BY` trực tiếp trong Database, không kéo toàn bộ dữ liệu về RAM của ứng dụng.

### 5.2 Bảo mật & Toàn vẹn (Security - NFR-SEC)
* **NFR-SEC-01**: Mật khẩu người dùng được băm an toàn bằng thuật toán `bcrypt` với cost factor tối thiểu 12.
* **NFR-SEC-02**: Phiên đăng nhập sử dụng Access Token (JWT 15 phút) và Refresh Token (7 ngày, lưu mã băm SHA-256 trong Database và truyền qua HttpOnly Cookie).
* **NFR-SEC-03**: Chống tấn công brute-force: Tự động khóa tài khoản tạm thời 15 phút sau 5 lần đăng nhập thất bại liên tiếp.
* **NFR-SEC-04**: Phòng chống XSS: Toàn bộ nội dung bình luận, mô tả hiển thị trên giao diện được React tự động escape; backend làm sạch dữ liệu đầu vào.
* **NFR-SEC-05**: Giới hạn tần suất (Rate Limiting) trên các endpoint nhạy cảm (Đăng nhập, Portal, gọi AI).

### 5.3 Bảo vệ quyền riêng tư (Privacy - NFR-PRI)
* **NFR-PRI-01**: Dữ liệu gửi sang bên thứ ba (Google Gemini API) bắt buộc phải che giấu thông tin định danh cá nhân (PII Masking).
* **NFR-PRI-02**: Ghi chú nội bộ (`INTERNAL`) và thông tin nhạy cảm của nhân viên không bao giờ được gửi sang dịch vụ AI ngoài hoặc hiển thị ở Public Portal.

### 5.4 Quan sát & Ghi nhật ký (Observability - NFR-OBS)
* **NFR-OBS-01**: Mọi request đi qua hệ thống đều được middleware gán một mã định danh duy nhất `request_id` để theo dõi xuyên suốt trong log.
* **NFR-OBS-02**: Mọi thay đổi dữ liệu quan trọng (đổi trạng thái, phân công, sửa vé, thay đổi quyền, thao tác AI) đều được lưu vào bảng `audit_logs` bất biến.
