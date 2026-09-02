# ĐẶC TẢ YÊU CẦU PHẦN MỀM (SRS)

## Hệ thống hỗ trợ khách hàng có tích hợp AI

---

## Thông tin tài liệu

| Thuộc tính | Giá trị |
|---|---|
| Tên tài liệu | Đặc tả yêu cầu phần mềm – Hệ thống hỗ trợ khách hàng có tích hợp AI |
| Mã tài liệu | SRS-CSAI |
| Phiên bản | 1.0 |
| Trạng thái | Bản cơ sở phục vụ thiết kế, phát triển và kiểm thử |
| Ngôn ngữ | Tiếng Việt |
| Phương pháp phát triển | Scrum |
| Kiến trúc dự kiến | React + FastAPI + PostgreSQL + Gemini API |
| Người thực hiện | La Văn Tuấn, Trần Minh Thuận |
| Ngày cập nhật | 02/09/2026 |

### Lịch sử thay đổi

| Phiên bản | Ngày | Người cập nhật | Nội dung |
|---|---|---|---|
| 1.0 | 02/09/2026 | Nhóm dự án | Khởi tạo đầy đủ đặc tả yêu cầu hệ thống |

### Quy ước mức độ ưu tiên

| Mức | Ý nghĩa |
|---|---|
| Must | Bắt buộc có trong phiên bản nghiệm thu |
| Should | Nên có; có thể lùi nếu Sprint gặp rủi ro lớn |
| Could | Cải tiến, không ảnh hưởng luồng nghiệp vụ cốt lõi |
| Won't | Không thực hiện trong phạm vi phiên bản hiện tại |

---

# 1. Giới thiệu

## 1.1. Mục đích

Tài liệu này mô tả đầy đủ các yêu cầu nghiệp vụ, yêu cầu chức năng, yêu cầu dữ liệu, giao diện, bảo mật, hiệu năng và tiêu chí nghiệm thu của Hệ thống hỗ trợ khách hàng có tích hợp AI.

Tài liệu được sử dụng làm căn cứ thống nhất giữa các thành viên dự án trong các hoạt động:

- Phân tích và xác nhận phạm vi.
- Thiết kế kiến trúc, cơ sở dữ liệu và giao diện.
- Xây dựng Backend, Frontend và tích hợp AI.
- Xây dựng test case và kiểm thử nghiệm thu.
- Theo dõi truy vết từ yêu cầu đến chức năng và kết quả kiểm thử.

SRS mô tả hệ thống ở mức yêu cầu. Các lựa chọn triển khai chi tiết có thể thay đổi nếu vẫn đáp ứng toàn bộ yêu cầu và tiêu chí nghiệm thu được nêu trong tài liệu.

## 1.2. Phạm vi sản phẩm

Hệ thống hỗ trợ tổ chức tiếp nhận và xử lý yêu cầu hỗ trợ của khách hàng theo vòng đời ticket. Khách hàng gửi yêu cầu qua Public Portal; nhân viên tiếp nhận, phân loại, trao đổi, xử lý và cập nhật trạng thái; quản lý nhóm phân công và theo dõi hoạt động của nhóm; quản trị viên quản lý người dùng, nhóm, chính sách SLA và nhật ký hệ thống.

Trí tuệ nhân tạo được tích hợp để hỗ trợ ba tác vụ:

1. Phân loại ticket theo danh mục và mức độ ưu tiên.
2. Tóm tắt lịch sử trao đổi của ticket.
3. Tạo bản nháp phản hồi cho nhân viên.

AI chỉ đóng vai trò trợ lý. AI không được tự động gửi phản hồi, tự phân công, tự đóng ticket hoặc trực tiếp ghi đè dữ liệu nghiệp vụ chính thức. Kết quả do AI sinh ra phải được người có quyền xem xét và chấp nhận, chỉnh sửa hoặc từ chối theo nguyên tắc Human-in-the-loop.

## 1.3. Mục tiêu hệ thống

- Tập trung hóa yêu cầu hỗ trợ và lịch sử trao đổi.
- Chuẩn hóa quy trình tiếp nhận, phân công, xử lý, giải quyết và đóng ticket.
- Giảm thời gian đọc và xử lý ticket dài bằng các gợi ý AI.
- Bảo đảm quyết định nghiệp vụ quan trọng luôn do con người kiểm soát.
- Phân quyền dữ liệu theo vai trò và phạm vi nhóm.
- Theo dõi thời hạn phản hồi, thời hạn giải quyết và tình trạng SLA.
- Cung cấp dữ liệu thống kê phục vụ đánh giá chất lượng hỗ trợ.
- Lưu vết các thao tác quan trọng để kiểm tra và truy cứu.

## 1.4. Đối tượng sử dụng tài liệu

- Giảng viên và người đánh giá dự án.
- Product Owner hoặc đại diện nghiệp vụ.
- Nhóm phân tích và thiết kế.
- Lập trình viên Frontend, Backend và tích hợp AI.
- Người kiểm thử.
- Người vận hành hệ thống.

## 1.5. Thuật ngữ và từ viết tắt

| Thuật ngữ | Giải thích |
|---|---|
| Ticket | Phiếu ghi nhận một yêu cầu hỗ trợ của khách hàng |
| Public Portal | Trang công khai cho phép khách hàng gửi và tra cứu yêu cầu |
| Support Agent | Nhân viên trực tiếp tiếp nhận và xử lý ticket |
| Team Manager | Quản lý nhóm hỗ trợ, có quyền xem và phân công trong nhóm phụ trách |
| Administrator | Quản trị viên có quyền quản trị toàn hệ thống |
| AI | Trí tuệ nhân tạo |
| Gemini API | Dịch vụ AI bên ngoài được hệ thống gọi để phân loại, tóm tắt và tạo bản nháp |
| Human-in-the-loop | Cơ chế bắt buộc con người kiểm duyệt kết quả AI trước khi áp dụng |
| PII | Thông tin định danh cá nhân như email, số điện thoại, số tài khoản |
| PII Masking | Che giấu hoặc thay thế PII trước khi gửi nội dung đến dịch vụ AI |
| SLA | Cam kết về thời gian phản hồi và thời gian giải quyết |
| RBAC | Kiểm soát truy cập dựa trên vai trò |
| Data Scoping | Giới hạn phạm vi dữ liệu theo người dùng hoặc nhóm |
| Audit Log | Nhật ký bất biến ghi lại các thao tác quan trọng |
| API | Giao diện lập trình ứng dụng |
| JWT | Chuẩn token dùng cho xác thực |
| P95 | 95% yêu cầu có thời gian phản hồi không vượt quá giá trị quy định |

## 1.6. Tài liệu và tiêu chuẩn tham chiếu

- IEEE/ISO/IEC 29148 – hướng dẫn đặc tả yêu cầu hệ thống và phần mềm.
- OWASP Top 10 – nhóm rủi ro bảo mật ứng dụng web.
- REST – nguyên tắc thiết kế API.
- Scrum Guide – cơ sở tổ chức quá trình phát triển lặp.
- Tài liệu thiết kế Use Case, ERD, kiến trúc và báo cáo dự án của nhóm.

---

# 2. Mô tả tổng quan

## 2.1. Bối cảnh sản phẩm

Hệ thống là một ứng dụng web gồm các thành phần chính:

| Thành phần | Công nghệ dự kiến | Trách nhiệm |
|---|---|---|
| Frontend | React, Vite, Vanilla CSS | Hiển thị giao diện, kiểm tra dữ liệu cơ bản, gọi API |
| Backend | FastAPI, Python | Xác thực, phân quyền, xử lý nghiệp vụ và cung cấp REST API |
| Validation | Pydantic | Kiểm tra cấu trúc và tính hợp lệ của Request/Response |
| Database | PostgreSQL, SQLAlchemy | Lưu trữ dữ liệu và bảo đảm toàn vẹn |
| AI Engine | Gemini API | Phân loại, tóm tắt và tạo bản nháp phản hồi |
| Authentication | JWT, bcrypt | Quản lý phiên và bảo vệ tài khoản |
| Deployment | Docker Compose | Đóng gói và chạy các thành phần |

Frontend không truy cập trực tiếp cơ sở dữ liệu hoặc Gemini API. Mọi yêu cầu phải đi qua Backend để kiểm tra xác thực, quyền hạn, dữ liệu đầu vào, che giấu PII và ghi nhật ký.

## 2.2. Ranh giới hệ thống

### 2.2.1. Bên trong phạm vi

- Xác thực và làm mới phiên người dùng nội bộ.
- Public Portal để tạo và tra cứu ticket.
- Quản lý vòng đời ticket.
- Tìm kiếm, lọc, sắp xếp và phân trang ticket.
- Quản lý nhóm hỗ trợ và thành viên nhóm.
- Phân công ticket cho nhóm và nhân viên.
- Bình luận với khách hàng và ghi chú nội bộ.
- Quản lý tệp đính kèm.
- Phân loại, tóm tắt và tạo bản nháp bằng AI.
- Kiểm duyệt kết quả AI.
- Theo dõi SLA.
- Dashboard và báo cáo thống kê cơ bản.
- Audit Log.

### 2.2.2. Ngoài phạm vi phiên bản hiện tại

- Chatbot tự động hội thoại trực tiếp với khách hàng.
- AI tự động gửi phản hồi hoặc tự động ra quyết định nghiệp vụ.
- RAG, kho tri thức, FAQ hoặc tìm kiếm tài liệu để bổ sung ngữ cảnh cho AI.
- Phân tích âm thanh, hình ảnh hoặc video bằng AI.
- Tổng đài điện thoại, mạng xã hội và ứng dụng di động riêng.
- Thanh toán, hợp đồng hoặc quản lý quan hệ khách hàng đầy đủ.
- Mô hình Customer độc lập; thông tin người gửi được lưu cùng ticket.
- Huấn luyện hoặc fine-tune mô hình AI.
- Email Gateway hai chiều trong phiên bản cơ sở; có thể bổ sung sau.

## 2.3. Nhóm người dùng và actor

| Actor | Mô tả | Phạm vi dữ liệu |
|---|---|---|
| Public User | Khách hàng hoặc người gửi yêu cầu không có tài khoản nội bộ | Tạo ticket và tra cứu ticket của mình bằng thông tin xác minh |
| Support Agent | Nhân viên hỗ trợ | Ticket thuộc nhóm mình tham gia hoặc được gán trực tiếp |
| Team Manager | Quản lý nhóm | Ticket, thành viên và thống kê trong nhóm mình quản lý |
| Administrator | Quản trị viên | Toàn bộ dữ liệu và chức năng quản trị |
| Gemini API | Hệ thống bên ngoài | Chỉ nhận phần dữ liệu cần thiết đã được che giấu PII |

## 2.4. Ma trận quyền tổng quát

| Chức năng | Public User | Support Agent | Team Manager | Administrator |
|---|---:|---:|---:|---:|
| Gửi ticket qua Public Portal | Có | Có, qua Portal | Có, qua Portal | Có, qua Portal |
| Tra cứu ticket đã gửi | Ticket của mình | Theo quyền nội bộ | Theo quyền nội bộ | Tất cả |
| Xem danh sách và chi tiết ticket | Không | Trong phạm vi | Trong nhóm quản lý | Tất cả |
| Bình luận công khai | Không trong trang nội bộ | Có | Có | Có |
| Ghi chú nội bộ | Không | Có | Có | Có |
| Thay đổi trạng thái | Không | Ticket được phép xử lý | Trong nhóm quản lý | Tất cả |
| Phân công ticket | Không | Không | Trong nhóm quản lý | Tất cả |
| Gọi chức năng AI | Không | Có | Có | Có |
| Duyệt, sửa hoặc từ chối kết quả AI | Không | Có | Có | Có |
| Xem Dashboard | Không | Dữ liệu cá nhân/phạm vi được cấp | Dữ liệu nhóm | Toàn hệ thống |
| Quản lý nhóm và người dùng | Không | Không | Xem thành viên nhóm | Có |
| Cấu hình SLA | Không | Không | Không | Có |
| Xem Audit Log | Không | Không | Không, trừ báo cáo được cấp | Có |

## 2.5. Môi trường vận hành

- Trình duyệt máy tính: phiên bản ổn định gần nhất của Chrome, Edge hoặc Firefox.
- Giao diện đáp ứng được màn hình có chiều rộng từ 360 px trở lên.
- Máy chủ hỗ trợ Docker và Docker Compose.
- Python 3.11 trở lên.
- Node.js 18 trở lên.
- PostgreSQL 14 trở lên.
- Kết nối HTTPS trong môi trường triển khai.
- Kết nối mạng ra ngoài đến Gemini API.

## 2.6. Ràng buộc thiết kế và triển khai

- Backend phải dùng FastAPI và Pydantic để kiểm tra dữ liệu.
- Frontend dùng React với Vite và Vanilla CSS; không phụ thuộc Tailwind CSS.
- Cơ sở dữ liệu chính là PostgreSQL.
- API tuân theo JSON và nguyên tắc REST.
- Không để API key hoặc thông tin bí mật trong mã nguồn.
- Mọi truy vấn dữ liệu phải đi qua ORM hoặc câu lệnh tham số hóa.
- AI chỉ sử dụng nội dung của ticket và lịch sử liên quan đã được phép; không sử dụng RAG/FAQ.
- Mọi đầu ra AI phải được lưu riêng với trạng thái chờ duyệt.
- Quyền phải được kiểm tra ở Backend; ẩn nút ở Frontend không được coi là biện pháp phân quyền.

## 2.7. Giả định và phụ thuộc

- Tổ chức có ít nhất một quản trị viên để tạo người dùng và nhóm.
- Danh mục ticket và chính sách SLA đã được cấu hình trước khi vận hành chính thức.
- Gemini API hoạt động và tài khoản dự án còn hạn mức.
- Người dùng nội bộ có địa chỉ email duy nhất.
- Đồng hồ máy chủ được đồng bộ để tính SLA và ghi log chính xác.
- Tệp tải lên được lưu trong vùng lưu trữ mà Backend kiểm soát.
- Nếu Gemini API không sẵn sàng, các chức năng quản lý ticket vẫn phải hoạt động.

---

# 3. Quy trình nghiệp vụ

## 3.1. Quy trình xử lý ticket tổng quát

1. Public User nhập họ tên, email, tiêu đề, nội dung và tệp đính kèm trên Public Portal.
2. Hệ thống kiểm tra dữ liệu, tạo mã ticket duy nhất, đặt trạng thái ban đầu là Open và bắt đầu tính SLA.
3. Nhân viên có thể yêu cầu AI phân loại. Trước khi gọi Gemini API, hệ thống che giấu PII.
4. AI đề xuất danh mục, mức độ ưu tiên, độ tin cậy và lý do; kết quả được lưu ở trạng thái pending_review.
5. Người có quyền chấp nhận, chỉnh sửa hoặc từ chối kết quả. Chỉ dữ liệu đã được con người xác nhận mới được áp dụng vào ticket.
6. Team Manager hoặc Administrator chọn nhóm và nhân viên phụ trách. Thông tin phân công được lưu vào ticket và lịch sử; ticket có thể chuyển sang In Progress.
7. Support Agent xử lý, thêm bình luận công khai hoặc ghi chú nội bộ và có thể dùng AI để tóm tắt hoặc tạo bản nháp.
8. Bản nháp AI không được gửi tự động. Nhân viên phải kiểm tra, chỉnh sửa nếu cần và chủ động gửi nội dung.
9. Khi đã xử lý xong, nhân viên chuyển ticket sang Resolved.
10. Nếu khách hàng phản hồi vấn đề chưa được xử lý, ticket được mở lại về In Progress.
11. Ticket chuyển sang Closed khi đã xác nhận hoàn tất hoặc hết thời gian chờ được quy định.
12. Mọi thay đổi quan trọng được ghi vào Ticket History và Audit Log.

## 3.2. Vòng đời trạng thái ticket

### 3.2.1. Danh sách trạng thái

| Mã trạng thái | Tên hiển thị | Ý nghĩa |
|---|---|---|
| OPEN | Mới mở | Ticket đã được tiếp nhận nhưng chưa bắt đầu xử lý |
| IN_PROGRESS | Đang xử lý | Đã có người/nhóm chịu trách nhiệm và đang xử lý |
| PENDING | Đang chờ | Đang chờ khách hàng, nhà cung cấp hoặc thông tin bên ngoài |
| RESOLVED | Đã giải quyết | Nhân viên xác định yêu cầu đã được xử lý |
| CLOSED | Đã đóng | Vòng đời ticket kết thúc |

Assigned không phải trạng thái. Việc đã phân công được biểu diễn bằng team_id, assigned_to và bản ghi lịch sử phân công. Cách này tránh trộn lẫn hai khái niệm độc lập: ticket đang ở bước xử lý nào và ticket đang do ai phụ trách.

### 3.2.2. Chuyển trạng thái hợp lệ

| Từ | Sang | Điều kiện chính |
|---|---|---|
| OPEN | IN_PROGRESS | Có nhân viên bắt đầu tiếp nhận hoặc được phân công |
| OPEN | PENDING | Ticket cần bổ sung thông tin trước khi xử lý |
| IN_PROGRESS | PENDING | Đang chờ phản hồi hoặc yếu tố bên ngoài |
| PENDING | IN_PROGRESS | Đã nhận đủ thông tin để tiếp tục |
| IN_PROGRESS | RESOLVED | Đã có nội dung xử lý/kết quả giải quyết |
| RESOLVED | IN_PROGRESS | Ticket được mở lại |
| RESOLVED | CLOSED | Đã xác nhận hoàn tất hoặc đủ điều kiện đóng |
| CLOSED | IN_PROGRESS | Chỉ người có quyền mở lại và phải nhập lý do |

Hệ thống phải từ chối mọi chuyển trạng thái không nằm trong bảng trên, trừ khi Administrator sử dụng thao tác quản trị đặc biệt có lý do và Audit Log.

## 3.3. Quy trình sử dụng AI

1. Người dùng chọn một chức năng AI trên ticket mà họ có quyền truy cập.
2. Backend kiểm tra quyền, trạng thái ticket và giới hạn tần suất.
3. Backend lấy đúng ngữ cảnh cần thiết; không gửi toàn bộ dữ liệu nếu không cần.
4. PII Masker thay email, số điện thoại và dữ liệu nhạy cảm bằng placeholder.
5. Backend tạo System Prompt, User Prompt và JSON Schema tương ứng.
6. Gemini API xử lý và trả kết quả.
7. Backend kiểm tra JSON, kiểu dữ liệu, giá trị enum và độ dài.
8. Kết quả hợp lệ được lưu thành AI Result có trạng thái pending_review.
9. Người dùng xem đầu vào đã rút gọn, kết quả, độ tin cậy hoặc cảnh báo.
10. Người dùng chấp nhận, chỉnh sửa rồi chấp nhận, hoặc từ chối.
11. Chỉ khi được duyệt, hệ thống mới áp dụng dữ liệu phân loại hoặc đưa nội dung bản nháp vào ô soạn thảo.
12. Hệ thống ghi người duyệt, thời gian, nội dung trước/sau và hành động vào Audit Log.

## 3.4. Quy trình SLA

- Khi ticket được tạo, hệ thống xác định chính sách SLA theo mức ưu tiên và danh mục hiện hành.
- Hệ thống tính hạn phản hồi đầu tiên và hạn giải quyết.
- Bình luận công khai đầu tiên của nhân viên được dùng để ghi nhận thời điểm phản hồi đầu tiên.
- Khi ticket ở Pending vì chờ khách hàng, việc tạm dừng SLA chỉ được thực hiện nếu chính sách cho phép.
- Khi ticket chuyển lại In Progress, thời gian SLA tiếp tục được tính.
- Dashboard phải phân biệt: trong hạn, sắp đến hạn và quá hạn.
- Việc thay đổi chính sách SLA không được tự ý sửa hạn của ticket cũ, trừ khi Administrator thực hiện cập nhật có chủ đích và được ghi log.

## 3.5. Quy tắc nghiệp vụ

| Mã | Quy tắc |
|---|---|
| BR-01 | Mỗi ticket có một mã công khai duy nhất, không tuần tự dễ đoán |
| BR-02 | Email người gửi là bắt buộc và phải đúng định dạng |
| BR-03 | Một ticket có tối đa một nhóm và một nhân viên phụ trách tại một thời điểm |
| BR-04 | Nhân viên được gán phải là thành viên đang hoạt động của nhóm được gán, trừ Administrator |
| BR-05 | Team Manager chỉ phân công trong nhóm mình quản lý |
| BR-06 | Ghi chú nội bộ không bao giờ được hiển thị trên Public Portal |
| BR-07 | Trạng thái phân công không được biểu diễn bằng trạng thái Assigned |
| BR-08 | Mọi kết quả AI mới tạo có trạng thái pending_review |
| BR-09 | AI không được tự gửi phản hồi, tự phân công, tự đổi trạng thái hoặc tự đóng ticket |
| BR-10 | Nội dung gửi AI phải được che giấu PII trước khi truyền |
| BR-11 | Kết quả AI sai cấu trúc không được áp dụng vào ticket |
| BR-12 | Tệp đính kèm phải được kiểm tra loại, kích thước và tên tệp |
| BR-13 | Xóa logic được ưu tiên cho dữ liệu nghiệp vụ cần truy vết |
| BR-14 | Các thay đổi quyền, phân công, trạng thái, SLA và quyết định AI phải có Audit Log |
| BR-15 | Thời gian được lưu trong cơ sở dữ liệu theo UTC và chuyển đổi khi hiển thị |

---

# 4. Yêu cầu chức năng

## 4.1. Xác thực và quản lý phiên

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-AUTH-01 | Hệ thống phải cho phép người dùng nội bộ đăng nhập bằng email và mật khẩu | Must |
| FR-AUTH-02 | Hệ thống phải từ chối tài khoản không tồn tại, bị khóa hoặc không hoạt động | Must |
| FR-AUTH-03 | Mật khẩu phải được so khớp bằng hàm băm an toàn; không lưu mật khẩu dạng rõ | Must |
| FR-AUTH-04 | Sau khi đăng nhập thành công, hệ thống phải cấp Access Token và Refresh Token | Must |
| FR-AUTH-05 | Access Token phải chứa tối thiểu user_id, role và thời hạn hết hiệu lực | Must |
| FR-AUTH-06 | Hệ thống phải hỗ trợ làm mới Access Token bằng Refresh Token còn hiệu lực | Must |
| FR-AUTH-07 | Hệ thống phải hỗ trợ đăng xuất và vô hiệu hóa Refresh Token hiện tại | Must |
| FR-AUTH-08 | Hệ thống phải khóa tạm thời hoặc giới hạn đăng nhập sau nhiều lần sai liên tiếp | Should |
| FR-AUTH-09 | Hệ thống phải điều hướng người dùng đến vùng chức năng phù hợp với vai trò | Must |
| FR-AUTH-10 | Hệ thống phải ghi log sự kiện đăng nhập thành công, thất bại bất thường và đăng xuất | Should |

## 4.2. Public Portal

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-PUB-01 | Public User phải có thể mở biểu mẫu tạo ticket mà không cần tài khoản nội bộ | Must |
| FR-PUB-02 | Biểu mẫu phải gồm họ tên, email, tiêu đề, nội dung mô tả và tệp đính kèm tùy chọn | Must |
| FR-PUB-03 | Hệ thống phải kiểm tra trường bắt buộc, định dạng email và giới hạn độ dài | Must |
| FR-PUB-04 | Hệ thống phải tạo ticket với mã duy nhất và trạng thái Open | Must |
| FR-PUB-05 | Hệ thống phải hiển thị mã tra cứu sau khi tạo ticket thành công | Must |
| FR-PUB-06 | Public User phải có thể tra cứu trạng thái ticket bằng mã ticket và email tương ứng | Must |
| FR-PUB-07 | Trang tra cứu chỉ được hiển thị bình luận công khai, không hiển thị ghi chú nội bộ, dữ liệu AI nội bộ hoặc Audit Log | Must |
| FR-PUB-08 | Hệ thống phải giới hạn tần suất tạo và tra cứu ticket để giảm spam và dò mã | Must |
| FR-PUB-09 | Thông báo lỗi trên Portal không được tiết lộ ticket có tồn tại nếu thông tin xác minh sai | Must |
| FR-PUB-10 | Hệ thống nên hỗ trợ CAPTCHA khi phát hiện hành vi bất thường | Could |

## 4.3. Quản lý ticket

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-TIC-01 | Người dùng nội bộ có quyền phải xem được danh sách ticket trong phạm vi dữ liệu của mình | Must |
| FR-TIC-02 | Danh sách phải hỗ trợ phân trang phía máy chủ | Must |
| FR-TIC-03 | Danh sách phải hỗ trợ tìm theo mã, tiêu đề, tên hoặc email người gửi | Must |
| FR-TIC-04 | Danh sách phải lọc theo trạng thái, ưu tiên, danh mục, nhóm, người phụ trách, SLA và khoảng thời gian | Must |
| FR-TIC-05 | Danh sách phải hỗ trợ sắp xếp theo ngày tạo, ngày cập nhật, ưu tiên và hạn SLA | Must |
| FR-TIC-06 | Mỗi dòng phải hiển thị tối thiểu mã, tiêu đề, người gửi, trạng thái, ưu tiên, nhóm/người phụ trách, SLA và thời gian cập nhật | Must |
| FR-TIC-07 | Người dùng có quyền phải xem được chi tiết ticket và lịch sử theo thứ tự thời gian | Must |
| FR-TIC-08 | Hệ thống phải cho phép cập nhật tiêu đề, danh mục, ưu tiên và trạng thái theo quyền | Must |
| FR-TIC-09 | Mọi thay đổi trường nghiệp vụ phải lưu giá trị cũ, giá trị mới, người thực hiện và thời gian | Must |
| FR-TIC-10 | Hệ thống phải kiểm tra chuyển trạng thái theo bảng chuyển trạng thái hợp lệ | Must |
| FR-TIC-11 | Khi mở lại ticket Closed hoặc Resolved, người dùng phải nhập lý do | Must |
| FR-TIC-12 | Hệ thống phải ngăn chỉnh sửa đồng thời làm ghi đè thay đổi mới hơn bằng version hoặc updated_at | Should |
| FR-TIC-13 | Hệ thống phải hỗ trợ xóa logic hoặc lưu trữ ticket thay vì xóa vật lý trực tiếp | Should |
| FR-TIC-14 | Ticket bị lưu trữ không xuất hiện trong danh sách mặc định nhưng vẫn có thể được quản trị viên tra cứu | Should |

## 4.4. Nhóm và phân công

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-ASG-01 | Team Manager và Administrator phải có thể gán ticket cho một nhóm hợp lệ | Must |
| FR-ASG-02 | Team Manager và Administrator phải có thể gán ticket cho một Support Agent hợp lệ | Must |
| FR-ASG-03 | Hệ thống phải kiểm tra người được gán thuộc nhóm của ticket và đang hoạt động | Must |
| FR-ASG-04 | Team Manager chỉ được phân công trong nhóm mình quản lý | Must |
| FR-ASG-05 | Administrator được phân công trên toàn hệ thống | Must |
| FR-ASG-06 | Support Agent không được tự phân công ticket cho người khác | Must |
| FR-ASG-07 | Khi phân công, hệ thống phải lưu người phân công, người/nhóm nhận, thời gian và lý do nếu có | Must |
| FR-ASG-08 | Hệ thống phải hỗ trợ đổi người phụ trách và lưu đầy đủ lịch sử | Must |
| FR-ASG-09 | Nếu người phụ trách bị vô hiệu hóa, ticket đang mở của người đó phải được đánh dấu cần phân công lại | Should |
| FR-ASG-10 | Việc phân công không tự động đồng nghĩa ticket đã giải quyết hoặc đã đóng | Must |

## 4.5. Bình luận, ghi chú và tệp đính kèm

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-COM-01 | Support Agent, Team Manager và Administrator có quyền phải thêm được bình luận công khai | Must |
| FR-COM-02 | Người dùng nội bộ có quyền phải thêm được ghi chú nội bộ | Must |
| FR-COM-03 | Mỗi bình luận phải lưu tác giả, loại hiển thị, nội dung và thời gian | Must |
| FR-COM-04 | Ghi chú nội bộ chỉ hiển thị cho người dùng nội bộ có quyền truy cập ticket | Must |
| FR-COM-05 | Hệ thống phải làm sạch nội dung hiển thị để phòng chống XSS | Must |
| FR-COM-06 | Bình luận đã gửi không được sửa âm thầm; nếu cho phép sửa phải lưu phiên bản hoặc Audit Log | Must |
| FR-COM-07 | Người dùng phải có thể tải tệp đính kèm cho ticket hoặc bình luận theo quyền | Must |
| FR-COM-08 | Hệ thống phải giới hạn tối đa 10 MB mỗi tệp và tối đa 5 tệp trong một lần gửi, có thể cấu hình | Must |
| FR-COM-09 | Hệ thống phải dùng danh sách loại tệp cho phép và từ chối tệp thực thi nguy hiểm | Must |
| FR-COM-10 | Tên tệp lưu trữ phải được chuẩn hóa; đường dẫn thật không được nhận trực tiếp từ người dùng | Must |
| FR-COM-11 | Chỉ người có quyền xem ticket mới được tải tệp đính kèm | Must |
| FR-COM-12 | Tệp bị xóa logic phải giữ metadata cần thiết cho Audit Log | Should |

## 4.6. Phân loại ticket bằng AI

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-AIC-01 | Người dùng nội bộ có quyền phải có thể yêu cầu AI phân loại một ticket | Must |
| FR-AIC-02 | Backend phải che giấu PII trước khi gửi tiêu đề và nội dung đến Gemini API | Must |
| FR-AIC-03 | AI phải trả về danh mục đề xuất, mức ưu tiên, độ tin cậy và lý do | Must |
| FR-AIC-04 | Danh mục và mức ưu tiên trả về phải thuộc tập giá trị hệ thống cho phép | Must |
| FR-AIC-05 | Độ tin cậy phải là số trong khoảng từ 0 đến 1 | Must |
| FR-AIC-06 | Kết quả phải được lưu riêng và có trạng thái pending_review | Must |
| FR-AIC-07 | Kết quả AI không được tự động cập nhật category hoặc priority của ticket | Must |
| FR-AIC-08 | Người duyệt phải có thể chấp nhận, chỉnh sửa hoặc từ chối đề xuất | Must |
| FR-AIC-09 | Khi chấp nhận, hệ thống mới cập nhật các trường đã duyệt vào ticket | Must |
| FR-AIC-10 | Hệ thống phải lưu model, prompt_version, thời gian xử lý và người yêu cầu | Must |
| FR-AIC-11 | Nếu độ tin cậy dưới ngưỡng cấu hình, giao diện phải hiển thị cảnh báo rõ ràng | Should |
| FR-AIC-12 | Hệ thống phải cho phép gọi lại nhưng không được ghi đè kết quả cũ | Must |

## 4.7. Tóm tắt lịch sử bằng AI

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-AIS-01 | Người dùng có quyền phải có thể yêu cầu AI tóm tắt lịch sử ticket | Must |
| FR-AIS-02 | Ngữ cảnh chỉ gồm dữ liệu ticket và các bình luận mà người yêu cầu được phép xem | Must |
| FR-AIS-03 | Hệ thống phải che giấu PII trước khi gọi AI | Must |
| FR-AIS-04 | Tóm tắt phải nêu vấn đề chính, nội dung quan trọng, bước đã thực hiện, trạng thái hiện tại và bước đề xuất tiếp theo | Must |
| FR-AIS-05 | Giao diện phải ghi rõ tóm tắt AI không thay thế lịch sử gốc | Must |
| FR-AIS-06 | Tóm tắt phải lưu thời điểm chụp ngữ cảnh hoặc mốc bình luận cuối cùng được sử dụng | Must |
| FR-AIS-07 | Khi ticket có bình luận mới sau thời điểm tóm tắt, hệ thống phải đánh dấu tóm tắt có thể đã cũ | Should |
| FR-AIS-08 | Tóm tắt được lưu ở pending_review và không chỉnh sửa lịch sử ticket | Must |
| FR-AIS-09 | Người dùng phải có thể chấp nhận, chỉnh sửa hoặc từ chối tóm tắt | Must |
| FR-AIS-10 | Nếu nội dung vượt giới hạn AI, Backend phải rút gọn có kiểm soát và thông báo phạm vi dữ liệu đã dùng | Should |

## 4.8. Tạo bản nháp phản hồi bằng AI

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-AID-01 | Người dùng có quyền phải có thể yêu cầu AI tạo bản nháp phản hồi | Must |
| FR-AID-02 | Người dùng có thể nhập hướng dẫn ngắn về mục tiêu hoặc giọng điệu | Should |
| FR-AID-03 | Backend chỉ gửi dữ liệu ticket cần thiết đã che giấu PII | Must |
| FR-AID-04 | AI phải trả về nội dung bản nháp và cảnh báo nếu thiếu thông tin | Must |
| FR-AID-05 | Bản nháp phải được lưu ở pending_review | Must |
| FR-AID-06 | Hệ thống không được tự gửi bản nháp cho khách hàng | Must |
| FR-AID-07 | Người dùng phải kiểm tra và có thể chỉnh sửa bản nháp trước khi sử dụng | Must |
| FR-AID-08 | Thao tác chấp nhận chỉ đưa nội dung vào vùng soạn thảo, chưa đồng nghĩa đã gửi | Must |
| FR-AID-09 | Việc gửi bình luận phải là một hành động riêng, rõ ràng của người dùng | Must |
| FR-AID-10 | Hệ thống phải lưu phiên bản AI và nội dung cuối đã được người dùng duyệt để phục vụ đánh giá | Should |

## 4.9. Kiểm duyệt kết quả AI

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-AIR-01 | Hệ thống phải có AI Review Panel trong màn hình chi tiết ticket | Must |
| FR-AIR-02 | Panel phải hiển thị loại kết quả, thời gian, model, trạng thái và nội dung đề xuất | Must |
| FR-AIR-03 | Chỉ người có quyền trên ticket mới được xem kết quả AI | Must |
| FR-AIR-04 | Chỉ kết quả pending_review mới được chấp nhận, chỉnh sửa hoặc từ chối | Must |
| FR-AIR-05 | Chấp nhận phải lưu reviewer_id và reviewed_at | Must |
| FR-AIR-06 | Chỉnh sửa rồi chấp nhận phải lưu cả đầu ra gốc và nội dung đã sửa | Must |
| FR-AIR-07 | Từ chối phải cho phép nhập lý do | Should |
| FR-AIR-08 | Kết quả đã duyệt không được duyệt lại; muốn thay đổi phải tạo kết quả mới | Must |
| FR-AIR-09 | Mọi quyết định kiểm duyệt phải được ghi Audit Log | Must |
| FR-AIR-10 | Giao diện phải phân biệt rõ nội dung do AI tạo và dữ liệu chính thức | Must |

## 4.10. Dashboard và báo cáo

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-REP-01 | Dashboard phải hiển thị tổng số ticket theo phạm vi quyền | Must |
| FR-REP-02 | Dashboard phải thống kê ticket theo trạng thái | Must |
| FR-REP-03 | Dashboard phải thống kê ticket theo mức ưu tiên và danh mục | Should |
| FR-REP-04 | Dashboard phải hiển thị số ticket trong hạn, sắp quá hạn và quá hạn SLA | Must |
| FR-REP-05 | Dashboard phải hiển thị thời gian phản hồi đầu tiên trung bình và thời gian giải quyết trung bình | Must |
| FR-REP-06 | Người dùng phải lọc thống kê theo khoảng thời gian | Must |
| FR-REP-07 | Team Manager chỉ xem thống kê của nhóm mình quản lý | Must |
| FR-REP-08 | Support Agent chỉ xem thống kê cá nhân hoặc phạm vi được cấp | Must |
| FR-REP-09 | Administrator xem được thống kê toàn hệ thống | Must |
| FR-REP-10 | Hệ thống nên hiển thị tỷ lệ kết quả AI được chấp nhận, chỉnh sửa và từ chối | Should |
| FR-REP-11 | Các truy vấn thống kê phải dùng cùng định nghĩa trạng thái và thời gian với dữ liệu chi tiết | Must |
| FR-REP-12 | Hệ thống nên hỗ trợ xuất CSV theo phạm vi quyền | Could |

## 4.11. Quản lý người dùng và nhóm

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-ADM-01 | Administrator phải có thể tạo, xem, cập nhật và vô hiệu hóa người dùng nội bộ | Must |
| FR-ADM-02 | Email tài khoản phải duy nhất | Must |
| FR-ADM-03 | Administrator phải gán vai trò Support Agent, Team Manager hoặc Administrator | Must |
| FR-ADM-04 | Hệ thống phải ngăn quản trị viên tự vô hiệu hóa tài khoản quản trị cuối cùng | Must |
| FR-ADM-05 | Administrator phải có thể tạo, cập nhật và vô hiệu hóa nhóm | Must |
| FR-ADM-06 | Administrator phải thêm hoặc xóa thành viên nhóm | Must |
| FR-ADM-07 | Hệ thống phải cho phép xác định Team Manager của từng nhóm | Must |
| FR-ADM-08 | Không được thêm người dùng không hoạt động vào nhóm | Must |
| FR-ADM-09 | Việc xóa thành viên không được xóa lịch sử xử lý trước đó | Must |
| FR-ADM-10 | Mọi thay đổi vai trò và thành viên nhóm phải được ghi Audit Log | Must |

## 4.12. SLA và Audit Log

| Mã | Yêu cầu | Ưu tiên |
|---|---|---|
| FR-SLA-01 | Administrator phải có thể cấu hình thời hạn phản hồi và giải quyết theo mức ưu tiên | Must |
| FR-SLA-02 | Chính sách SLA phải có thời gian hiệu lực và trạng thái hoạt động | Must |
| FR-SLA-03 | Khi tạo ticket, hệ thống phải chụp chính sách áp dụng và tính các deadline | Must |
| FR-SLA-04 | Hệ thống phải ghi thời điểm phản hồi đầu tiên | Must |
| FR-SLA-05 | Hệ thống phải ghi thời điểm giải quyết | Must |
| FR-SLA-06 | Hệ thống phải xác định trạng thái SLA dựa trên thời gian hiện tại và deadline | Must |
| FR-SLA-07 | Nếu hỗ trợ tạm dừng SLA ở Pending, hệ thống phải lưu từng khoảng tạm dừng | Should |
| FR-AUD-01 | Hệ thống phải ghi Audit Log cho đăng nhập quan trọng, thay đổi quyền, phân công, trạng thái, SLA và kiểm duyệt AI | Must |
| FR-AUD-02 | Mỗi log phải chứa actor, hành động, loại đối tượng, mã đối tượng, thời gian và metadata cần thiết | Must |
| FR-AUD-03 | Audit Log không được chứa mật khẩu, token, API key hoặc nội dung PII không cần thiết | Must |
| FR-AUD-04 | Người dùng thông thường không được sửa hoặc xóa Audit Log | Must |
| FR-AUD-05 | Administrator phải có thể lọc Audit Log theo actor, hành động, đối tượng và thời gian | Must |

---

# 5. Đặc tả Use Case

## 5.1. UC-01 – Đăng nhập

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Tiền điều kiện | Tài khoản tồn tại, đang hoạt động và chưa bị khóa |
| Kích hoạt | Người dùng gửi biểu mẫu đăng nhập |
| Hậu điều kiện thành công | Phiên hợp lệ được tạo; người dùng vào trang phù hợp |
| Hậu điều kiện thất bại | Không tạo phiên; lần đăng nhập sai được ghi nhận |

Luồng chính:

1. Người dùng nhập email và mật khẩu.
2. Frontend kiểm tra trường bắt buộc.
3. Backend xác thực thông tin.
4. Backend cấp Access Token và Refresh Token.
5. Frontend tải thông tin người dùng và điều hướng vào ứng dụng.

Ngoại lệ:

- Email hoặc mật khẩu sai: trả thông báo chung, không xác nhận email có tồn tại.
- Tài khoản bị khóa hoặc vô hiệu hóa: từ chối đăng nhập.
- Quá nhiều lần sai: áp dụng rate limit hoặc khóa tạm thời.

## 5.2. UC-02 – Tạo ticket từ Public Portal

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Public User |
| Tiền điều kiện | Portal hoạt động |
| Kích hoạt | Người dùng chọn gửi yêu cầu |
| Hậu điều kiện thành công | Ticket Open được tạo và mã tra cứu được trả về |

Luồng chính:

1. Người dùng nhập họ tên, email, tiêu đề và mô tả.
2. Người dùng có thể chọn tệp đính kèm.
3. Hệ thống kiểm tra dữ liệu và tệp.
4. Hệ thống tạo ticket, mã công khai và mốc SLA.
5. Hệ thống lưu tệp hợp lệ.
6. Hệ thống hiển thị kết quả và mã tra cứu.

Ngoại lệ:

- Dữ liệu thiếu hoặc sai định dạng: chỉ rõ trường cần sửa.
- Tệp không hợp lệ: từ chối tệp; không thực thi nội dung tệp.
- Vượt rate limit: yêu cầu thử lại sau.
- Lỗi lưu dữ liệu: không được tạo bản ghi ticket dở dang.

## 5.3. UC-03 – Tra cứu ticket công khai

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Public User |
| Tiền điều kiện | Ticket đã tồn tại |
| Kích hoạt | Người dùng nhập mã ticket và email |
| Hậu điều kiện | Hiển thị dữ liệu công khai nếu xác minh đúng |

Luồng chính:

1. Người dùng nhập mã ticket và email đã dùng khi gửi.
2. Hệ thống kiểm tra rate limit và thông tin.
3. Hệ thống trả trạng thái, nội dung ban đầu và các bình luận công khai.

Ngoại lệ:

- Thông tin không khớp: trả thông báo chung.
- Ticket đã lưu trữ: vẫn trả trạng thái nếu chính sách cho phép.
- Không được trả ghi chú nội bộ, kết quả AI, phân công nội bộ hoặc Audit Log.

## 5.4. UC-04 – Xem và lọc danh sách ticket

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Tiền điều kiện | Đã đăng nhập |
| Hậu điều kiện | Danh sách đúng phạm vi và bộ lọc được hiển thị |

Luồng chính:

1. Người dùng mở trang Ticket.
2. Backend xác định phạm vi dữ liệu theo vai trò và nhóm.
3. Người dùng nhập từ khóa hoặc chọn bộ lọc.
4. Backend truy vấn có phân trang và trả tổng số bản ghi.
5. Frontend hiển thị danh sách và trạng thái bộ lọc.

Ngoại lệ:

- Bộ lọc không hợp lệ: trả lỗi 422.
- Yêu cầu trang vượt giới hạn: trả trang rỗng hoặc điều chỉnh theo quy ước API.
- Không được loại bỏ Data Scoping khi người dùng thay đổi tham số lọc.

## 5.5. UC-05 – Xem chi tiết ticket

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Tiền điều kiện | Người dùng có quyền trên ticket |
| Hậu điều kiện | Chi tiết và lịch sử hợp lệ được hiển thị |

Luồng chính:

1. Người dùng chọn ticket.
2. Backend kiểm tra quyền đối tượng.
3. Hệ thống trả thông tin ticket, SLA, phân công, bình luận, tệp và lịch sử.
4. Hệ thống trả các kết quả AI mà người dùng có quyền xem.

Ngoại lệ:

- Ticket không tồn tại: trả 404.
- Ticket tồn tại nhưng ngoài phạm vi: trả 403 hoặc 404 theo chính sách chống lộ dữ liệu.

## 5.6. UC-06 – Phân công ticket

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Team Manager, Administrator |
| Tiền điều kiện | Ticket tồn tại; actor có quyền phân công |
| Hậu điều kiện | Nhóm/người phụ trách được cập nhật và có lịch sử |

Luồng chính:

1. Actor mở hộp thoại phân công.
2. Hệ thống trả danh sách nhóm và thành viên hợp lệ theo phạm vi.
3. Actor chọn nhóm, nhân viên và nhập ghi chú tùy chọn.
4. Backend kiểm tra lại quyền và quan hệ thành viên.
5. Hệ thống cập nhật phân công.
6. Nếu phù hợp, ticket chuyển từ Open sang In Progress.
7. Hệ thống ghi Ticket History và Audit Log.

Ngoại lệ:

- Nhân viên không thuộc nhóm: từ chối.
- Manager phân công ngoài nhóm quản lý: từ chối.
- Ticket đã thay đổi bởi người khác: trả xung đột và yêu cầu tải lại.

## 5.7. UC-07 – Cập nhật trạng thái

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Tiền điều kiện | Có quyền xử lý ticket |
| Hậu điều kiện | Trạng thái mới hợp lệ được lưu |

Luồng chính:

1. Actor chọn trạng thái mới.
2. Hệ thống kiểm tra phép chuyển.
3. Nếu chuyển Pending, actor chọn lý do chờ.
4. Nếu chuyển Resolved, actor nhập kết quả xử lý khi cần.
5. Backend cập nhật trạng thái và mốc SLA.
6. Hệ thống ghi lịch sử và Audit Log.

Ngoại lệ:

- Chuyển trạng thái không hợp lệ: từ chối và trả danh sách trạng thái hợp lệ.
- Mở lại ticket nhưng thiếu lý do: từ chối.

## 5.8. UC-08 – Thêm bình luận hoặc ghi chú

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Tiền điều kiện | Có quyền trên ticket |
| Hậu điều kiện | Nội dung được lưu đúng loại hiển thị |

Luồng chính:

1. Actor chọn Bình luận công khai hoặc Ghi chú nội bộ.
2. Actor nhập nội dung và chọn tệp nếu có.
3. Hệ thống kiểm tra, làm sạch dữ liệu và lưu.
4. Với bình luận công khai đầu tiên, hệ thống ghi first_response_at.
5. Giao diện cập nhật lịch sử.

Ngoại lệ:

- Nội dung rỗng và không có tệp: từ chối.
- Tệp không hợp lệ: từ chối tệp.
- Loại nội dung không phù hợp vai trò: từ chối.

## 5.9. UC-09 – Yêu cầu AI phân loại

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Actor phụ | Gemini API |
| Tiền điều kiện | Có quyền trên ticket; ticket có nội dung |
| Hậu điều kiện | AI Result loại classification ở pending_review được tạo |

Luồng chính:

1. Actor chọn Phân loại bằng AI.
2. Backend kiểm tra quyền và rate limit.
3. Backend che giấu PII và tạo prompt.
4. Gemini trả JSON theo schema.
5. Backend kiểm tra danh mục, mức ưu tiên, độ tin cậy và lý do.
6. Hệ thống lưu kết quả pending_review.
7. Frontend mở AI Review Panel.

Ngoại lệ:

- Gemini timeout: lưu trạng thái failed và cho phép thử lại.
- JSON sai: không áp dụng; ghi lỗi kỹ thuật đã làm sạch.
- Danh mục không hợp lệ: đánh dấu invalid hoặc ánh xạ theo quy tắc cấu hình, không tự đoán im lặng.

## 5.10. UC-10 – Yêu cầu AI tóm tắt

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Actor phụ | Gemini API |
| Tiền điều kiện | Ticket có lịch sử; actor có quyền |
| Hậu điều kiện | AI Result loại summary ở pending_review được tạo |

Luồng chính:

1. Actor chọn Tóm tắt lịch sử.
2. Backend lấy nội dung được phép và che giấu PII.
3. Backend ghi mốc dữ liệu cuối đã đưa vào prompt.
4. Gemini trả tóm tắt có cấu trúc.
5. Backend kiểm tra và lưu kết quả.
6. Giao diện hiển thị cảnh báo đây là nội dung AI.

Ngoại lệ:

- Lịch sử quá dài: áp dụng giới hạn có kiểm soát và thông báo phạm vi.
- Không có đủ dữ liệu: AI Result có cảnh báo thiếu thông tin.

## 5.11. UC-11 – Yêu cầu AI tạo bản nháp

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Actor phụ | Gemini API |
| Tiền điều kiện | Có quyền; ticket có thông tin cần thiết |
| Hậu điều kiện | Bản nháp pending_review được tạo, chưa gửi |

Luồng chính:

1. Actor chọn Tạo bản nháp.
2. Actor nhập hướng dẫn hoặc giọng điệu nếu cần.
3. Backend lấy ngữ cảnh, che giấu PII và gọi Gemini.
4. Backend kiểm tra, lưu kết quả pending_review.
5. Actor chuyển sang UC-12 để duyệt.

Ngoại lệ:

- AI đưa ra nội dung có cảnh báo hoặc không đủ căn cứ: giao diện hiển thị cảnh báo.
- Không có bất kỳ bước nào tự động tạo bình luận công khai.

## 5.12. UC-12 – Kiểm duyệt kết quả AI

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Tiền điều kiện | AI Result thuộc ticket được phép xem và đang pending_review |
| Hậu điều kiện | Kết quả có trạng thái approved, edited hoặc rejected |

Luồng chấp nhận:

1. Actor xem đầu ra AI.
2. Actor chọn Chấp nhận.
3. Backend kiểm tra trạng thái hiện tại.
4. Với phân loại, Backend cập nhật category và priority.
5. Với bản nháp, hệ thống đưa nội dung vào vùng soạn thảo nhưng chưa gửi.
6. Hệ thống lưu reviewer và Audit Log.

Luồng chỉnh sửa:

1. Actor sửa các trường cho phép.
2. Actor chọn Lưu và chấp nhận.
3. Hệ thống lưu đầu ra gốc, đầu ra đã sửa và áp dụng theo loại kết quả.

Luồng từ chối:

1. Actor chọn Từ chối và nhập lý do nếu cần.
2. Hệ thống chuyển trạng thái rejected, không áp dụng dữ liệu.

Ngoại lệ:

- Kết quả đã được người khác duyệt: trả xung đột 409.
- Actor mất quyền trên ticket: trả 403.

## 5.13. UC-13 – Xem Dashboard

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Support Agent, Team Manager, Administrator |
| Tiền điều kiện | Đã đăng nhập |
| Hậu điều kiện | Chỉ số đúng phạm vi và thời gian được hiển thị |

Luồng chính:

1. Actor chọn khoảng thời gian.
2. Backend áp dụng Data Scoping.
3. Backend tính số lượng, thời gian trung bình và SLA.
4. Frontend hiển thị thẻ chỉ số và biểu đồ.

Ngoại lệ:

- Khoảng thời gian quá lớn: giới hạn hoặc xử lý theo chính sách.
- Không có dữ liệu: hiển thị giá trị 0, không hiển thị lỗi.

## 5.14. UC-14 – Quản lý người dùng và nhóm

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Administrator |
| Tiền điều kiện | Đăng nhập với vai trò Administrator |
| Hậu điều kiện | Dữ liệu người dùng/nhóm hợp lệ được cập nhật và ghi log |

Luồng chính:

1. Administrator mở trang quản trị.
2. Thực hiện tạo hoặc cập nhật người dùng/nhóm.
3. Backend kiểm tra email, vai trò, trạng thái và quan hệ.
4. Hệ thống lưu thay đổi.
5. Hệ thống ghi Audit Log.

Ngoại lệ:

- Email trùng: từ chối.
- Vô hiệu hóa quản trị viên cuối cùng: từ chối.
- Xóa thành viên đang nhận ticket: cảnh báo và yêu cầu phương án phân công lại.

## 5.15. UC-15 – Quản lý SLA và xem Audit Log

| Thuộc tính | Mô tả |
|---|---|
| Actor chính | Administrator |
| Tiền điều kiện | Đăng nhập với quyền quản trị |
| Hậu điều kiện | Chính sách SLA được lưu hoặc Audit Log được truy vấn |

Luồng chính:

1. Administrator cấu hình thời hạn theo mức ưu tiên.
2. Backend kiểm tra giá trị dương và thời gian hiệu lực.
3. Chính sách mới được lưu theo phiên bản.
4. Administrator có thể lọc Audit Log theo thời gian, actor và hành động.

Ngoại lệ:

- Thời hạn không hợp lệ: từ chối.
- Hai chính sách hoạt động bị chồng lấn: từ chối hoặc yêu cầu kết thúc chính sách cũ.

---

# 6. Yêu cầu dữ liệu

## 6.1. Danh sách thực thể

| Thực thể | Mục đích |
|---|---|
| users | Tài khoản người dùng nội bộ |
| support_teams | Nhóm hỗ trợ |
| team_members | Quan hệ người dùng – nhóm và vai trò trong nhóm |
| tickets | Dữ liệu chính của yêu cầu hỗ trợ |
| comments | Bình luận công khai và ghi chú nội bộ |
| attachments | Metadata tệp đính kèm |
| ai_results | Đầu ra AI và trạng thái kiểm duyệt |
| ticket_history | Lịch sử thay đổi nghiệp vụ của ticket |
| sla_policies | Chính sách thời gian phản hồi và giải quyết |
| refresh_tokens | Quản lý phiên làm mới |
| audit_logs | Nhật ký thao tác quan trọng |

## 6.2. Quan hệ dữ liệu

- Một support_team có nhiều team_members.
- Một user có thể thuộc nhiều support_teams thông qua team_members.
- Một ticket có thể được gán cho một support_team và một user tại một thời điểm.
- Một ticket có nhiều comments, attachments, ai_results và ticket_history.
- Một comment có thể có nhiều attachments.
- Một user có thể tạo comments, yêu cầu AI, duyệt AI và thực hiện thay đổi.
- Một sla_policy có thể được áp dụng cho nhiều tickets; ticket phải lưu deadline đã tính để giữ lịch sử.
- Một user có thể có nhiều refresh_tokens.
- Audit Log tham chiếu logic đến nhiều loại đối tượng qua entity_type và entity_id.

## 6.3. Từ điển dữ liệu chính

### 6.3.1. users

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh người dùng |
| full_name | VARCHAR(100) | NOT NULL | Họ tên |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Email đăng nhập, chuẩn hóa chữ thường |
| password_hash | VARCHAR(255) | NOT NULL | Mật khẩu đã băm |
| role | ENUM | NOT NULL | AGENT, MANAGER, ADMIN |
| is_active | BOOLEAN | DEFAULT TRUE | Trạng thái tài khoản |
| failed_login_count | INTEGER | DEFAULT 0 | Số lần đăng nhập sai liên tiếp |
| locked_until | TIMESTAMPTZ | NULL | Thời điểm hết khóa |
| created_at | TIMESTAMPTZ | NOT NULL | Ngày tạo |
| updated_at | TIMESTAMPTZ | NOT NULL | Ngày cập nhật |

### 6.3.2. support_teams

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh nhóm |
| name | VARCHAR(100) | UNIQUE, NOT NULL | Tên nhóm |
| description | TEXT | NULL | Mô tả |
| is_active | BOOLEAN | DEFAULT TRUE | Trạng thái |
| created_at | TIMESTAMPTZ | NOT NULL | Ngày tạo |
| updated_at | TIMESTAMPTZ | NOT NULL | Ngày cập nhật |

### 6.3.3. team_members

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh quan hệ |
| team_id | UUID | FK support_teams.id, NOT NULL | Nhóm |
| user_id | UUID | FK users.id, NOT NULL | Thành viên |
| team_role | ENUM | NOT NULL | MEMBER hoặc MANAGER |
| joined_at | TIMESTAMPTZ | NOT NULL | Ngày tham gia |
| is_active | BOOLEAN | DEFAULT TRUE | Trạng thái thành viên |

Ràng buộc duy nhất: team_id + user_id.

### 6.3.4. tickets

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh nội bộ |
| ticket_code | VARCHAR(30) | UNIQUE, NOT NULL | Mã công khai khó đoán |
| requester_name | VARCHAR(100) | NOT NULL | Tên người gửi |
| requester_email | VARCHAR(255) | NOT NULL | Email người gửi |
| subject | VARCHAR(200) | NOT NULL | Tiêu đề |
| description | TEXT | NOT NULL | Nội dung ban đầu |
| category | VARCHAR(50) hoặc FK | NULL | Danh mục đã xác nhận |
| priority | ENUM | NOT NULL | LOW, MEDIUM, HIGH, URGENT |
| status | ENUM | NOT NULL | OPEN, IN_PROGRESS, PENDING, RESOLVED, CLOSED |
| team_id | UUID | FK support_teams.id, NULL | Nhóm phụ trách |
| assigned_to | UUID | FK users.id, NULL | Nhân viên phụ trách |
| sla_policy_id | UUID | FK sla_policies.id, NULL | Chính sách được áp dụng |
| first_response_due_at | TIMESTAMPTZ | NULL | Hạn phản hồi đầu tiên |
| resolution_due_at | TIMESTAMPTZ | NULL | Hạn giải quyết |
| first_response_at | TIMESTAMPTZ | NULL | Thời điểm phản hồi đầu tiên |
| resolved_at | TIMESTAMPTZ | NULL | Thời điểm giải quyết |
| closed_at | TIMESTAMPTZ | NULL | Thời điểm đóng |
| version | INTEGER | DEFAULT 1 | Kiểm soát cập nhật đồng thời |
| created_at | TIMESTAMPTZ | NOT NULL | Ngày tạo |
| updated_at | TIMESTAMPTZ | NOT NULL | Ngày cập nhật |
| archived_at | TIMESTAMPTZ | NULL | Ngày lưu trữ/xóa logic |

### 6.3.5. comments

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh bình luận |
| ticket_id | UUID | FK tickets.id, NOT NULL | Ticket |
| author_id | UUID | FK users.id, NULL | Người dùng nội bộ; NULL nếu nguồn công khai tương lai |
| content | TEXT | NOT NULL | Nội dung đã xử lý an toàn |
| visibility | ENUM | NOT NULL | PUBLIC hoặc INTERNAL |
| source | ENUM | NOT NULL | HUMAN hoặc AI_ASSISTED |
| ai_result_id | UUID | FK ai_results.id, NULL | Kết quả AI nguồn nếu có |
| created_at | TIMESTAMPTZ | NOT NULL | Ngày tạo |
| edited_at | TIMESTAMPTZ | NULL | Ngày sửa nếu chính sách cho phép |
| deleted_at | TIMESTAMPTZ | NULL | Xóa logic |

### 6.3.6. attachments

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh |
| ticket_id | UUID | FK tickets.id, NOT NULL | Ticket |
| comment_id | UUID | FK comments.id, NULL | Bình luận liên quan |
| original_name | VARCHAR(255) | NOT NULL | Tên hiển thị |
| stored_name | VARCHAR(255) | UNIQUE, NOT NULL | Tên lưu an toàn |
| storage_path | TEXT | NOT NULL | Đường dẫn nội bộ |
| mime_type | VARCHAR(100) | NOT NULL | Loại MIME đã kiểm tra |
| size_bytes | BIGINT | NOT NULL | Kích thước |
| checksum | VARCHAR(128) | NULL | Mã kiểm tra toàn vẹn |
| uploaded_by | UUID | FK users.id, NULL | Người tải lên |
| created_at | TIMESTAMPTZ | NOT NULL | Ngày tạo |
| deleted_at | TIMESTAMPTZ | NULL | Xóa logic |

### 6.3.7. ai_results

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh kết quả |
| ticket_id | UUID | FK tickets.id, NOT NULL | Ticket |
| requested_by | UUID | FK users.id, NOT NULL | Người yêu cầu |
| result_type | ENUM | NOT NULL | CLASSIFICATION, SUMMARY, DRAFT_REPLY |
| status | ENUM | NOT NULL | PENDING_REVIEW, APPROVED, EDITED, REJECTED, FAILED |
| model_name | VARCHAR(100) | NOT NULL | Model đã gọi |
| prompt_version | VARCHAR(30) | NOT NULL | Phiên bản prompt |
| input_hash | VARCHAR(128) | NOT NULL | Băm đầu vào đã xử lý |
| context_cutoff_at | TIMESTAMPTZ | NULL | Mốc dữ liệu cuối trong ngữ cảnh |
| original_output | JSONB | NULL | Kết quả chuẩn hóa ban đầu |
| reviewed_output | JSONB | NULL | Kết quả sau chỉnh sửa |
| confidence | NUMERIC(4,3) | NULL | Độ tin cậy cho phân loại |
| reviewer_id | UUID | FK users.id, NULL | Người duyệt |
| review_reason | TEXT | NULL | Lý do chỉnh sửa/từ chối |
| requested_at | TIMESTAMPTZ | NOT NULL | Thời điểm yêu cầu |
| completed_at | TIMESTAMPTZ | NULL | Thời điểm AI hoàn tất |
| reviewed_at | TIMESTAMPTZ | NULL | Thời điểm duyệt |
| latency_ms | INTEGER | NULL | Thời gian gọi AI |
| error_code | VARCHAR(50) | NULL | Mã lỗi đã làm sạch |

### 6.3.8. ticket_history

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh |
| ticket_id | UUID | FK tickets.id, NOT NULL | Ticket |
| changed_by | UUID | FK users.id, NULL | Người thực hiện hoặc hệ thống |
| event_type | VARCHAR(50) | NOT NULL | STATUS_CHANGED, ASSIGNED, FIELD_UPDATED... |
| field_name | VARCHAR(50) | NULL | Trường thay đổi |
| old_value | JSONB | NULL | Giá trị cũ |
| new_value | JSONB | NULL | Giá trị mới |
| reason | TEXT | NULL | Lý do |
| created_at | TIMESTAMPTZ | NOT NULL | Thời điểm |

### 6.3.9. sla_policies

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh |
| name | VARCHAR(100) | NOT NULL | Tên chính sách |
| priority | ENUM | NOT NULL | Mức ưu tiên |
| first_response_minutes | INTEGER | > 0 | Thời hạn phản hồi |
| resolution_minutes | INTEGER | > 0 | Thời hạn giải quyết |
| pause_on_pending | BOOLEAN | DEFAULT FALSE | Có tạm dừng khi Pending |
| effective_from | TIMESTAMPTZ | NOT NULL | Bắt đầu hiệu lực |
| effective_to | TIMESTAMPTZ | NULL | Kết thúc hiệu lực |
| is_active | BOOLEAN | DEFAULT TRUE | Trạng thái |

### 6.3.10. refresh_tokens

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh phiên |
| user_id | UUID | FK users.id, NOT NULL | Chủ phiên |
| token_hash | VARCHAR(255) | UNIQUE, NOT NULL | Băm Refresh Token |
| expires_at | TIMESTAMPTZ | NOT NULL | Hết hạn |
| revoked_at | TIMESTAMPTZ | NULL | Thu hồi |
| created_at | TIMESTAMPTZ | NOT NULL | Ngày tạo |
| user_agent | TEXT | NULL | Thông tin thiết bị đã rút gọn |
| ip_address | INET | NULL | IP theo chính sách riêng tư |

### 6.3.11. audit_logs

| Trường | Kiểu gợi ý | Ràng buộc | Mô tả |
|---|---|---|---|
| id | UUID | PK | Định danh |
| actor_id | UUID | FK users.id, NULL | Người hoặc hệ thống thực hiện |
| action | VARCHAR(100) | NOT NULL | Hành động |
| entity_type | VARCHAR(50) | NOT NULL | Loại đối tượng |
| entity_id | UUID | NULL | Định danh đối tượng |
| outcome | ENUM | NOT NULL | SUCCESS hoặc FAILURE |
| metadata | JSONB | NULL | Dữ liệu đã lọc bí mật/PII |
| ip_address | INET | NULL | IP nếu chính sách cho phép |
| created_at | TIMESTAMPTZ | NOT NULL | Thời điểm |

## 6.4. Ràng buộc toàn vẹn

- Không cho phép ticket tham chiếu nhóm hoặc người dùng không tồn tại.
- Nếu assigned_to khác NULL và team_id khác NULL, assigned_to phải là thành viên hoạt động của team_id, trừ thao tác Administrator có quy tắc riêng.
- priority và status chỉ nhận giá trị enum hợp lệ.
- confidence phải nằm trong khoảng 0 đến 1.
- reviewed_at và reviewer_id chỉ có khi kết quả đã được duyệt hoặc từ chối.
- resolution_due_at không được sớm hơn created_at.
- resolved_at không được sớm hơn created_at.
- Comment INTERNAL không được trả qua API công khai.
- Email phải được chuẩn hóa trước khi so sánh và lưu.
- Mọi bản ghi nghiệp vụ phải dùng timestamp có múi giờ.

## 6.5. Chỉ mục đề xuất

- tickets(ticket_code) duy nhất.
- tickets(status, updated_at).
- tickets(team_id, status, updated_at).
- tickets(assigned_to, status, updated_at).
- tickets(priority, resolution_due_at).
- tickets(requester_email).
- comments(ticket_id, created_at).
- ai_results(ticket_id, result_type, status, requested_at).
- ticket_history(ticket_id, created_at).
- audit_logs(created_at), audit_logs(actor_id, created_at), audit_logs(entity_type, entity_id).
- team_members(team_id, user_id) duy nhất.

## 6.6. Lưu trữ và vòng đời dữ liệu

- Ticket, bình luận, lịch sử và quyết định AI phải được lưu tối thiểu theo chính sách của tổ chức; giá trị mặc định đề xuất là 12 tháng.
- Audit Log đề xuất lưu tối thiểu 12 tháng và không cho người dùng ứng dụng sửa.
- Refresh Token hết hạn hoặc bị thu hồi có thể được dọn định kỳ sau thời gian an toàn.
- Tệp đính kèm xóa logic được dọn vật lý theo tác vụ nền và chính sách lưu trữ.
- Dữ liệu sao lưu phải được mã hóa và kiểm soát quyền truy cập.
- Yêu cầu xóa dữ liệu cá nhân phải cân bằng với nghĩa vụ lưu vết; có thể ẩn danh hóa thay vì xóa toàn bộ lịch sử.

---

# 7. Yêu cầu giao diện

## 7.1. Giao diện người dùng

### 7.1.1. Màn hình đăng nhập

- Trường email và mật khẩu.
- Nút đăng nhập.
- Thông báo lỗi chung, không tiết lộ email tồn tại.
- Trạng thái đang xử lý để ngăn gửi lặp.
- Điều hướng theo vai trò sau đăng nhập.

### 7.1.2. Dashboard

- Thẻ tổng ticket, Open, In Progress, Pending, Resolved/Closed và quá hạn SLA.
- Biểu đồ ticket theo trạng thái và thời gian.
- Thống kê thời gian phản hồi, thời gian giải quyết.
- Bộ lọc thời gian.
- Chỉ hiển thị dữ liệu đúng phạm vi quyền.

### 7.1.3. Danh sách ticket

- Ô tìm kiếm.
- Bộ lọc trạng thái, ưu tiên, danh mục, nhóm, nhân viên, SLA và thời gian.
- Nút xóa bộ lọc.
- Bảng dữ liệu có phân trang.
- Nhãn màu phải đi kèm chữ hoặc biểu tượng; không chỉ dựa vào màu.
- Sidebar có thể co gập nhưng không làm mất chức năng.

### 7.1.4. Chi tiết ticket

- Tiêu đề, mã, người gửi, trạng thái, ưu tiên, danh mục.
- Thông tin nhóm, người phụ trách và SLA.
- Dòng thời gian bình luận, ghi chú, thay đổi và tệp.
- Vùng nhập bình luận/ghi chú.
- Các nút AI phân loại, tóm tắt và tạo bản nháp.
- AI Review Panel thể hiện rõ nguồn AI và trạng thái duyệt.
- Nút thay đổi trạng thái và phân công theo quyền.

### 7.1.5. Quản trị

- Danh sách và biểu mẫu người dùng.
- Danh sách nhóm và thành viên.
- Cấu hình SLA có kiểm tra giá trị.
- Trang Audit Log chỉ đọc, có bộ lọc.

### 7.1.6. Public Portal

- Trang tạo ticket đơn giản, không yêu cầu kiến thức nội bộ.
- Trang kết quả có mã tra cứu và hướng dẫn lưu mã.
- Trang tra cứu yêu cầu mã và email.
- Không hiển thị thông tin phân công, ghi chú nội bộ, dữ liệu AI hoặc Audit Log.

## 7.2. Quy tắc trải nghiệm người dùng

- Mọi hành động làm thay đổi dữ liệu phải có trạng thái loading và ngăn gửi lặp.
- Thao tác đóng, mở lại, từ chối AI hoặc vô hiệu hóa tài khoản phải yêu cầu xác nhận.
- Lỗi kiểm tra dữ liệu phải hiển thị gần trường liên quan.
- Sau thao tác thành công phải có thông báo và cập nhật dữ liệu trên màn hình.
- Khi dữ liệu đã bị người khác sửa, giao diện phải yêu cầu tải lại thay vì âm thầm ghi đè.
- Nút không có quyền phải được ẩn hoặc vô hiệu hóa, đồng thời Backend vẫn phải kiểm tra quyền.

## 7.3. Khả năng tiếp cận

- Có thể sử dụng các chức năng chính bằng bàn phím.
- Thành phần biểu mẫu có label rõ ràng.
- Focus phải nhìn thấy được.
- Độ tương phản văn bản đáp ứng mức AA khi khả thi.
- Thông báo lỗi không chỉ thể hiện bằng màu.
- Hộp thoại phải giữ focus và có thể đóng bằng bàn phím.

---

# 8. Yêu cầu API và tích hợp

## 8.1. Quy ước REST API

- Base path: /api.
- Request và Response dùng application/json, trừ tải tệp.
- Dùng UUID cho định danh nội bộ.
- Thời gian trả theo ISO 8601 và UTC.
- Danh sách phân trang trả items, page, page_size, total và total_pages.
- Lỗi trả error_code, message và details đã làm sạch.
- Không trả stack trace, câu SQL, token hoặc API key cho client.
- Các endpoint nội bộ yêu cầu Bearer Access Token hợp lệ.

## 8.2. Danh sách endpoint đề xuất

### 8.2.1. Xác thực

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| POST | /api/auth/login | Đăng nhập |
| POST | /api/auth/refresh | Làm mới Access Token |
| POST | /api/auth/logout | Thu hồi phiên hiện tại |
| GET | /api/auth/me | Lấy thông tin người dùng hiện tại |

### 8.2.2. Public Portal

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| POST | /api/public/tickets | Tạo ticket công khai |
| POST | /api/public/tickets/track | Tra cứu bằng mã và email |

### 8.2.3. Ticket và trao đổi

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| GET | /api/tickets | Danh sách, tìm kiếm và lọc |
| GET | /api/tickets/{ticket_id} | Chi tiết ticket |
| POST | /api/tickets | Tạo ticket nội bộ nếu được bật |
| PATCH | /api/tickets/{ticket_id} | Cập nhật trường cho phép |
| PATCH | /api/tickets/{ticket_id}/status | Chuyển trạng thái |
| POST | /api/tickets/{ticket_id}/assign | Phân công |
| GET | /api/tickets/{ticket_id}/comments | Danh sách bình luận |
| POST | /api/tickets/{ticket_id}/comments | Tạo bình luận hoặc ghi chú |
| POST | /api/tickets/{ticket_id}/attachments | Tải tệp |
| GET | /api/attachments/{attachment_id}/download | Tải tệp có kiểm tra quyền |
| GET | /api/tickets/{ticket_id}/history | Lịch sử thay đổi |

### 8.2.4. AI

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| POST | /api/ai/tickets/{ticket_id}/classify | Yêu cầu phân loại |
| POST | /api/ai/tickets/{ticket_id}/summarize | Yêu cầu tóm tắt |
| POST | /api/ai/tickets/{ticket_id}/draft-reply | Yêu cầu bản nháp |
| GET | /api/ai/tickets/{ticket_id}/results | Danh sách kết quả AI |
| GET | /api/ai/results/{result_id} | Chi tiết kết quả |
| POST | /api/ai/results/{result_id}/approve | Chấp nhận |
| POST | /api/ai/results/{result_id}/edit | Chỉnh sửa và chấp nhận |
| POST | /api/ai/results/{result_id}/reject | Từ chối |

### 8.2.5. Quản trị và báo cáo

| Phương thức | Endpoint | Chức năng |
|---|---|---|
| GET/POST | /api/users | Danh sách/tạo người dùng |
| GET/PATCH | /api/users/{user_id} | Xem/cập nhật người dùng |
| GET/POST | /api/teams | Danh sách/tạo nhóm |
| GET/PATCH | /api/teams/{team_id} | Xem/cập nhật nhóm |
| POST | /api/teams/{team_id}/members | Thêm thành viên |
| DELETE | /api/teams/{team_id}/members/{user_id} | Vô hiệu hóa quan hệ thành viên |
| GET/POST | /api/sla-policies | Xem/tạo chính sách SLA |
| PATCH | /api/sla-policies/{policy_id} | Cập nhật trạng thái chính sách |
| GET | /api/dashboard/summary | Chỉ số tổng quan |
| GET | /api/dashboard/trends | Xu hướng theo thời gian |
| GET | /api/audit-logs | Tra cứu Audit Log |

## 8.3. Mã trạng thái HTTP

| Mã | Trường hợp |
|---:|---|
| 200 | Đọc hoặc cập nhật thành công |
| 201 | Tạo mới thành công |
| 204 | Xóa logic/thu hồi thành công không cần body |
| 400 | Yêu cầu sai nghiệp vụ |
| 401 | Chưa xác thực hoặc token không hợp lệ |
| 403 | Đã xác thực nhưng không có quyền |
| 404 | Không tìm thấy hoặc cố ý che đối tượng ngoài phạm vi |
| 409 | Xung đột phiên bản, email trùng hoặc kết quả AI đã được duyệt |
| 413 | Tệp hoặc request quá lớn |
| 415 | Loại nội dung/tệp không hỗ trợ |
| 422 | Dữ liệu không đạt validation |
| 429 | Vượt giới hạn tần suất |
| 500 | Lỗi nội bộ đã được che thông tin |
| 502/503/504 | Dịch vụ AI bên ngoài lỗi, không sẵn sàng hoặc timeout |

## 8.4. Schema đầu ra AI

### 8.4.1. Phân loại

Các trường bắt buộc:

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| category | string | Thuộc danh sách danh mục cho phép |
| priority | string | LOW, MEDIUM, HIGH hoặc URGENT |
| confidence | number | Từ 0 đến 1 |
| reason | string | 1 đến 500 ký tự |

Ví dụ logic:

    {
      "category": "TECHNICAL",
      "priority": "HIGH",
      "confidence": 0.87,
      "reason": "Người dùng không thể đăng nhập và công việc đang bị gián đoạn."
    }

### 8.4.2. Tóm tắt

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| problem | string | Vấn đề chính |
| key_points | array[string] | Các điểm quan trọng |
| actions_taken | array[string] | Các bước đã thực hiện |
| current_status | string | Trạng thái theo ngữ cảnh |
| next_steps | array[string] | Bước tiếp theo đề xuất |
| warnings | array[string] | Dữ liệu thiếu hoặc không chắc chắn |

### 8.4.3. Bản nháp phản hồi

| Trường | Kiểu | Ràng buộc |
|---|---|---|
| draft | string | Nội dung dự thảo, không rỗng |
| tone | string | Giọng điệu đã sử dụng |
| assumptions | array[string] | Giả định của AI |
| warnings | array[string] | Cảnh báo thiếu thông tin |

## 8.5. Tích hợp Gemini API

- API key chỉ được đọc từ biến môi trường hoặc kho bí mật.
- Backend phải đặt timeout; giá trị đề xuất là 30 giây.
- Chỉ retry tối đa một lần với lỗi tạm thời và phải tránh tạo kết quả trùng.
- Không retry lỗi validation, lỗi quyền hoặc lỗi do prompt.
- Phải ghi model_name, prompt_version, latency_ms và trạng thái gọi.
- Log không được chứa nguyên văn prompt có PII hoặc API key.
- Khi Gemini lỗi, hệ thống trả thông báo có thể hiểu và không ảnh hưởng dữ liệu ticket.
- Kết quả raw phải được chuẩn hóa và kiểm tra trước khi lưu/hiển thị.
- Tệp nhị phân không được gửi trực tiếp cho AI trong phiên bản hiện tại.

---

# 9. Yêu cầu phi chức năng

## 9.1. Bảo mật

| Mã | Yêu cầu có thể kiểm thử |
|---|---|
| NFR-SEC-01 | Mọi kết nối trong môi trường triển khai phải dùng HTTPS |
| NFR-SEC-02 | Mật khẩu phải được băm bằng bcrypt với cost phù hợp, đề xuất 12 trở lên tùy năng lực máy chủ |
| NFR-SEC-03 | Access Token có thời hạn ngắn, đề xuất 15 phút |
| NFR-SEC-04 | Refresh Token có thời hạn tối đa đề xuất 7 ngày, được lưu dạng băm và có thể thu hồi |
| NFR-SEC-05 | Nếu dùng cookie cho Refresh Token, cookie phải có HttpOnly, Secure và SameSite phù hợp kiến trúc triển khai |
| NFR-SEC-06 | Backend phải kiểm tra RBAC và Data Scoping ở mọi endpoint có dữ liệu bảo vệ |
| NFR-SEC-07 | Hệ thống phải chống IDOR bằng kiểm tra quyền trên từng ticket, comment, attachment và AI Result |
| NFR-SEC-08 | Dữ liệu đầu vào phải được kiểm tra bằng schema và nội dung hiển thị phải được chống XSS |
| NFR-SEC-09 | Truy vấn cơ sở dữ liệu phải được tham số hóa |
| NFR-SEC-10 | Public endpoint và endpoint AI phải có rate limiting |
| NFR-SEC-11 | Tệp tải lên phải được kiểm tra phần mở rộng, MIME, kích thước và tên an toàn |
| NFR-SEC-12 | Bí mật không được commit vào Git hoặc trả cho client |
| NFR-SEC-13 | Thông báo lỗi không được lộ stack trace, cấu trúc hệ thống hoặc dữ liệu nhạy cảm |
| NFR-SEC-14 | Thay đổi vai trò, nhóm, SLA, phân công, trạng thái và AI review phải có Audit Log |
| NFR-SEC-15 | Hệ thống phải có kiểm thử cho truy cập chéo nhóm và truy cập đối tượng trực tiếp |

## 9.2. Riêng tư và bảo vệ dữ liệu

| Mã | Yêu cầu |
|---|---|
| NFR-PRI-01 | Chỉ thu thập dữ liệu cần thiết để xử lý yêu cầu |
| NFR-PRI-02 | PII phải được che giấu trước mọi lời gọi Gemini |
| NFR-PRI-03 | Placeholder phải giữ đủ ngữ cảnh nhưng không cho phép suy ra dữ liệu gốc khi không cần |
| NFR-PRI-04 | Không ghi token, mật khẩu, API key hoặc PII đầy đủ vào log |
| NFR-PRI-05 | Public Portal chỉ trả dữ liệu tối thiểu sau khi xác minh mã và email |
| NFR-PRI-06 | Giao diện phải thông báo AI được sử dụng để hỗ trợ xử lý nội dung |
| NFR-PRI-07 | Quyền truy cập dữ liệu sao lưu phải hạn chế cho người vận hành được ủy quyền |

## 9.3. Hiệu năng

Các chỉ tiêu sau là mục tiêu nghiệm thu trong môi trường kiểm thử đã mô tả, không phải số liệu đã đo nếu chưa có báo cáo kiểm thử.

| Mã | Chỉ tiêu |
|---|---|
| NFR-PER-01 | API không gọi AI có thời gian phản hồi P95 không quá 2 giây với 50 người dùng đồng thời |
| NFR-PER-02 | Trang danh sách ticket P95 không quá 2 giây với 50.000 ticket và bộ lọc có chỉ mục |
| NFR-PER-03 | Đăng nhập P95 không quá 3 giây, không tính độ trễ mạng phía người dùng |
| NFR-PER-04 | Thao tác AI có thời gian phản hồi mục tiêu P95 không quá 20 giây với ngữ cảnh trong giới hạn |
| NFR-PER-05 | Lời gọi AI phải timeout không quá 30 giây |
| NFR-PER-06 | Dashboard cho khoảng thời gian 12 tháng có P95 không quá 5 giây |
| NFR-PER-07 | Phân trang mặc định 20 bản ghi và tối đa 100 bản ghi mỗi trang |

## 9.4. Tính sẵn sàng và khả năng phục hồi

| Mã | Yêu cầu |
|---|---|
| NFR-AVL-01 | Mục tiêu sẵn sàng là 99% theo tháng, không tính thời gian bảo trì đã thông báo |
| NFR-AVL-02 | Lỗi Gemini không được làm gián đoạn tạo, xem, bình luận hoặc cập nhật ticket |
| NFR-AVL-03 | Giao dịch nhiều bước phải rollback nếu một bước bắt buộc thất bại |
| NFR-AVL-04 | Hệ thống phải sao lưu cơ sở dữ liệu tối thiểu mỗi ngày |
| NFR-AVL-05 | Mục tiêu RPO là 24 giờ và RTO là 4 giờ cho phiên bản dự án |
| NFR-AVL-06 | Tác vụ dọn token và tệp phải có khả năng chạy lại an toàn |

## 9.5. Khả năng mở rộng

| Mã | Yêu cầu |
|---|---|
| NFR-SCA-01 | Backend phải stateless đối với Access Token để có thể chạy nhiều instance |
| NFR-SCA-02 | Danh sách lớn phải phân trang phía máy chủ |
| NFR-SCA-03 | Các cột lọc phổ biến phải có chỉ mục |
| NFR-SCA-04 | Tệp không nên lưu trực tiếp trong bảng PostgreSQL; chỉ lưu metadata và vị trí |
| NFR-SCA-05 | Module AI phải tách khỏi nghiệp vụ ticket qua service interface để có thể thay model |

## 9.6. Khả năng bảo trì

| Mã | Yêu cầu |
|---|---|
| NFR-MAI-01 | Mã nguồn tách api, core, models, schemas và services |
| NFR-MAI-02 | Logic Gemini, PII Masking và Ticket Service phải tách thành module |
| NFR-MAI-03 | Cấu hình theo môi trường; không hard-code URL, key hoặc mật khẩu |
| NFR-MAI-04 | Thay đổi lược đồ phải được quản lý bằng migration |
| NFR-MAI-05 | API phải có tài liệu OpenAPI do FastAPI sinh và được rà soát |
| NFR-MAI-06 | Các hàm nghiệp vụ cốt lõi phải có unit test |
| NFR-MAI-07 | Prompt AI phải có version và test schema |

## 9.7. Khả năng quan sát

| Mã | Yêu cầu |
|---|---|
| NFR-OBS-01 | Mỗi request phải có request_id để truy vết |
| NFR-OBS-02 | Log phải ở dạng có cấu trúc, gồm thời gian, mức độ, request_id và mã lỗi |
| NFR-OBS-03 | Phải theo dõi tỷ lệ lỗi, độ trễ API, độ trễ AI và số lần AI timeout |
| NFR-OBS-04 | Health check phải phân biệt tình trạng ứng dụng, database và phụ thuộc AI |
| NFR-OBS-05 | Audit Log nghiệp vụ phải tách khỏi log kỹ thuật |

## 9.8. Tính tương thích và khả dụng

| Mã | Yêu cầu |
|---|---|
| NFR-USA-01 | Giao diện phải hoạt động trên Chrome, Edge và Firefox phiên bản ổn định gần nhất |
| NFR-USA-02 | Giao diện phải dùng được từ chiều rộng 360 px; bảng có thể cuộn ngang có kiểm soát |
| NFR-USA-03 | Một người dùng mới phải có thể tạo ticket công khai mà không cần hướng dẫn ngoài |
| NFR-USA-04 | Các thuật ngữ trạng thái, ưu tiên và AI phải nhất quán trên toàn hệ thống |
| NFR-USA-05 | Giao diện phải phản hồi thao tác trong 100 ms bằng trạng thái hình ảnh, ngay cả khi xử lý Backend lâu hơn |

---

# 10. Kiểm tra dữ liệu và xử lý lỗi

## 10.1. Quy tắc validation

| Dữ liệu | Quy tắc |
|---|---|
| Họ tên người gửi | Bắt buộc; 2–100 ký tự; loại bỏ khoảng trắng thừa |
| Email | Bắt buộc; đúng định dạng; tối đa 255 ký tự; chuẩn hóa chữ thường |
| Tiêu đề | Bắt buộc; 5–200 ký tự |
| Mô tả | Bắt buộc; 10–20.000 ký tự |
| Bình luận | 1–10.000 ký tự nếu không có tệp |
| Mật khẩu | Tối thiểu 8 ký tự; chính sách mạnh hơn có thể cấu hình |
| Page | Số nguyên từ 1 |
| Page size | Số nguyên từ 1 đến 100 |
| Confidence | Số từ 0 đến 1 |
| SLA minutes | Số nguyên dương |
| Trạng thái/ưu tiên | Thuộc enum cho phép |
| Tệp | Tối đa 10 MB/tệp; tối đa 5 tệp/lần; loại nằm trong allowlist |

Validation ở Frontend nhằm hỗ trợ trải nghiệm. Backend là nơi quyết định cuối cùng và phải lặp lại toàn bộ kiểm tra quan trọng.

## 10.2. Mã lỗi nghiệp vụ đề xuất

| Mã lỗi | Ý nghĩa |
|---|---|
| AUTH_INVALID_CREDENTIALS | Thông tin đăng nhập không hợp lệ |
| AUTH_ACCOUNT_LOCKED | Tài khoản bị khóa tạm thời |
| AUTH_TOKEN_EXPIRED | Access Token hết hạn |
| ACCESS_DENIED | Không có quyền |
| TICKET_NOT_FOUND | Không tìm thấy ticket trong phạm vi |
| INVALID_STATUS_TRANSITION | Chuyển trạng thái không hợp lệ |
| ASSIGNEE_NOT_IN_TEAM | Người nhận không thuộc nhóm |
| VERSION_CONFLICT | Dữ liệu đã được người khác cập nhật |
| FILE_TOO_LARGE | Tệp vượt giới hạn |
| FILE_TYPE_NOT_ALLOWED | Loại tệp không cho phép |
| AI_RATE_LIMITED | Vượt giới hạn gọi AI |
| AI_TIMEOUT | Dịch vụ AI quá thời gian |
| AI_INVALID_RESPONSE | Đầu ra AI sai schema |
| AI_RESULT_ALREADY_REVIEWED | Kết quả AI đã được duyệt |
| SLA_POLICY_CONFLICT | Chính sách SLA chồng lấn hoặc không hợp lệ |

## 10.3. Nguyên tắc xử lý lỗi

- Client nhận thông báo dễ hiểu và mã lỗi ổn định.
- Chi tiết kỹ thuật được ghi trong log có request_id.
- Không để lỗi AI rollback thay đổi ticket không liên quan.
- Không lưu dữ liệu một phần khi giao dịch nghiệp vụ bắt buộc thất bại.
- Với lỗi xung đột, client phải tải lại dữ liệu mới nhất.
- Với lỗi mạng tạm thời, giao diện cho phép người dùng thử lại có chủ đích.

---

# 11. Tiêu chí nghiệm thu

## 11.1. Nghiệm thu nghiệp vụ cốt lõi

| Mã | Điều kiện đạt |
|---|---|
| AC-01 | Public User tạo được ticket hợp lệ và nhận mã tra cứu |
| AC-02 | Ticket mới có trạng thái Open và deadline SLA phù hợp |
| AC-03 | Public User tra cứu đúng ticket bằng mã + email và không thấy dữ liệu nội bộ |
| AC-04 | Agent chỉ xem được ticket trong nhóm hoặc được gán cho mình |
| AC-05 | Manager chỉ xem và phân công trong nhóm mình quản lý |
| AC-06 | Administrator xem và quản trị được toàn hệ thống |
| AC-07 | Bộ lọc ticket theo trạng thái và thời gian trả kết quả đúng |
| AC-08 | Chuyển trạng thái sai bị từ chối; chuyển đúng tạo lịch sử |
| AC-09 | Ghi chú nội bộ không xuất hiện trên Public Portal |
| AC-10 | Tệp không hợp lệ bị từ chối và không thể truy cập khi không có quyền |

## 11.2. Nghiệm thu AI

| Mã | Điều kiện đạt |
|---|---|
| AC-AI-01 | PII được thay bằng placeholder trước khi Gemini nhận nội dung |
| AC-AI-02 | Phân loại trả category, priority, confidence và reason đúng schema |
| AC-AI-03 | AI Result mới luôn ở pending_review |
| AC-AI-04 | Trước khi duyệt, kết quả phân loại không thay đổi ticket |
| AC-AI-05 | Chấp nhận phân loại mới cập nhật các trường đã duyệt |
| AC-AI-06 | Tóm tắt có các phần bắt buộc và không thay thế lịch sử gốc |
| AC-AI-07 | Bản nháp được đưa vào ô soạn thảo nhưng không tự gửi |
| AC-AI-08 | Chỉnh sửa AI lưu được cả đầu ra gốc và đầu ra sau sửa |
| AC-AI-09 | Từ chối AI không làm thay đổi dữ liệu chính thức |
| AC-AI-10 | Gemini timeout không làm mất hoặc sai dữ liệu ticket |
| AC-AI-11 | Quyết định AI được ghi reviewer, thời gian và Audit Log |

## 11.3. Nghiệm thu bảo mật và hiệu năng

| Mã | Điều kiện đạt |
|---|---|
| AC-SEC-01 | Truy cập ticket bằng ID ngoài phạm vi bị từ chối |
| AC-SEC-02 | Agent không gọi được API quản trị dù gửi request trực tiếp |
| AC-SEC-03 | Nội dung XSS thử nghiệm không thực thi trên trình duyệt |
| AC-SEC-04 | SQL Injection cơ bản không làm thay đổi câu truy vấn |
| AC-SEC-05 | Token, mật khẩu và API key không xuất hiện trong response/log kiểm tra |
| AC-SEC-06 | Tệp thực thi hoặc quá kích thước bị từ chối |
| AC-PER-01 | Các ngưỡng P95 ở Mục 9.3 đạt trong môi trường kiểm thử đã ghi nhận |

---

# 12. Ma trận truy vết yêu cầu

| Nhóm yêu cầu | Use Case | Thành phần chính | Nhóm kiểm thử |
|---|---|---|---|
| FR-AUTH | UC-01 | Auth API, JWT Service, users, refresh_tokens | TC-AUTH |
| FR-PUB | UC-02, UC-03 | Public API, tickets, attachments | TC-PUB |
| FR-TIC | UC-04, UC-05, UC-07 | Ticket API, Ticket Service, ticket_history | TC-TIC |
| FR-ASG | UC-06 | Assignment Service, teams, team_members | TC-ASG |
| FR-COM | UC-08 | Comment API, File Service | TC-COM |
| FR-AIC | UC-09, UC-12 | Gemini Service, PII Masker, ai_results | TC-AIC |
| FR-AIS | UC-10, UC-12 | Gemini Service, Context Builder | TC-AIS |
| FR-AID | UC-11, UC-12 | Gemini Service, Draft UI | TC-AID |
| FR-AIR | UC-12 | AI Review API, Audit Service | TC-AIR |
| FR-REP | UC-13 | Dashboard API, thống kê SQL | TC-REP |
| FR-ADM | UC-14 | User/Team API | TC-ADM |
| FR-SLA, FR-AUD | UC-15 | SLA Service, Audit Service | TC-SLA, TC-AUD |
| NFR-SEC, NFR-PRI | Tất cả | Middleware, RBAC, Validation | TC-SEC |
| NFR-PER | UC-01 đến UC-15 | Toàn hệ thống | TC-PER |

Mỗi test case chi tiết cần ghi ít nhất: mã yêu cầu liên quan, tiền điều kiện, dữ liệu kiểm thử, bước thực hiện, kết quả mong đợi, kết quả thực tế và trạng thái Pass/Fail.

---

# 13. Yêu cầu kiểm thử

## 13.1. Unit Test

- Kiểm tra hàm chuyển trạng thái ticket.
- Kiểm tra RBAC và Data Scoping.
- Kiểm tra tính deadline SLA.
- Kiểm tra PII Masker với email, số điện thoại và chuỗi đặc biệt.
- Kiểm tra schema đầu ra AI.
- Kiểm tra validation tệp và dữ liệu đầu vào.
- Kiểm tra tính toán thời gian phản hồi và giải quyết.

Mục tiêu coverage đề xuất: tối thiểu 80% cho service nghiệp vụ cốt lõi; coverage tổng không được dùng thay thế cho chất lượng test case.

## 13.2. Integration Test

- API đăng nhập với database và Refresh Token.
- Tạo ticket kèm tệp trong một giao dịch nhất quán.
- Phân công với dữ liệu nhóm thật.
- Bình luận công khai cập nhật first_response_at.
- Gọi Gemini bằng mock để kiểm tra timeout, JSON sai và thành công.
- Duyệt AI cập nhật ticket và tạo Audit Log.
- Truy vấn Dashboard khớp dữ liệu nguồn.

## 13.3. System Test

- Luồng từ Public Portal đến Closed.
- Luồng Pending và tiếp tục xử lý.
- Luồng mở lại ticket.
- Luồng đầy đủ PII Masking → Gemini JSON → pending_review → duyệt/chỉnh sửa → Audit Log.
- Kiểm thử bốn vai trò và truy cập chéo nhóm.
- Kiểm thử giao diện trên các trình duyệt hỗ trợ.

## 13.4. Security Test

- Broken Access Control và IDOR.
- JWT hết hạn, giả mạo hoặc đã thu hồi.
- Brute force đăng nhập và dò mã ticket.
- SQL Injection.
- Stored/Reflected XSS.
- Tải tệp nguy hiểm và path traversal.
- Lộ thông tin qua lỗi và log.
- Prompt injection trong nội dung ticket: AI vẫn chỉ sinh gợi ý, không được gọi hành động nghiệp vụ.

## 13.5. Performance Test

- 50 người dùng đồng thời đọc/lọc ticket.
- Tập dữ liệu tối thiểu 50.000 ticket cho truy vấn danh sách.
- Đo P50, P95, P99 và tỷ lệ lỗi.
- Tách riêng thời gian Backend và thời gian Gemini.
- Ghi rõ phần cứng, phiên bản phần mềm, dữ liệu và kịch bản để kết quả có thể lặp lại.

---

# 14. Cấu hình và triển khai

## 14.1. Biến môi trường tối thiểu

| Biến | Mục đích | Bí mật |
|---|---|---:|
| DATABASE_URL | Kết nối PostgreSQL | Có |
| JWT_SECRET_KEY hoặc khóa RS256 | Ký token | Có |
| ACCESS_TOKEN_EXPIRE_MINUTES | Thời hạn Access Token | Không |
| REFRESH_TOKEN_EXPIRE_DAYS | Thời hạn Refresh Token | Không |
| GEMINI_API_KEY | Xác thực Gemini | Có |
| GEMINI_MODEL | Tên model | Không |
| AI_TIMEOUT_SECONDS | Timeout AI | Không |
| AI_LOW_CONFIDENCE_THRESHOLD | Ngưỡng cảnh báo | Không |
| MAX_UPLOAD_SIZE_MB | Giới hạn tệp | Không |
| ALLOWED_FILE_TYPES | Loại tệp cho phép | Không |
| CORS_ALLOWED_ORIGINS | Origin được phép | Không |
| LOG_LEVEL | Mức log | Không |

File .env thật không được commit. Dự án chỉ cung cấp .env.example không chứa giá trị bí mật.

## 14.2. Health Check

- Liveness: tiến trình Backend đang chạy.
- Readiness: Backend kết nối được PostgreSQL và migration phù hợp.
- Trạng thái Gemini được báo riêng; Gemini lỗi không làm liveness của hệ thống thất bại.
- Frontend phải hiển thị thông báo AI tạm thời không khả dụng trong khi chức năng ticket vẫn dùng được.

## 14.3. Migration và dữ liệu khởi tạo

- Migration phải chạy theo thứ tự và có cơ chế phát hiện thất bại.
- Dữ liệu khởi tạo gồm một Administrator, danh mục cơ bản và chính sách SLA.
- Mật khẩu khởi tạo không được hard-code; phải đổi sau lần đăng nhập đầu hoặc được truyền an toàn.
- Không tự động xóa dữ liệu khi container khởi động lại.

---

# 15. Rủi ro và biện pháp kiểm soát

| Mã | Rủi ro | Ảnh hưởng | Biện pháp |
|---|---|---|---|
| R-01 | AI phân loại sai | Sai ưu tiên hoặc danh mục | pending_review, confidence, người duyệt |
| R-02 | AI tạo phản hồi không chính xác | Gửi thông tin sai cho khách hàng | Bản nháp, không tự gửi, bắt buộc kiểm tra |
| R-03 | Rò rỉ PII sang dịch vụ AI | Vi phạm riêng tư | PII Masking, tối thiểu hóa dữ liệu, test |
| R-04 | Gemini lỗi hoặc hết quota | Chức năng AI gián đoạn | Timeout, lỗi tách biệt, ticket vẫn hoạt động |
| R-05 | Manager/Agent xem sai phạm vi | Lộ dữ liệu | RBAC + team scoping tại Backend, test IDOR |
| R-06 | Ghi chú nội bộ lộ ra Portal | Lộ nghiệp vụ nội bộ | visibility bắt buộc, serializer riêng cho Portal |
| R-07 | Truy vấn thống kê sai định nghĩa | Báo cáo không đáng tin | Một nguồn định nghĩa, đối chiếu dữ liệu mẫu |
| R-08 | Trạng thái Assigned gây mâu thuẫn | Sai vòng đời ticket | Dùng trường phân công; trạng thái dùng Pending |
| R-09 | Tệp độc hại | Mất an toàn máy chủ/người dùng | Allowlist, giới hạn, lưu ngoài web root |
| R-10 | Ghi đè cập nhật đồng thời | Mất dữ liệu | Optimistic locking bằng version |
| R-11 | SLA tính sai do múi giờ | Đánh giá sai quá hạn | Lưu UTC, test biên thời gian |
| R-12 | Prompt injection từ khách hàng | AI làm theo chỉ dẫn không phù hợp | System Prompt, schema, không cấp công cụ hành động, người duyệt |

---

# 16. Quyết định thiết kế cần giữ nhất quán

1. Không có trạng thái Assigned. Phân công là team_id và assigned_to.
2. Pending có nghĩa đang chờ thông tin hoặc yếu tố bên ngoài, không có nghĩa đã được phân công.
3. Không có bảng Customer trong phạm vi hiện tại; requester_name và requester_email nằm trong tickets.
4. AI chỉ có ba chức năng: phân loại, tóm tắt, tạo bản nháp.
5. Không triển khai RAG/FAQ làm nguồn cho AI trong phiên bản này.
6. AI không tự gửi, tự đổi trạng thái, tự phân công hoặc tự đóng ticket.
7. Mọi AI Result mới đều là pending_review.
8. Chỉ kết quả được người có quyền xác nhận mới ảnh hưởng dữ liệu chính thức.
9. Frontend không phải ranh giới bảo mật; Backend luôn kiểm tra quyền.
10. Ticket History mô tả diễn biến của ticket; Audit Log phục vụ kiểm toán toàn hệ thống.

---

# 17. Các điểm cần xác nhận trước khi chốt phiên bản 1.0

Các mục sau không cản trở việc dùng SRS làm cơ sở phát triển, nhưng Product Owner cần xác nhận để tránh nhóm tự suy đoán:

| Mã | Câu hỏi cần xác nhận | Giá trị mặc định trong SRS |
|---|---|---|
| TBD-01 | Danh sách category chính thức gồm những gì? | TECHNICAL, ACCOUNT, BILLING, GENERAL, OTHER |
| TBD-02 | Pending có tạm dừng SLA không? | Theo từng sla_policy; mặc định không |
| TBD-03 | Sau bao lâu Resolved tự chuyển Closed? | Chưa tự động trong phiên bản cơ sở |
| TBD-04 | Public User có được phản hồi lại trên Portal không? | Chỉ tra cứu; phản hồi hai chiều là mở rộng |
| TBD-05 | Định dạng tệp được phép? | PDF, PNG, JPG, TXT, DOCX; cấm file thực thi |
| TBD-06 | Chính sách lưu trữ dữ liệu thực tế? | 12 tháng |
| TBD-07 | Ngưỡng confidence thấp? | 0,70 |
| TBD-08 | Có áp dụng giờ làm việc khi tính SLA không? | Tính liên tục 24/7 trong phiên bản cơ sở |
| TBD-09 | Có gửi email thông báo không? | Không thuộc phiên bản cơ sở |

Mọi thay đổi các giá trị trên phải được cập nhật đồng thời trong SRS, schema, API, giao diện và test case.

---

# 18. Điều kiện hoàn thành yêu cầu

Một yêu cầu chỉ được xem là hoàn thành khi:

- Mã nguồn đã được triển khai theo Acceptance Criteria.
- Có kiểm tra quyền và validation tại Backend.
- Có migration nếu thay đổi dữ liệu.
- Có unit/integration test phù hợp và test đạt.
- API/OpenAPI được cập nhật.
- Giao diện xử lý đủ loading, empty, success và error state.
- Không làm lộ PII, secret hoặc dữ liệu ngoài phạm vi.
- Với chức năng AI, có PII Masking, JSON validation, pending_review và Human-in-the-loop.
- Có minh chứng kiểm thử hoặc screenshot cần thiết cho báo cáo.
- Product Owner hoặc người được giao xác nhận kết quả Sprint.

---

# 19. Phê duyệt tài liệu

| Vai trò | Họ tên | Trạng thái | Ngày |
|---|---|---|---|
| Đại diện nhóm phát triển | La Văn Tuấn | Chờ xác nhận |  |
| Thành viên nhóm | Trần Minh Thuận | Chờ xác nhận |  |
| Giảng viên/Người đánh giá |  | Chờ xác nhận |  |

Khi tài liệu được phê duyệt, mọi thay đổi phạm vi phải được ghi nhận trong Product Backlog, đánh giá ảnh hưởng đến thiết kế, dữ liệu, API, kiểm thử và cập nhật phiên bản SRS.
