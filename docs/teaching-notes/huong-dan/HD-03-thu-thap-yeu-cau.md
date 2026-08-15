# HD-03: Kỹ thuật thu thập yêu cầu nghiệp vụ bằng phỏng vấn trực tiếp + biểu mẫu chuẩn hoá

**Tuần:** 1 — Nền tảng & chốt yêu cầu | **Đối tượng phù hợp:** Cả hai (Lãnh đạo & IT/BA) | **Ngày thực hiện:** 13/08/2026 (đợt 1)

## Mục tiêu

Biến các mục "Cần làm rõ" trong Sheet 1 (Mẫu thu thập yêu cầu) thành đặc tả đủ rõ ("Đã rõ") để dùng làm input thiết kế database ở Tuần 2 — thay vì viết một tài liệu SRS (Software Requirements Specification — đặc tả yêu cầu phần mềm) dài dòng, dùng thẳng bảng câu hỏi đã chuẩn bị sẵn làm kịch bản phỏng vấn.

## Cách tiếp cận đã dùng

1. Xác định người phụ trách từng nhóm báo cáo dựa theo nguồn dữ liệu (Hệ thống FT vs AMIS) và vai trò trong RACI (Sheet 2, file Biểu mẫu).
2. Phỏng vấn trực tiếp, mang theo đúng 4 câu hỏi chuẩn cho từng báo cáo (đã in sẵn trong cột "Câu hỏi nghiệp vụ cần trả lời").
3. Điền câu trả lời thẳng vào Sheet 1 ngay trong/ngay sau buổi họp, đổi Trạng thái dòng đó sang "Đã rõ".

## Kết quả đợt 1 (phỏng vấn Trưởng phòng Kinh doanh)

| Nhóm báo cáo | Số dòng đã "Đã rõ" |
|---|---|
| Báo cáo kinh doanh (doanh thu/lãi lỗ theo dịch vụ, khách hàng, Khối-Phòng-NV) | 3/3 |
| Tình trạng đơn hàng | 1/1 |
| Tình trạng xuất hóa đơn | 1/1 |
| **Tổng đợt 1** | **5/14** |

Ví dụ 1 kết quả cụ thể thu được (Doanh thu theo dịch vụ): *"Dịch vụ Cước mang lại doanh thu và lợi nhuận cao. Nhưng Dịch vụ Hải quan lại là nòng cốt và mang lại doanh thu, lợi nhuận ổn định"* — một insight nghiệp vụ thực tế mà nếu không phỏng vấn trực tiếp sẽ không thể suy ra chỉ từ tên trường dữ liệu.

## Còn lại — cần đợt phỏng vấn tiếp theo (9/14 dòng)

| Người cần phỏng vấn | Báo cáo còn "Cần làm rõ" |
|---|---|
| Trưởng phòng Kinh doanh / CSKH | Tăng giảm loại khách hàng (A/B/C), Theo nguồn khách hàng, CRM, Pricing (Thành đơn, Nhà cung cấp) |
| Trưởng phòng Kế toán – Tài chính | Chi phí theo Khối, Chi phí theo Nhóm, Công nợ, Dòng tiền |

Ưu tiên nhất trong đợt tiếp theo: **tiêu chí phân loại khách hàng A/B/C** (ảnh hưởng trực tiếp tới thiết kế RBAC ở Tuần 3) và **ngưỡng công nợ quá hạn** (ảnh hưởng cảnh báo/màu sắc trên dashboard).

## Bài học rút ra

- Không cần đợi phỏng vấn xong 100% mới bắt đầu code — các bước không phụ thuộc trực tiếp vào phần còn thiếu (như 1.4 Scaffold cấu trúc dự án) có thể làm song song, miễn cập nhật đúng trạng thái thực tế (không đánh dấu "Hoàn thành" khi chỉ mới xong một phần) để tránh sai lệch giữa kế hoạch và thực tế.
- Phỏng vấn theo từng nhóm phụ trách (thay vì gộp tất cả Trưởng phòng vào 1 buổi) giúp buổi họp ngắn gọn, đúng trọng tâm — mỗi người chỉ trả lời phần mình nắm rõ nhất.
- Câu trả lời định tính (ví dụ nhận định "dịch vụ nào ổn định") cũng là thông tin hữu ích cho thiết kế dashboard (gợi ý cần hiển thị xu hướng, không chỉ số tuyệt đối) — không phải mọi câu trả lời phỏng vấn đều cần quy về công thức toán học ngay.

## Kết quả

5/14 dòng yêu cầu đã rõ (nhóm Kinh doanh). Đủ để bắt đầu Bước 1.4 (Scaffold cấu trúc dự án — không phụ thuộc chi tiết nghiệp vụ). Cần hoàn tất đợt phỏng vấn Kế toán – Tài chính trước khi thiết kế schema chi tiết ở Tuần 2.
