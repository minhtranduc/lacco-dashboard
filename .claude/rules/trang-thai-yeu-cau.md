---
paths:
  - "src/services/**"
  - "src/db/**"
  - "docs/requirements/**"
---

# Trạng thái yêu cầu báo cáo — dữ liệu chi tiết

> File này tự động nạp khi Claude làm việc với code trong `src/services/`, `src/db/`, hoặc `docs/requirements/` — không tải khi làm việc ở nơi khác (auth, deploy, UI...) để tiết kiệm ngữ cảnh.
> Nguồn: Tài liệu Kiến trúc Hệ thống + Sheet 1 "Mẫu thu thập yêu cầu" (`Bieu_mau_Yeu_cau_va_RACI_LACCO.xlsx`). Cập nhật mỗi khi có đợt phỏng vấn mới — xem `docs/teaching-notes/huong-dan/HD-03-thu-thap-yeu-cau.md`.

## Nguyên tắc

Chỉ code phần logic khi trạng thái là **Đã rõ**; phần "Cần làm rõ" chỉ dựng khung UI/schema, không hardcode công thức đoán mò.

## Bảng trạng thái (14 dòng)

| Nhóm báo cáo | Báo cáo con | Trạng thái | Ghi chú công thức (nếu đã rõ) |
|---|---|---|---|
| Kinh doanh | Doanh thu/lãi lỗ theo dịch vụ | ✅ Đã rõ | Dịch vụ Cước: doanh thu/lợi nhuận cao. Dịch vụ Hải quan: nòng cốt, ổn định. |
| Kinh doanh | Doanh thu/lãi lỗ theo khách hàng | ✅ Đã rõ | Top khách hàng thay đổi thứ hạng thường xuyên trong top 20 |
| Kinh doanh | Doanh thu/lãi lỗ theo Khối-Phòng-NV | ✅ Đã rõ | Khối kinh doanh trực tiếp luôn đạt KPI tốt nhất |
| Kinh doanh | Tình trạng đơn hàng | ✅ Đã rõ | Cần xác nhận danh sách trạng thái cụ thể trong hệ thống FT |
| Kinh doanh | Tình trạng xuất hóa đơn | ✅ Đã rõ | Là 1 trạng thái trong quy trình đơn hàng |
| Khách hàng | Tăng giảm loại KH (A/B/C) | ⛔ Cần làm rõ | **Ưu tiên cao nhất** — ảnh hưởng trực tiếp RBAC Tuần 3 |
| Khách hàng | Theo nguồn khách hàng | ⛔ Cần làm rõ | |
| Khách hàng | CRM | ⛔ Cần làm rõ | |
| Pricing | Thành đơn | ⛔ Cần làm rõ | |
| Pricing | Nhà cung cấp | ⛔ Cần làm rõ | |
| Chi phí | Theo Khối | ⛔ Cần làm rõ | Nguồn: AMIS |
| Chi phí | Theo Nhóm (LĐ/QL/Frontline/Middle/Backend) | ⛔ Cần làm rõ | Cần xác nhận ranh giới 5 nhóm |
| Công nợ | Khối → Phòng → Kinh doanh | ⛔ Cần làm rõ | **Ưu tiên cao** — ngưỡng quá hạn ảnh hưởng cảnh báo/màu sắc dashboard |
| Dòng tiền | Thu/chi, tồn quỹ | ⛔ Cần làm rõ | Nguồn: AMIS (cần xác nhận chính xác) |

## Yêu cầu còn tồn đọng — KHÔNG code logic tương ứng cho đến khi chốt

Còn 9/14 dòng "Cần làm rõ", cần phỏng vấn Trưởng phòng Kế toán – Tài chính (Chi phí theo Khối/Nhóm, Công nợ, Dòng tiền) và bổ sung với Trưởng phòng Kinh doanh/CSKH (tiêu chí A/B/C, nguồn KH, CRM, Pricing). Ưu tiên nhất: **tiêu chí phân loại KH A/B/C** và **ngưỡng công nợ quá hạn**. Xem chi tiết tại `docs/teaching-notes/huong-dan/HD-03-thu-thap-yeu-cau.md` và Sheet 1 của `Bieu_mau_Yeu_cau_va_RACI_LACCO.xlsx`.
