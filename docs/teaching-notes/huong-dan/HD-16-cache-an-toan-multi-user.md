# HD-16: Pattern cache an toàn multi-user trong Streamlit

**Tuần:** 4 — Báo cáo Kinh doanh & Khách hàng | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 07/09/2026

## Mục tiêu

Audit độc lập toàn bộ dự án để xác nhận rủi ro bảo mật lớn nhất đã xác định từ đầu (mục 7 Kế hoạch triển khai — Streamlit cache rò dữ liệu giữa các user) tiếp tục được kiểm soát, không chỉ ở code mới của bước 4.1 mà toàn bộ `src/app/`.

## Giải thích khái niệm: vì sao cache Streamlit mặc định nguy hiểm với ứng dụng nhiều người dùng

`@st.cache_data` mặc định cache kết quả theo giá trị các tham số đầu vào của hàm (dùng hash nội bộ của Streamlit). Nếu 1 hàm lấy dữ liệu báo cáo không nhận tham số nào định danh người gọi, thì lần gọi đầu tiên (của bất kỳ user nào) sẽ tạo ra 1 entry cache dùng chung — mọi user khác gọi lại cùng hàm đó (với cùng các tham số còn lại, ví dụ cùng khoảng ngày) sẽ nhận lại **đúng cùng 1 kết quả đã cache**, kể cả khi RBAC của họ khác nhau hoàn toàn. Đây chính là cách 1 Manager có thể vô tình thấy dữ liệu đã cache cho 1 User khác đăng nhập trước đó.

Cách khắc phục chuẩn: đưa `user_id` (và/hoặc `role_value`) vào làm tham số đầu vào của mọi hàm cache liên quan tới dữ liệu theo phạm vi người dùng — giá trị này trở thành một phần của cache key, nên Streamlit tự tách cache riêng cho từng user. Biến global/module-level còn nguy hiểm hơn cache sai cách: nó tồn tại xuyên suốt vòng đời tiến trình server, không có bất kỳ cơ chế phân biệt theo tham số nào — `st.session_state` mới là nơi đúng để giữ dữ liệu riêng theo từng phiên đăng nhập.

## Cách tiếp cận / Quy trình đã dùng

1. Pattern `_cached_data_scope(user_id, role_value)` được thiết lập lần đầu ở `main.py` (bước 3.1, Tuần 3) làm mẫu chuẩn duy nhất trong dự án — mọi module báo cáo viết sau (bước 4.1) đều sao chép đúng mẫu này qua persona `report-builder-agent`, không tự sáng tạo cách khác.
2. Ở bước 4.2, giao việc cho `qa-reviewer-agent` (persona chỉ đọc — Read/Grep/Glob/Bash, không Write/Edit, đúng vai trò tách biệt người viết code khỏi người audit, như đã dùng ở bước 3.2) quét lại **toàn bộ** `src/app/` — không chỉ 2 trang mới của bước 4.1 — để có 1 lần xác nhận độc lập, không dựa vào phần tự-review nhanh mà `report-builder-agent` đã làm lúc build ở bước 4.1.
3. Tự đối chiếu thêm bằng `grep` trực tiếp trên code thật (không chỉ tin bảng agent trả về) — phát hiện 1 sai lệch nhỏ (xem bảng lỗi bên dưới).

### Kết quả audit — 9 hàm `@st.cache_data` trong toàn dự án (không có `@st.cache_resource` nào)

| File | Số hàm cache | Kết quả |
|---|---|---|
| `main.py` | 1 | PASS |
| `pages/1_Bao_cao_Kinh_doanh.py` | 5 | PASS |
| `pages/2_Bao_cao_Khach_hang.py` | 3 | PASS |

Toàn bộ 9/9 hàm đều nhận `user_id: int` và/hoặc `role_value: str` làm tham số đầu vào trực tiếp — không có trường hợp ngoại lệ "dữ liệu tĩnh không cần user_id" nào trong dự án hiện tại. Không phát hiện biến global/module-level nào chứa dữ liệu nghiệp vụ — chỉ có 2 hằng số cấu hình thuần tuý (`_SESSION_KEY = "lacco_auth_session"`, `_CLASSIFICATION_ORDER = ["A","B","C"]`). Tên key `st.session_state` nhất quán tuyệt đối giữa `main.py` và cả 2 trang báo cáo.

## Sai lệch thật gặp phải khi tự xác minh

| # | Sai lệch | Cách phát hiện | Kết luận |
|---|---|---|---|
| 1 | `qa-reviewer-agent` kết luận "8/8 PASS" trong báo cáo, nhưng bảng liệt kê chi tiết có đúng 9 hàm (đều PASS) | Tự đếm lại số dòng trong chính bảng agent trả về, đối chiếu với `grep -n "st.cache_data"` chạy độc lập trên code thật (đếm được đúng 9 decorator thật) | Không phải lỗi bảo mật — toàn bộ 9 hàm đều PASS đúng như bảng chi tiết. Chỉ là lỗi đếm tổng trong câu kết luận tóm tắt của agent. Vẫn đáng ghi nhận: kể cả 1 báo cáo "toàn PASS" cũng cần đối chiếu số liệu cụ thể (đếm dòng, grep độc lập), không dừng lại ở việc tin câu kết luận tổng quát |

## Bài học rút ra

- Pattern cache theo `(user_id, role_value)` chỉ thực sự hiệu quả khi được coi là quy ước bắt buộc ngay từ mẫu code đầu tiên (`main.py`, bước 3.1) — nhờ vậy 2 module hoàn toàn mới ở bước 4.1 tự động tuân theo đúng mẫu mà không cần đặc tả lại chi tiết, chỉ cần persona trỏ đọc lại mẫu có sẵn.
- Audit bảo mật nên tách vai trò người viết code và người review, và nên **lặp lại độc lập theo từng bước lớn**, không coi 1 lần tự-review nhanh của agent viết code (bước 4.1) là đủ thay cho 1 lần audit toàn diện, chuyên trách (bước 4.2) — 2 lớp kiểm tra khác mục đích, không thay thế nhau.
- Ngay cả với agent chuyên trách audit, vẫn cần tự đối chiếu số liệu cụ thể (ở đây: đếm lại bằng `grep`) thay vì chỉ tin câu kết luận dạng "N/N PASS" — một câu tóm tắt sai không nhất thiết đi kèm nội dung sai, nhưng nếu không bắt được thói quen này sẽ dần hình thành thói quen tin tưởng mù quáng vào định dạng báo cáo đẹp thay vì vào nội dung thật.

## Kết quả

Bước 4.2 hoàn thành: audit độc lập xác nhận toàn bộ 9 hàm cache trong dự án (`main.py` + 2 module báo cáo Tuần 4) đều gắn đúng `user_id`/`role_value`, không có biến global chứa dữ liệu nhạy cảm, `session_state` key nhất quán 100%. Không phát hiện lỗ hổng nào cần sửa — rủi ro bảo mật lớn nhất của dự án (cache rò dữ liệu giữa các user) tiếp tục được kiểm soát tốt qua 2 lần audit độc lập (bước 3.2 và bước 4.2).
