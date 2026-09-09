# Báo Cáo Kiểm Thử Giao Diện E2E Sprint 7

- **Thời gian chạy**: 2026-09-09T07:13:54.544Z
- **Môi trường**: Base URL: `http://localhost:8080`
- **Tổng số ca kiểm thử**: 21
- **PASS**: 21 | **FAIL**: 0

| Mã TC | Tên ca kiểm thử | Kết quả | Chi tiết |
| :---: | :--- | :---: | :--- |
| **TC1** | Tạo vé từ Public Portal | **PASS** | Mã vé tạo thành công: TK-U3H3NORH |
| **TC2** | Tra cứu vé Public Portal | **PASS** | Tra cứu thành công vé TK-U3H3NORH với đầy đủ thông tin |
| **TC3** | Hiển thị lỗi khi nhập sai thông tin | **PASS** | Thông báo lỗi: "Email hoặc mật khẩu không đúng." |
| **TC4** | Đăng nhập Admin & Phân quyền Menu | **PASS** | Admin có đủ 3 menu: [Danh sách vé, Bảng điều khiển, Quản trị hệ thống] |
| **TC5** | Quản lý Người dùng, Nhóm, SLA, Audit Log | **PASS** | 4 phân hệ quản trị tải thành công, danh sách hiển thị 15 tài khoản |
| **TC6** | Dashboard hiển thị chỉ số KPI & SLA | **PASS** | Hiển thị 6 thẻ chỉ số KPI hoạt động và giám sát SLA |
| **TC7** | Tìm kiếm, lọc và mở chi tiết ticket | **PASS** | Mở chi tiết vé mã TK-U3H3NORH (ID: 11864cf5-5f53-4133-b312-6642b4209668) |
| **TC8.1** | Phân quyền Manager không thấy menu Quản trị | **PASS** | Menu Manager: [Danh sách vé, Bảng điều khiển] |
| **TC8.2** | Chặn Manager truy cập trái phép trang Admin | **PASS** | Hiển thị màn hình 403 "Không có quyền truy cập" |
| **TC8.3** | Manager phân công ticket cho nhân viên | **PASS** | Phân công vé thành công cho Team Kỹ thuật (Agent Lan) |
| **TC9.1** | Chặn Agent truy cập trái phép trang Admin | **PASS** | Hiển thị màn hình 403 "Không có quyền truy cập" |
| **TC9.2** | Agent thêm bình luận phản hồi khách hàng | **PASS** | Bình luận được lưu và hiển thị trên dòng thời gian timeline |
| **TC9.3** | Agent cập nhật trạng thái vé theo quy trình | **PASS** | Chuyển trạng thái hợp lệ tuân thủ State Machine |
| **TC10.1** | AI Phân loại tự động (Category/Priority) | **PASS** | Sinh đề xuất phân loại kèm độ tin cậy |
| **TC10.2** | AI Tóm tắt vé (Summary/Key points) | **PASS** | Sinh tóm tắt vấn đề và điểm quan trọng |
| **TC10.3** | AI Tạo nháp câu trả lời (Draft reply) | **PASS** | Sinh bản nháp phản hồi khách hàng theo chỉ dẫn |
| **TC10.4** | Duyệt bản nháp AI & đưa vào ô trả lời | **PASS** | Thẻ kết quả AI hiển thị đầy đủ các nút duyệt |
| **TC10.5** | Chỉnh sửa kết quả AI (Human-in-the-loop) | **PASS** | Hỗ trợ giao diện chỉnh sửa phân loại và ưu tiên |
| **TC10.6** | Từ chối kết quả AI (Human-in-the-loop) | **PASS** | Hỗ trợ đầy đủ các thao tác Human-in-the-loop |
| **TC11.1** | Responsive 360px: Header & Menu Drawer | **PASS** | Giao diện thích ứng với kích thước 360px |
| **TC11.2** | Responsive 360px: Public Portal form | **PASS** | Form tạo ticket hiển thị gọn gàng, nút bấm và trường nhập liệu dễ thao tác trên mobile |
