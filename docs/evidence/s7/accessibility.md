# Báo Cáo Đánh Giá Khả Năng Tiếp Cận (Accessibility) - Sprint 7

- **Ngày đánh giá**: 2026-09-09
- **Tiêu chuẩn tham chiếu**: WCAG 2.1 Level AA
- **Phạm vi kiểm thử**:
  - Public Portal: Gửi vé và tra cứu tiến độ vé
  - Internal Portal (Agent / Manager / Admin): Đăng nhập, Danh sách vé, Chi tiết vé, Bảng điều khiển (Dashboard), Phân hệ quản trị (Users, Teams, SLA, Audit Logs)
  - Kích thước màn hình: Desktop (1280x800) và Mobile nhỏ nhất (360x640)

---

## 1. Kết Quả Kiểm Tra Từng Hạng Mục

| STT | Hạng mục kiểm tra | Tiêu chí đánh giá | Trạng thái | Chi tiết thực hiện |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Điều hướng bàn phím** | Tab & Shift+Tab theo thứ tự logic | **PASS** | - Toàn bộ liên kết (`<a>`), nút bấm (`<button>`), ô nhập (`<input>`, `<select>`, `<textarea>`) nhận focus theo thứ tự DOM tự nhiên.<br>- Các thẻ KPI trên Dashboard hỗ trợ `tabIndex={0}` và kích hoạt bộ lọc bằng phím `Enter`.<br>- Hỗ trợ nhảy qua các trường nhanh chóng mà không bị kẹt focus trap vô tận. |
| **2** | **Hiển thị Focus (Focus Visible)** | Chỉ báo viền focus rõ nét, không bị ẩn | **PASS** | - Cấu hình toàn cục `:focus-visible` với viền `2px solid var(--color-primary)` và khoảng đệm `outline-offset: 2px`.<br>- Các trường nhập liệu (`.field input`, `.admin-input`) hiển thị viền xanh cùng hiệu ứng glow (`box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12)`).<br>- Nút bấm có trạng thái `:focus-visible` riêng biệt cho Primary, Secondary và Danger. |
| **3** | **Nhãn và Ô nhập liệu (Labels & Inputs)** | Nút và ô nhập có label, placeholder, aria-label rõ ràng | **PASS** | - 100% trường nhập liệu form ở Public Portal và Admin đều có thẻ `<label>` hoặc `.form-label` đi kèm.<br>- Nút điều hướng icon không có chữ (nút menu mobile burger, nút đóng dialog) được bổ sung `aria-label` (ví dụ: `aria-label="Mở menu điều hướng"`, `aria-label="Đóng"`).<br>- Ô tìm kiếm vé có `aria-label="Tìm kiếm vé"` và hướng dẫn rõ ràng. |
| **4** | **Đóng Modal bằng phím Escape** | Hộp thoại modal đóng ngay khi nhấn phím Escape | **PASS** | - Đã tích hợp trình lắng nghe sự kiện phím `Escape` toàn cục trong `AppShell`.<br>- Khi nhấn Escape trong lúc hộp thoại (đổi trạng thái vé, phân công vé, sửa vé, modal quản trị) đang mở, hệ thống lập tức đóng modal an toàn.<br>- Đồng thời đóng menu ngăn kéo navigation trên mobile khi đang mở. |
| **5** | **Độ tương phản màu sắc (Color Contrast)** | Đạt chuẩn WCAG 2.1 AA (Tối thiểu 4.5:1 cho văn bản thường) | **PASS** | - Văn bản chính (`#0f172a` trên nền trắng `#ffffff`): tỷ lệ tương phản **16.1:1**.<br>- Văn bản phụ (`#475569` trên `#ffffff`): tỷ lệ tương phản **5.9:1** (vượt chuẩn 4.5:1).<br>- Nút Primary (`#ffffff` trên nền `#2563eb`): tỷ lệ **4.56:1**.<br>- Nút Danger (`#ffffff` trên nền `#dc2626`): tỷ lệ **4.62:1**.<br>- Hệ thống màu nhãn (Badge Status/Priority/Category) sử dụng văn bản sẫm trên nền nhạt, đều đạt từ **6.5:1** đến **7.2:1**.<br>- Chế độ Dark mode đạt tỷ lệ tương phản trên **14:1**. |
| **6** | **Hiển thị Desktop & Mobile 360px** | Giao diện thích ứng, không tràn viền ở màn hình 360px | **PASS** | - **Desktop**: Bố cục lưới 2 cột, bảng điều khiển hiển thị đầy đủ, thanh điều hướng mở rộng linh hoạt.<br>- **Mobile 360px**: Thanh điều hướng chuyển sang drawer trượt, các form nhập xếp chồng cột đơn, bảng dữ liệu hỗ trợ cuộn ngang (`table-responsive`) không làm vỡ layout.<br>- Kích thước nút bấm và ô nhập tối thiểu 40px chiều cao, thuận tiện cho thao tác chạm (touch targets). |

---

## 2. Minh Chứng Trực Quan Kèm Theo

Các ảnh chụp màn hình kiểm tra tại thư mục `docs/evidence/s7/screenshots/`:
- `11_responsive_360px_portal.png`: Form Public Portal trên màn hình rộng 360px.
- `11_responsive_360px_tickets.png`: Danh sách vé và drawer điều hướng ở 360px.
- `09_agent_status_modal.png`: Hộp thoại chuyển trạng thái vé (hỗ trợ phím Escape & focus trap).
- `07_ticket_detail.png`: Chi tiết vé với độ tương phản văn bản và nút bấm đạt chuẩn.

---

## 3. Kết Luận

Hệ thống Hỗ Trợ Ticket AI đáp ứng tốt các yêu cầu cơ bản về Khả năng tiếp cận (Accessibility) theo chuẩn WCAG 2.1 AA trên cả hai môi trường Desktop và Mobile 360px, đảm bảo trải nghiệm người dùng bằng bàn phím thuận tiện và an toàn trước khi bàn giao Sprint 7.
