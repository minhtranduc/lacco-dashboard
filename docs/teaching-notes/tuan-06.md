# Nhật ký Tuần 6 — Export, hiệu năng, giám sát lỗi

**Thời gian dự kiến:** 31/08 – 06/09/2026 | **Thời gian hoàn thành thực tế:** 11–13/09/2026 | **Trạng thái:** 4/4 bước hoàn thành

## 1. Tổng quan

Tuần 6 gồm 4 bước: xuất báo cáo Excel/PDF (6.1, HD-18), test tải 20 người dùng đồng thời (6.2, HD-19), cấu hình Sentry giám sát lỗi runtime (6.3, HD-20), và nhật ký tuần này (6.4). Cả 4 bước đã hoàn thành, muộn hơn lịch dự kiến khoảng 5-7 ngày (đúng như tracker vẫn ghi nhận: "ngày là mốc linh hoạt, không phải deadline cứng") — không có bước nào bị bỏ dở hay đóng non.

Đây là tuần có mật độ "phát hiện thật ngoài dự kiến" cao nhất tính đến nay: cả 3 bước kỹ thuật (6.1, 6.2, 6.3) đều phát sinh ít nhất 1 vướng mắc không lường trước khi lập kế hoạch — từ `kaleido`/Chrome headless treo (6.1), quên `ruff check` khiến CI chặn 2 lần liên tiếp (6.2), đến `sentry-sdk` tự động bật tích hợp gây trùng dữ liệu (6.3). Điểm chung: tất cả đều được phát hiện bằng cách xác minh thật (test thực nghiệm, đọc log CI, đếm issue trên dashboard) chứ không phải suy luận trước, và đều có bằng chứng cụ thể ghi trong HD-18/19/20.

Tiến độ tổng dự án sau tuần này: **29/38 bước (76,3%)** — theo sheet "3-Tien do tong quan" của tracker.

## 2. Đối chiếu tiêu chí nghiệm thu MVP Giai đoạn 1 (Kế hoạch triển khai mục 8)

Đây là 7 tiêu chí nghiệm thu cuối Giai đoạn 1 (8 tuần), không phải tiêu chí phải đạt từng tuần — dưới đây chỉ liệt kê phần Tuần 6 đã đặt nền móng, không phải toàn bộ đã "xong":

| # | Tiêu chí (nguyên văn Kế hoạch triển khai) | Tuần 6 đóng góp gì |
|---|---|---|
| 1 | Tất cả 6 nhóm báo cáo hoạt động | Không thuộc phạm vi Tuần 6 (đã xong ở Tuần 4/5; Dòng tiền đã chốt dời Giai đoạn 2 — xem CLAUDE.md) |
| 2 | RBAC 3 cấp hoạt động đúng | Không thuộc phạm vi Tuần 6 (đã xong ở Tuần 3/5) |
| 3 | Audit log và login history ghi nhận đầy đủ | Không thuộc phạm vi Tuần 6 (đã xong ở Tuần 3) — nhưng bước 6.3 bổ sung thêm 1 lớp giám sát khác (lỗi runtime, không phải hành vi người dùng) |
| 4 | **Xuất được Excel/PDF cho mọi báo cáo** | **Đạt ở bước 6.1** — 6/6 trang báo cáo, 20 cặp chart+bảng, đã xác minh qua UI thật cả 3 role |
| 5 | **Chịu tải 20 người dùng đồng thời không lỗi** | **Đạt ở bước 6.2** — đo tại tầng Service/DB, 481-488 lượt gọi/60s tuỳ lần đo, 0 lỗi, p95 tối đa 0,011s so với ngưỡng 3s COO xác nhận bổ sung. Lưu ý: đo trên dữ liệu mẫu quy mô nhỏ, cần đo lại gần sát dữ liệu thật hơn trước go-live (bước 7.2) |
| 6 | Có backup/restore đã test thử | Chưa thuộc phạm vi Tuần 6 — dự kiến bước 7.3 |
| 7 | Có bộ tài liệu case study sẵn sàng làm bài giảng mẫu | Tuần 6 đóng góp 3 file HD (HD-18/19/20) + nhật ký này — đều có bảng lỗi thật, không chỉ quy trình lý tưởng |

Ngoài 7 tiêu chí trên, bước 6.3 (Sentry) không nằm trong danh sách tiêu chí nghiệm thu gốc nhưng thuộc lộ trình 8 tuần đã lên kế hoạch (tăng khả năng vận hành trước go-live) — deliverable "Sentry ghi nhận lỗi thử nghiệm thành công" đã đạt, xác minh bằng dashboard thật (6 issue, event ID cụ thể trong HD-20).

## 3. Bảng chi tiết các bước trong tuần

| Bước | Tên bước | Trạng thái | Ngày hoàn thành | Mã HD |
|---|---|---|---|---|
| 6.1 | Export Excel/PDF | Hoàn thành | 11/09/2026 | HD-18 |
| 6.2 | Test tải 20 concurrent users | Hoàn thành | 11/09/2026 | HD-19 |
| 6.3 | Cấu hình Sentry | Hoàn thành | 13/09/2026 | HD-20 |
| 6.4 | Review & nhật ký Tuần 6 | Hoàn thành | 13/09/2026 | (nhật ký này) |

## 4. Quyết định kiến trúc & lý do

**Quyết định của COO (nghiệp vụ/hạ tầng, qua `AskUserQuestion`):**
- **ReportLab thay vì WeasyPrint** cho export PDF (bước 6.1) — Claude đề xuất vì WeasyPrint cần cài GTK3 runtime riêng trên Windows, rủi ro khi deploy Windows Server đã biết trước (bước 7.2); COO xác nhận phương án khuyến nghị.
- **Nội dung PDF gồm cả chart Plotly dạng ảnh, không chỉ bảng số liệu** (bước 6.1) — COO chọn phương án đầy đủ hơn dù biết trước sẽ cần thêm `kaleido` (thư viện render chart thành ảnh) và rủi ro đi kèm.
- **Ngưỡng hiệu năng định lượng bổ sung cho tiêu chí "20 người dùng đồng thời"** (bước 6.2) — Kế hoạch triển khai chỉ ghi tiêu chí định tính; Claude đề xuất p95<3 giây/hàm, lỗi=0%, COO xác nhận. Đã ghi vào CLAUDE.md mục 7 để không phải hỏi lại cho các lần đo tải sau.
- **Sentry SaaS free tier, không self-host** (bước 6.3) — Claude trình bày đánh đổi (self-host cần Docker + nhiều service, tốn công bảo trì cho 1 người vận hành không có đội dev backup — đúng bối cảnh dự án ghi ở CLAUDE.md mục 1), COO xác nhận phương án khuyến nghị.

**Quyết định kỹ thuật thuần (Claude/CLI tự quyết theo convention có sẵn, không cần hỏi COO):**
- Đo tải ở tầng Service/Database thay vì dùng công cụ HTTP load-test (Locust/JMeter) — vì Streamlit dùng WebSocket + rerun toàn trang, không khớp mô hình "1 request = 1 response" mà các công cụ đó giả định.
- Bắc cầu Loguru → Sentry bằng sink riêng (Cách A) thay vì propagate ngược về `logging` chuẩn (Cách B) — tường minh hơn, dễ test độc lập hơn.
- 4 tham số bảo mật bắt buộc khi init Sentry (`send_default_pii=False`, `include_local_variables=False`, `traces_sample_rate=0`, `disabled_integrations=[LoguruIntegration()]`) — suy ra trực tiếp từ CLAUDE.md mục 6 (rủi ro bảo mật dữ liệu tài chính/khách hàng), không phải yêu cầu riêng của COO nhưng bắt buộc theo luật đã có.

## 5. Vấn đề gặp phải & cách Claude hỗ trợ giải quyết

| # | Bước | Vấn đề | Cách xử lý |
|---|---|---|---|
| 1 | 6.1 | `requirements.txt` thiếu `plotly`/`openpyxl` dù đã dùng ngầm định từ Tuần 4/5 | Đối chiếu trực tiếp `import` thực tế với file, bổ sung 2 dòng |
| 2 | 6.1 | Nút "Xuất PDF" làm `kaleido` render lại ở MỌI lần Streamlit rerun, không chỉ khi bấm nút | Tách 2 bước: "Tạo PDF" trước, hiện nút tải sau |
| 3 | 6.1 | `kaleido` có thể treo vô thời hạn khi render chart (nghi do phần mềm bảo mật máy dev, không xác định dứt điểm được) | Bọc timeout 20s bằng thread daemon; nếu lỗi/treo, PDF vẫn xuất được, chỉ thiếu ảnh chart — graceful fallback, không chặn tính năng chính |
| 4 | 6.2 | Dịch vụ Windows `MySQL80` đang Stopped khi bắt đầu test | Khởi động lại; ghi chú cần kiểm tra tự khởi động cùng Windows trước bước 7.2 |
| 5 | 6.2 | 2 commit đầu bị CI chặn vì bỏ sót `ruff check` trước commit | Tự phát hiện qua CI đỏ, sửa lint, chạy lại xác nhận hành vi không đổi (488 lượt/0 lỗi so với 481 lượt/0 lỗi lần đầu) |
| 6 | 6.3 | Prompt giao việc giả định đã có sẵn class Pydantic Settings — kiểm tra thật bằng `grep` cho thấy KHÔNG có | Tạo mới `src/services/config.py`, không sửa nhầm file không tồn tại, không refactor phần MySQL ngoài phạm vi |
| 7 | 6.3 | `sentry-sdk` tự động bật `LoguruIntegration` khi thấy `loguru` đã cài, gây mỗi lỗi sinh 2 event trùng lặp — chỉ phát hiện được khi đếm issue thật trên dashboard (3 issue thay vì 2 kỳ vọng) | Thêm `disabled_integrations=[LoguruIntegration()]` tường minh, xác minh lại hết trùng bằng lần chạy thứ 2 |

## 6. Prompt tiêu biểu đã dùng trong tuần

- **Câu hỏi quyết định kỹ thuật trước khi code** (dùng cho cả 6.1 và 6.3): đưa ra 2 phương án kèm đánh đổi rõ ràng (ví dụ ReportLab/WeasyPrint, Sentry SaaS/self-host), có 1 phương án khuyến nghị kèm lý do — không hỏi mở "anh muốn dùng gì" để tránh COO phải tự nghiên cứu.
- **Prompt giao việc tự chứa hoàn toàn cho Claude Code CLI** (dùng cho bước 6.3): nhúng nguyên văn quyết định đã chốt, các tham số bảo mật bắt buộc, cảnh báo trước 1 gotcha kỹ thuật cụ thể (Loguru không tự được `LoggingIntegration` bắt), và yêu cầu xác minh bằng dashboard thật thay vì chỉ code chạy không lỗi — giúp CLI tránh đúng lỗi trùng event trước khi nó xảy ra... (thực tế vẫn xảy ra, nhưng CLI phát hiện và xử lý được nhanh nhờ đã được nhắc kiểm tra kỹ).
- **Yêu cầu "ghi lại vướng mắc thật, không chỉ báo cáo bản đã sửa xong"** lặp lại nhất quán trong mọi prompt giao việc — tạo thói quen cho CLI tự ghi log lỗi/nguyên nhân/cách xử lý ngay trong lúc làm, không phải nhớ lại sau.

## 7. Ước tính thời gian tiết kiệm so với làm thủ công

Ước tính định tính (không phải số đo chính xác hay cam kết ROI chính thức): việc tự điều tra và xử lý 1 mình vấn đề `kaleido` treo do môi trường (bước 6.1) hoặc phát hiện lỗi trùng event ẩn trong hành vi mặc định của `sentry-sdk` (bước 6.3) — nếu tự làm thủ công, nhiều khả năng sẽ tốn nhiều giờ tra cứu tài liệu SDK và thử-sai mới phát hiện ra nguyên nhân "auto_enabling_integrations". Việc thiết kế graceful fallback ngay từ đầu (thay vì phát hiện sau khi lỗi tái diễn ở production) cũng là dạng tiết kiệm khó lượng hoá nhưng thực chất — tránh 1 lớp rủi ro vận hành ở bước go-live sau này.

## 8. Bài học rút ra cho tuần sau

- **Đừng tin giả định trong prompt giao việc nếu chưa xác minh bằng code thật** — bước 6.3 suýt sửa nhầm 1 file không tồn tại vì prompt giả định sai; `grep`/đọc code trực tiếp trước khi sửa nên là bước mặc định, không phải bước "phòng khi cần".
- **SDK bên thứ 3 có thể tự động bật hành vi ẩn dựa trên package đã cài** (`sentry-sdk` + `auto_enabling_integrations`) — trước khi tự viết 1 tích hợp thủ công cho thư viện mà SDK đích có thể đã hỗ trợ sẵn, luôn kiểm tra tài liệu SDK trước, tránh trùng lặp âm thầm.
- **Xác minh bằng bằng chứng thật (dashboard, CI xanh, đếm issue) — không dừng ở "code chạy không lỗi"** — lặp lại đúng bài học đã rút ra ở HD-18 (kaleido) và giờ lại đúng ở HD-20 (Sentry); đây có vẻ là 1 loại lỗi có tính hệ thống của việc tích hợp SDK/thư viện ngoài, không phải ngẫu nhiên.
- **`ruff check` trước commit tiếp tục là điểm dễ quên nhất** dù đã ghi rõ trong CLAUDE.md mục 4 — 6.2 đã bị chặn CI 2 lần vì việc này; 6.3 không lặp lại nhờ được nhắc trực tiếp trong prompt giao việc — nên tiếp tục nhắc lại tường minh trong mọi prompt liên quan tới commit, không giả định CLI "nhớ" luật cũ.

## 9. Việc cần làm tiếp

- **Tuần 7 (Kiểm thử & triển khai):** 7.1 Test suite & security review cuối (qa-reviewer-agent), 7.2 Deploy Windows Server, 7.3 Backup/restore, 7.4 Review & nhật ký Tuần 7.
- **Rủi ro mang từ Tuần 6 sang bước 7.2:** `kaleido`/Chrome headless chưa xác nhận chạy ổn định trên Windows Server thật (chỉ mới graceful fallback, chưa xác nhận dứt điểm nguyên nhân treo trên máy dev) — cần test riêng trước go-live.
- **Rủi ro mang từ Tuần 6 sang bước 7.2:** dịch vụ Windows `MySQL80` cần xác nhận đặt tự khởi động cùng Windows trên server thật.
- **Rủi ro mang từ Tuần 6 sang bước 7.2:** kết quả test tải (bước 6.2) dựa trên dữ liệu mẫu quy mô nhỏ — nên đo lại với khối lượng gần thực tế hơn trước hoặc trong go-live.
- **Theo dõi quota Sentry free tier** khi ứng dụng vận hành thật lâu dài (giới hạn ~5.000 lỗi/tháng) — nếu vượt, cân nhắc nâng cấp gói hoặc lọc bớt lỗi ít quan trọng trước khi gửi.
- **Chưa refactor `db_connection.py` sang dùng chung class Pydantic Settings** vừa tạo ở bước 6.3 (`src/services/config.py`) — để dành cho 1 bước sau nếu cần đồng bộ cấu hình, không thuộc phạm vi bắt buộc của Giai đoạn 1.
