# HD-19: Kịch bản test tải cho ứng dụng nội bộ nhỏ

**Tuần:** 6 — Export, hiệu năng, giám sát lỗi | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 11/09/2026

## Mục tiêu

Xác nhận Dashboard chịu được 20 người dùng truy cập đồng thời không lỗi (tiêu chí ghi trong Kế hoạch triển khai mục 8), trước khi sang bước kiểm thử/triển khai (Tuần 7).

## Giải thích khái niệm: vì sao không dùng công cụ load-test thông thường (Locust...)

Các công cụ load-test phổ biến (Locust, JMeter...) được thiết kế cho ứng dụng kiểu REST — gửi 1 HTTP request, nhận 1 response, lặp lại. Streamlit không hoạt động theo mô hình đó: mỗi người dùng giữ 1 kết nối WebSocket riêng trong suốt phiên làm việc, và MỌI tương tác (đổi bộ lọc, chuyển tab) đều khiến toàn bộ script của trang đó chạy lại từ đầu (rerun) — không có khái niệm "1 request = 1 response" rõ ràng để công cụ load-test HTTP đo lường đúng. Vì vậy bước này chọn cách đo tải trực tiếp ở tầng Service/Database (lớp thực sự chịu tải khi nhiều người dùng cùng truy vấn), thay vì mô phỏng qua giao diện.

## Cách tiếp cận / Quy trình đã dùng

1. Kiểm tra cấu hình connection pool hiện tại của SQLAlchemy (`src/services/db_connection.py`) trước khi test — không set tường minh, dùng mặc định `QueuePool` (`pool_size=5`, `max_overflow=10`, tối đa 15 connection đồng thời, `pool_timeout=30s`).
2. Kiểm tra Kế hoạch triển khai mục 8 xem có ngưỡng cụ thể nào cho "20 người dùng đồng thời" không — tài liệu gốc chỉ ghi "chịu tải 20 người dùng đồng thời không lỗi", không có số cụ thể cho thời gian phản hồi. Tự đề xuất ngưỡng bổ sung (COO xác nhận): **p95 (95th percentile thời gian phản hồi) < 3 giây/hàm, tỷ lệ lỗi/timeout = 0%, không có lỗi pool connection timeout**.
3. Viết `scripts/load_test_services.py` — script chẩn đoán (không phải code sản phẩm): lấy toàn bộ `user_id` thật từ bảng `user` (dự án hiện có đúng 20 user), tính `compute_data_scope()` thật cho từng user (không giả lập RBAC), mô phỏng 20 "người dùng" bằng 20 luồng chạy song song (`ThreadPoolExecutor(max_workers=20)`), mỗi luồng lặp trong 60 giây, mỗi vòng nghỉ ngẫu nhiên 2-3 giây rồi gọi 1 trong 6 hàm đại diện (mỗi module báo cáo 1 hàm đơn giản nhất) với `scope` thật của user đó.
4. Chạy thật với DB "lacco" thật (không phải SQLite test), tổng hợp min/max/avg/p95 và số lỗi theo từng hàm.

## Kết quả thu được

Chạy 60 giây, 20 luồng đồng thời, tổng 481 lượt gọi, **0 lỗi**:

| Hàm | Số lần gọi | Min (s) | Max (s) | Avg (s) | P95 (s) |
|---|---|---|---|---|---|
| `report_chi_phi.get_cost_vs_budget_by_division` | 90 | 0.000 | 0.016 | 0.003 | 0.010 |
| `report_cong_no.get_debt_aging_summary` | 74 | 0.003 | 0.038 | 0.006 | 0.011 |
| `report_don_hang.get_order_status_counts` | 76 | 0.000 | 0.035 | 0.003 | 0.005 |
| `report_khach_hang.get_classification_trend` | 82 | 0.001 | 0.035 | 0.004 | 0.006 |
| `report_kinh_doanh.get_revenue_profit_by_service` | 72 | 0.001 | 0.039 | 0.004 | 0.008 |
| `report_pricing.get_win_rate_by_org` | 87 | 0.001 | 0.034 | 0.006 | 0.009 |

Toàn bộ 6 hàm có p95 ≤ 0.011s — thoải mái dưới ngưỡng 3 giây (dư khoảng 270 lần) — **ĐẠT** tiêu chí "chịu tải 20 người dùng đồng thời không lỗi". Không cần sửa cấu hình connection pool (giữ nguyên mặc định `pool_size=5`/`max_overflow=10`) vì chưa có dấu hiệu nghẽn thật — tránh tối ưu sớm khi chưa cần thiết.

**Lưu ý quan trọng khi đọc kết quả này:** dữ liệu test là dữ liệu mẫu tổng hợp (synthetic) quy mô nhỏ dùng cho case study, không phải khối lượng dữ liệu thật của LACCO khi vận hành lâu dài. Kết quả này xác nhận đúng "cơ chế đồng thời hoạt động ổn định, không có lỗi pool/threading" — chưa xác nhận hiệu năng ở khối lượng dữ liệu lớn hơn nhiều lần. Nên test lại 1 lần với dữ liệu gần thực tế hơn (hoặc theo dõi thời gian phản hồi thật sau khi vận hành 1 thời gian) trước hoặc trong giai đoạn go-live.

## Vấn đề phát sinh trong lúc test

| # | Vấn đề | Cách xử lý |
|---|---|---|
| 1 | Dịch vụ Windows `MySQL80` đang ở trạng thái Stopped khi bắt đầu test | Khởi động lại để chạy test, giữ nguyên trạng thái chạy sau đó (cần cho việc dev tiếp theo) — nên kiểm tra dịch vụ này được đặt tự khởi động cùng Windows trước khi triển khai thật ở bước 7.2 |
| 2 | Chạy `python scripts/load_test_services.py` trực tiếp không tự có `src` trên `sys.path` (Python mặc định thêm thư mục chứa script, không phải thư mục gốc repo) | Thêm `sys.path.insert(...)` ngay trong script để tự chạy độc lập được, không cần set `PYTHONPATH` tay |

## Bài học rút ra

- **"Chịu tải 20 người dùng" không có nghĩa như nhau ở mọi loại ứng dụng** — với 1 ứng dụng Streamlit nội bộ, câu hỏi quan trọng không phải "bao nhiêu request/giây" (kiểu web app thông thường) mà là "connection pool DB có đủ cho số phiên đồng thời không, và code có giữ connection lâu hơn cần thiết không" — chọn đúng tầng để đo (Service/DB thay vì HTTP) quan trọng hơn chọn đúng công cụ.
- **Kết quả "quá nhanh, quá tốt" cần được diễn giải đúng ngữ cảnh, không mặc nhiên coi là hiệu năng production** — dữ liệu mẫu nhỏ khiến mọi truy vấn đều rất nhanh; đây là bằng chứng "cơ chế đúng", không phải bằng chứng "hiệu năng ở quy mô thật", 2 điều này cần được phân biệt rõ khi báo cáo lên Ban Lãnh đạo.
- **Không tối ưu khi chưa có vấn đề thật** — dù có thể tăng `pool_size` "cho chắc", việc này không cần thiết khi số liệu đã dư thừa an toàn 270 lần so với ngưỡng; thêm cấu hình không có bằng chứng cần thiết chỉ làm tăng độ phức tạp phải bảo trì sau này.

## Kết quả

Bước 6.2 hoàn thành: xác nhận Dashboard đạt tiêu chí "chịu tải 20 người dùng đồng thời không lỗi" ở tầng Service/DB (481 lượt gọi, 0 lỗi, p95 tối đa 0.011s so với ngưỡng 3s) — không cần thay đổi cấu hình. Rủi ro cần theo dõi thêm: kết quả dựa trên dữ liệu mẫu quy mô nhỏ, nên xác nhận lại khi có khối lượng dữ liệu gần thực tế hơn trước khi go-live (bước 7.2).
