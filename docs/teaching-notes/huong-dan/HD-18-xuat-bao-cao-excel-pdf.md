# HD-18: Xuất báo cáo Excel/PDF chuyên nghiệp bằng Python

**Tuần:** 6 — Export, hiệu năng, giám sát lỗi | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 11/09/2026

## Mục tiêu

Thêm chức năng xuất Excel và PDF cho toàn bộ 6 trang báo cáo (Kinh doanh, Khách hàng, Đơn hàng, Pricing, Chi phí, Công nợ) — để Ban Lãnh đạo/Trưởng phòng lưu lại số liệu, gửi email, hoặc in ra ngoài phiên xem trực tiếp trên Dashboard.

## Giải thích khái niệm: vì sao cần "kaleido"

Chart trên Dashboard là Plotly — 1 đối tượng tương tác (zoom, hover) chỉ hiển thị được trong trình duyệt, không có sẵn dạng "ảnh tĩnh" để nhúng vào PDF. `kaleido` là thư viện chuyên convert 1 chart Plotly thành ảnh PNG bằng cách chạy ngầm 1 trình duyệt Chrome ẩn (headless), "chụp" lại chart rồi trả về file ảnh. Đây là bước kỹ thuật bắt buộc nếu muốn PDF có cả biểu đồ (không chỉ bảng số liệu) — và cũng là nguồn gốc phần lớn khó khăn của bước này (xem bảng lỗi bên dưới), vì phụ thuộc vào việc máy chạy có cho phép 1 tiến trình Chrome con khởi động bình thường hay không.

## Cách tiếp cận / Quy trình đã dùng

1. **2 quyết định kỹ thuật cần COO xác nhận trước khi code** (qua `AskUserQuestion`, không tự chọn):
   - Thư viện PDF: **ReportLab** (khuyến nghị) thay vì **WeasyPrint** — vì WeasyPrint cần cài GTK3 runtime riêng trên Windows, rủi ro khi deploy Windows Server ở bước 7.2 (đích deploy đã biết trước). ReportLab thuần Python, không phụ thuộc hệ thống ngoài.
   - Nội dung PDF: **bảng số liệu + chart Plotly dạng ảnh** (phức tạp hơn) thay vì chỉ bảng số liệu (đơn giản, an toàn hơn) — COO chọn phương án đầy đủ hơn dù biết trước sẽ cần thêm `kaleido`.
2. Xây `src/services/export_utils.py` — module tiện ích thuần (không mở kết nối DB, không nhận `scope`, chỉ nhận `DataFrame`/`Figure` đã tính sẵn từ service gọi trước đó, đúng nguyên tắc tách lớp CLAUDE.md mục 2):
   - `dataframe_to_excel_bytes()` — openpyxl, tiêu đề + header in đậm, auto-width cột.
   - `build_pdf_report_bytes()` — ReportLab, đăng ký font TTF hỗ trợ tiếng Việt (Helvetica mặc định của ReportLab KHÔNG có dấu tiếng Việt), nhúng ảnh chart qua `kaleido`, giới hạn bảng 200 dòng đầu kèm ghi chú nếu dữ liệu dài hơn.
3. Thêm nút "⬇️ Xuất Excel" / "⬇️ Xuất PDF" vào toàn bộ 20 cặp chart+bảng trên 6 trang báo cáo — luôn dùng đúng `DataFrame`/`Figure` đã hiển thị (đã qua RBAC ở service), không query DB riêng cho export.
4. Test thật qua UI với cả 3 role (Admin/Manager/User), nhiều trang, mở lại file tải về xác nhận đúng dữ liệu + đúng dấu tiếng Việt.

### Lỗi/vấn đề thật gặp phải (nhiều, nên ghi bảng — đây là phần giá trị nhất)

| # | Vấn đề | Nguyên nhân | Cách phát hiện | Cách xử lý |
|---|---|---|---|---|
| 1 | `requirements.txt` thiếu `plotly` và `openpyxl` dù cả 2 đã dùng ngầm định từ Tuần 4/5 | Lỗ hổng reproducibility có từ trước, không liên quan trực tiếp bước 6.1 nhưng phát hiện khi rà lại file này | Đọc trực tiếp `requirements.txt` đối chiếu với `import` thực tế trong code, không giả định | Bổ sung 2 dòng vào `requirements.txt`, lấy đúng version đang cài qua `pip show` |
| 2 | Nút "Xuất PDF" gọi thẳng `build_pdf_report_bytes()` trong `data=` của `st.download_button` làm kaleido render lại ở MỌI lần Streamlit rerun (kể cả chỉ đổi filter), không phải khi bấm nút | Cách Streamlit đánh giá lại `data=` ở mọi rerun trang, khác với giả định ban đầu (nút rẻ như Excel) | Test tay, thấy chart bị render lại liên tục dù không bấm Xuất PDF | Tách 2 bước cho riêng PDF: bấm "Tạo PDF" trước → mới hiện nút tải — Excel giữ nguyên 1 nút vì không tốn kaleido |
| 3 | `kaleido` có thể treo vô thời hạn khi render chart, không trả lỗi cũng không timeout tự nhiên | Chrome con do kaleido khởi động bị crash-loop (`Network service crashed, restarting service`, `GPU process has crashed` trong log Chrome), nghi do phần mềm bảo mật (Kaspersky) trên máy dev giám sát/hạn chế tiến trình con headless — KHÔNG xác định được nguyên nhân dứt điểm | Test cô lập bằng script tối thiểu ngoài repo, thử cả kaleido 0.2.1 và 1.4.0, chạy thẳng `chrome.exe` mà kaleido tải về (thoát ngay lập tức, exit code 0, không log — hành vi bất thường của Chromium) | Bọc timeout 20s thủ công bằng `threading.Thread(daemon=True)` (không dùng `ThreadPoolExecutor` — nó `atexit` join thread không-daemon, sẽ treo cả tiến trình Streamlit khi restart/stop nếu kaleido treo); nếu timeout/lỗi, PDF vẫn build tiếp KHÔNG có ảnh chart, thay bằng 1 dòng ghi chú — không để người dùng nhận lỗi trắng |
| 4 | Giả thuyết ban đầu "đường dẫn dự án có khoảng trắng (`Lacco Dashboard`) gây lỗi kaleido" | — | Test lại script kaleido tối thiểu ở `C:\tmp` (không dấu cách) — vẫn treo y hệt | **Giả thuyết SAI, đã loại trừ bằng thực nghiệm** — không phải do đường dẫn, quay lại nghi vấn phần mềm bảo mật/môi trường Windows |
| 5 | Nghi ngờ `streamlit run src/app/main.py` lỗi `ModuleNotFoundError: No module named 'src'` như tài liệu mô tả (CLAUDE.md mục 5) | Chạy lệnh từ sai thư mục làm việc (cwd) ở 1 lần thử trước đó | Chạy lại từ terminal mới, đúng thư mục gốc repo, không set `PYTHONPATH` tay | **Không phải lỗi thật** — tài liệu CLAUDE.md mục 5 đúng, không cần sửa |

## Kết quả thu được

- File mới: `src/services/export_utils.py` (381 dòng).
- Sửa 6 trang báo cáo (`src/app/pages/1..6`) — thêm export cho toàn bộ 20 cặp chart+bảng.
- `requirements.txt`: +4 dòng (`plotly`, `openpyxl`, `reportlab`, `kaleido==0.2.1` — pin bản cũ hơn vì bản `1.4.0` lỗi ngay `BrowserFailedError` trên máy test).
- Commit `9942a7e8`, push lên `main`, CI `lint-and-test` xanh (run #19, ~50s).
- Excel: xác nhận đúng dữ liệu + đúng dấu tiếng Việt qua UI thật, cả 3 role, đúng RBAC theo từng role (Admin xem hết, Manager theo Khối/Phòng, User theo phạm vi hẹp nhất).
- PDF: font tiếng Việt + graceful fallback đã xác nhận đúng ở mức hàm (function-level test, không qua UI thật do giới hạn thời gian phiên) — **chưa xác nhận được render chart thành công trên máy dev hiện tại** (xem vấn đề #3), nhưng tính năng luôn trả về PDF hợp lệ (có hoặc không có ảnh chart).

## Bài học rút ra

- **Một tính năng "làm đúng yêu cầu" (PDF có chart) có thể phụ thuộc vào 1 thành phần hạ tầng (Chrome headless qua kaleido) không hoàn toàn nằm trong tầm kiểm soát của code** — khi thành phần đó không ổn định trên 1 môi trường cụ thể, cách xử lý đúng không phải là cố ép nó chạy bằng mọi giá, mà là thiết kế graceful fallback để tính năng chính (xuất được file) không bao giờ thất bại hoàn toàn, dù phần "đẹp hơn" (có chart) có thể tạm thời không khả dụng.
- **Đừng vội tin giả thuyết đầu tiên, kể cả giả thuyết nghe hợp lý** — "đường dẫn có khoảng trắng" là 1 giả thuyết cụ thể, dễ kiểm chứng, hợp lý về mặt kỹ thuật (đã có tiền lệ với các công cụ dòng lệnh khác trên Windows) nhưng SAI khi test thực nghiệm. Luôn thiết kế 1 phép thử loại trừ rõ ràng (cô lập biến số) thay vì chỉ suy luận.
- **1 tính năng phụ thuộc trình duyệt headless cần được test riêng trên đúng môi trường đích trước khi tin tưởng** — môi trường máy dev (có phần mềm bảo mật, cấu hình riêng) không đại diện chắc chắn cho môi trường production (Windows Server ở bước 7.2). Đây là rủi ro đã ghi nhận, cần test lại độc lập trước go-live, không giả định "chạy được ở dev thì chạy được ở production".
- **Rà lại `requirements.txt` định kỳ, không chỉ khi thêm thư viện mới** — dự án đã 2 lần phát hiện thư viện dùng ngầm định nhưng thiếu khai báo (Tuần 6: `plotly`, `openpyxl`) — nên là 1 việc kiểm tra chủ động, không chờ đến khi máy mới cài đặt lỗi mới phát hiện.

## Kết quả

Bước 6.1 hoàn thành: 6/6 trang báo cáo có nút xuất Excel (hoạt động đầy đủ, đã xác minh qua UI thật) và xuất PDF (hoạt động ổn định kể cả khi chart không render được, nhờ graceful fallback) — commit `9942a7e8`, CI xanh. Rủi ro môi trường về kaleido/Chrome headless trên Windows Server thật được ghi nhận rõ, mang sang bước 7.2 để kiểm tra độc lập trước khi go-live.
