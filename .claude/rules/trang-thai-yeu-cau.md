---
paths:
  - "src/services/**"
  - "src/db/**"
  - "docs/requirements/**"
---

# Trạng thái yêu cầu báo cáo — dữ liệu chi tiết

> File này tự động nạp khi Claude làm việc với code trong `src/services/`, `src/db/`, hoặc `docs/requirements/` — không tải khi làm việc ở nơi khác (auth, deploy, UI...) để tiết kiệm ngữ cảnh.
> Nguồn: Tài liệu Kiến trúc Hệ thống + Sheet 1 "Mẫu thu thập yêu cầu" (`Bieu_mau_Yeu_cau_va_RACI_LACCO.xlsx`). Cập nhật sau đợt phỏng vấn hoàn tất 17/08/2026 (bước 1.3) — xem `docs/teaching-notes/huong-dan/HD-03-thu-thap-yeu-cau.md`. Cập nhật thêm 07/09/2026 (chốt Tuần 4) — bổ sung quyết định loại trừ đơn Huỷ đã chốt ở bước 4.1.

## Nguyên tắc

Chỉ code phần logic khi trạng thái là **Đã rõ**; phần "Cần làm rõ" chỉ dựng khung UI/schema, không hardcode công thức đoán mò.

## Bảng trạng thái (14 dòng)

| Nhóm báo cáo | Báo cáo con | Trạng thái | Ghi chú công thức (nếu đã rõ) |
|---|---|---|---|
| Kinh doanh | Doanh thu/lãi lỗ theo dịch vụ | ✅ Đã rõ | Dịch vụ Cước: doanh thu/lợi nhuận cao. Dịch vụ Hải quan: nòng cốt, ổn định. **Đơn `status="Huỷ"` loại trừ khỏi tổng (COO xác nhận 07/09/2026, bước 4.1) — có số liệu riêng theo dõi số lượng/giá trị đơn Huỷ.** |
| Kinh doanh | Doanh thu/lãi lỗ theo khách hàng | ✅ Đã rõ | Top khách hàng thay đổi thứ hạng thường xuyên trong top 20. Đơn `status="Huỷ"` loại trừ khỏi tổng — như trên. |
| Kinh doanh | Doanh thu/lãi lỗ theo Khối-Phòng-NV | ✅ Đã rõ | Khối kinh doanh trực tiếp luôn đạt KPI tốt nhất. Đơn `status="Huỷ"` loại trừ khỏi tổng — như trên. |
| Kinh doanh | Tình trạng đơn hàng | ✅ Đã rõ | Cần xác nhận danh sách đầy đủ trạng thái cụ thể trong hệ thống FT với Trưởng phòng Vận hành. Riêng giá trị "Huỷ" đã được COO xác nhận cách xử lý cho mục đích tính doanh thu/lãi lỗ (loại trừ) — không có nghĩa là toàn bộ danh sách trạng thái đã được Vận hành xác nhận đầy đủ. |
| Kinh doanh | Tình trạng xuất hóa đơn | ✅ Đã rõ | Là 1 trạng thái trong quy trình đơn hàng |
| Khách hàng | Tăng giảm loại KH (A/B/C) | ✅ Đã rõ | Dựa theo cột "Phân loại" đã có sẵn trong hệ thống FT — không tự định nghĩa lại ngưỡng xếp hạng, dùng nguyên trường này để phân nhóm A/B/C. **Dùng trực tiếp cho RBAC** (xem CLAUDE.md mục 6). |
| Khách hàng | Theo nguồn khách hàng | ✅ Đã rõ | Dựa theo cột "Nguồn" đã có sẵn trong hệ thống FT |
| Khách hàng | CRM | ⛔ Cần làm rõ | Hệ thống chưa có dữ liệu CRM. **Đã chốt dời sang Giai đoạn 2** — không phải chờ trả lời thêm ở Giai đoạn 1. |
| Pricing | Thành đơn | ✅ Đã rõ | Công thức: Số lượng chốt đơn / Số lượng request giá |
| Pricing | Nhà cung cấp | ✅ Đã rõ | Dựa vào báo cáo đánh giá nhà cung cấp do Nhân viên Pricing lập |
| Chi phí | Theo Khối | ✅ Đã rõ | So sánh chi thực tế với budget từng Khối (đã có budget từng khối). Nguồn: AMIS |
| Chi phí | Theo Nhóm (LĐ/QL/Frontline/Middle/Backend) | ✅ Đã rõ | Dùng nguyên nhóm nhân sự đã phân sẵn trong AMIS, không cần tự định nghĩa lại ranh giới 5 nhóm |
| Công nợ | Khối → Phòng → Kinh doanh | ✅ Đã rõ | Ngưỡng quá hạn theo 4 mức: 0-30 ngày, 31-60 ngày, 61-90 ngày, trên 90 ngày. Nguồn: AMIS |
| Dòng tiền | Thu/chi, tồn quỹ | ⛔ Cần làm rõ | Chưa xác nhận nguồn dữ liệu chính xác trong AMIS. **Đã chốt dời sang Giai đoạn 2** — không phải chờ trả lời thêm ở Giai đoạn 1. |

## Quy ước bổ sung đã chốt (Tuần 4, bước 4.1/4.3)

- **Nhóm theo Tuần trong biểu đồ xu hướng dùng ISO week** (MySQL `%x-%v`, tuần bắt đầu Thứ Hai) — COO xác nhận 07/09/2026, áp dụng nhất quán cho mọi module có biểu đồ trend theo thời gian (Chi phí, Công nợ theo tháng/tuần khi xây ở Tuần 5 cũng nên theo quy ước này trừ khi có lý do khác).

## Yêu cầu còn tồn đọng — KHÔNG code logic tương ứng cho đến khi chốt

Chỉ còn 2/14 dòng "Cần làm rõ": **CRM** (báo cáo khách hàng) và **Dòng tiền**. Cả hai KHÔNG phải "chưa phỏng vấn" — đã phỏng vấn xong ngày 17/08/2026 và được xác nhận **ngoài phạm vi Giai đoạn 1, dời sang Giai đoạn 2**. Với 2 nhóm này ở Giai đoạn 1: chỉ dựng khung UI rỗng/placeholder nếu cần cho demo, KHÔNG viết logic tính, KHÔNG tạo bảng schema thật trong `src/db/`. Xem chi tiết tại `docs/teaching-notes/huong-dan/HD-03-thu-thap-yeu-cau.md` và Sheet 1 của `Bieu_mau_Yeu_cau_va_RACI_LACCO.xlsx`.
