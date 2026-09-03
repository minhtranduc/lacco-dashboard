# Nhật ký Tuần 3 — Auth, RBAC & bảo mật

**Dự án:** Dashboard LACCO — Giai đoạn 1 (WebApp MVP) | **Tuần:** 3/8 | **Người thực hiện:** Minh Tran (COO) | **Ngày viết:** 03/09/2026

> Tài liệu này là nguyên liệu thô cho case study "Claude for Business" — ghi lại đúng những gì đã xảy ra (kể cả lỗi và đường vòng), không phải bản tường thuật lý tưởng hoá.

## 1. Tổng quan

Tuần 3 đặt mục tiêu: xây module đăng nhập + RBAC 3 cấp thật (không chỉ schema như Tuần 2), thiết lập checklist review bảo mật, viết bộ test tự động đầu tiên, và cấu hình CI cơ bản. Đây là tuần đầu tiên dự án chạm vào bảo mật thật (bcrypt, session, phân quyền dữ liệu) và cũng là tuần đầu tiên có "lưới an toàn" tự động (test + CI) thay vì chỉ kiểm tra tay.

**Kết quả:** 5/5 bước hoàn thành. Về lịch: khung dự kiến ban đầu là "10/08–16/08/2026", thực tế Tuần 3 tách làm 2 đợt cách nhau khá xa — bước 3.1–3.2 hoàn thành 25/08/2026, sau đó tạm dừng theo lịch làm việc thật của COO, và bước 3.3–3.5 chỉ tiếp tục vào 03/09/2026 (cách nhau 9 ngày). Ghi nhận trung thực: đây là khoảng trễ lớn nhất từ đầu dự án so với khung dự kiến, nhưng không ảnh hưởng chất lượng — điểm tạm dừng (cuối bước 3.2) được chốt bằng 1 đợt rà soát đầy đủ (xem mục 5), nên khi quay lại ở 03/09 không mất thời gian dò lại ngữ cảnh.

## 2. Đối chiếu tiêu chí nghiệm thu

Tiêu chí ở mục 8 Kế hoạch triển khai (7 mục) vẫn là tiêu chí **cuối Giai đoạn 1**, chưa áp dụng từng tuần. Tuần 3 đặt nền móng như sau:

| Tiêu chí Giai đoạn 1 (mục 8) | Nền móng Tuần 3 đã đặt |
|---|---|
| RBAC 3 cấp hoạt động đúng theo A/B/C, Khối/Phòng | Lần đầu tiên hoạt động THẬT (Tuần 2 mới chỉ có bảng nền) — `compute_data_scope()` tính đúng phạm vi Admin (toàn bộ)/Manager (theo Phòng)/User (theo nhân viên), có 13 test tự động xác nhận, đã đăng nhập thử thật với 3 tài khoản test |
| Audit log và login history ghi nhận đầy đủ | Ghi thật lần đầu — mọi lần đăng nhập (kể cả sai mật khẩu) ghi `login_history`; thao tác đặt lại mật khẩu test ghi `audit_log` (không lộ hash/plaintext) — đã test tự động cả 2 nhánh thành công/thất bại |
| Có bộ tài liệu case study đầu tiên | HD-11 → HD-14 hoàn thành (4 tài liệu), nhật ký Tuần 3 (file này) là nhật ký thứ ba |
| 6 nhóm báo cáo, Xuất Excel/PDF, chịu tải 20 người dùng, backup/restore | Chưa thuộc phạm vi Tuần 3 — các tiêu chí này thuộc Tuần 4 trở đi (module báo cáo) và Tuần 6–7 (export, hiệu năng, backup) |

Ngoài 7 tiêu chí chính thức, Tuần 3 còn đặt 1 nền móng không nằm trong mục 8 nhưng có giá trị lâu dài: **bộ test tự động + pipeline CI** — không phải tiêu chí nghiệm thu MVP, nhưng là điều kiện để các tuần sau (đặc biệt Tuần 4 module báo cáo) không phải kiểm tra tay lặp lại mỗi lần sửa code.

## 3. Chi tiết 5 bước Tuần 3

| Bước | Tên | Trạng thái | Ngày hoàn thành thực tế | Mã HD |
|---|---|---|---|---|
| 3.1 | Xây Auth & RBAC | Hoàn thành | 25/08/2026 | HD-11 |
| 3.2 | Checklist bảo mật cho reviewer | Hoàn thành | 25/08/2026 | HD-12 |
| 3.3 | Viết test đầu tiên | Hoàn thành | 03/09/2026 | HD-13 |
| 3.4 | Cấu hình CI cơ bản | Hoàn thành | 03/09/2026 | HD-14 |
| 3.5 | Review & nhật ký Tuần 3 | Hoàn thành | 03/09/2026 | (file này) |

## 4. Quyết định kiến trúc & lý do

- **Admin luôn xem toàn bộ dữ liệu, không giới hạn theo Khối/Phòng** (quyết định nghiệp vụ, COO xác nhận trực tiếp qua câu hỏi rõ ràng ở bước 3.1) — agent code ban đầu suy luận Admin có gắn `employee_id` vẫn bị giới hạn như Giám đốc Khối, nhưng đây mâu thuẫn với định nghĩa gốc "Admin = quản trị hệ thống" ở CLAUDE.md. Đã sửa `scope.py`, ghi thẳng quyết định vào CLAUDE.md mục 6 và persona `auth-rbac-agent.md` để không bị suy luận lại sai ở lần sau.
- **`streamlit-authenticator` đảm nhiệm cả bcrypt lẫn form đăng nhập** (quyết định kỹ thuật, theo đúng CLAUDE.md mục 3 đã chốt từ trước) — không tự viết lại logic hash.
- **Tách quyền "review" khỏi quyền "sửa" ở cấp subagent** (quyết định kỹ thuật, bước 3.2) — `qa-reviewer-agent` chỉ có Read/Grep/Glob/Bash, không có Write/Edit, khác hẳn 3 subagent trước — tránh tình huống "vừa đá bóng vừa thổi còi".
- **Test tự động dùng SQLite in-memory thay vì kết nối MySQL "lacco" thật** (quyết định kỹ thuật, bước 3.3) — tận dụng tham số `engine=` đã thiết kế sẵn từ bước 3.1; lý do quyết định không chỉ là tốc độ mà còn vì bước 3.4 (CI) sắp chạy trên GitHub Actions, môi trường đó không có đường kết nối vào MySQL nội bộ công ty.
- **Chọn Ruff làm công cụ lint + format** (quyết định kỹ thuật, bước 3.4) — CLAUDE.md chưa chốt công cụ cụ thể; Ruff phù hợp vì nhanh, gộp lint+format trong 1 tool, ít cấu hình cho dự án học 1 mình.
- **CI chỉ dừng ở lint + test, chưa làm CD (tự động deploy)** (quyết định phạm vi, kỹ thuật) — chưa cần thiết ở Giai đoạn 1 khi chưa go-live; tránh làm phức tạp hoá quá sớm.

## 5. Vấn đề gặp phải & cách Claude hỗ trợ giải quyết

| Vấn đề | Cách xử lý |
|---|---|
| Mật khẩu MySQL root chưa từng được đổi kể từ sự cố lộ ở bước 2.3 (`password_last_changed` = 21/05/2025 — cũ hơn cả sự cố) | Không chỉ hỏi "đã đổi chưa" mà tự truy vấn `mysql.user` lấy bằng chứng thời gian cụ thể trước khi bắt đầu code Auth. COO đổi mật khẩu ngay trong phiên; Claude cập nhật `.env`/MCP và xác minh lại bằng kết nối thật qua `db_connection.py` |
| Phạm vi Admin — agent tự suy luận 2 cách hợp lý về kỹ thuật nhưng khác nhau (giới hạn theo Khối vs. toàn bộ) | Agent tự liệt kê thành mục "cần xác nhận" thay vì tự chọn; đưa câu hỏi rõ ràng cho COO quyết định, không đoán |
| File `.git/index.lock` kẹt lại 2 lần trong tuần (do lệnh `git status`/`git log` chẩn đoán không có quyền tự dọn) | Xác nhận đây là file khoá 0 byte vô hại (không phải tiến trình git đang chạy thật), hướng dẫn xoá bằng lệnh xoá file thường qua CLI thật của COO — không dùng lệnh git để xoá |
| Prompt giao việc bước 3.3 quá dài (~150 dòng), bị cắt cụt giữa chừng khi dán qua giao diện chat — CLI chỉ nhận được phần cài đặt, mất phần mô tả test case cụ thể | CLI tự nhận ra thiếu và báo lại thay vì đoán bừa; tiếp tục dán phần còn thiếu vào đúng phiên đang chạy (không mở phiên mới, giữ nguyên ngữ cảnh `conftest.py` đã viết). Từ bước 3.4 trở đi, chủ động chia prompt dài thành 2 phần ngay từ đầu để tránh lặp lại |
| Run CI đầu tiên FAIL: `ModuleNotFoundError: No module named 'src'` khi pytest chạy trên GitHub Actions | Nguyên nhân: CI gọi thẳng lệnh `pytest`, khác với `python -m pytest` dùng khi test cục bộ — cách gọi khác nhau dẫn đến `sys.path` khác nhau. Fix bằng `pythonpath = ["."]` trong `pyproject.toml`, verify lại cục bộ bằng đúng lệnh `pytest` trần trước khi push lại |

## 6. Prompt tiêu biểu đã dùng trong tuần

- **Thiết kế hàm nghiệp vụ với tham số `engine=None`/tương đương ngay từ đầu**, kể cả khi chưa viết test — chi phí thêm rất nhỏ lúc viết code (bước 3.1), nhưng giúp bước viết test (3.3) không phải quay lại sửa code nguồn hay dựng mock phức tạp.
- **Chia nhỏ prompt dài theo từng "VIỆC" và dán/chạy tuần tự**, thay vì gộp 1 khối rất dài — áp dụng từ bước 3.4 sau khi rút kinh nghiệm từ lần bị cắt cụt ở bước 3.3.
- **Áp dụng 1 checklist/công cụ kiểm tra mới lên TOÀN BỘ code cũ ngay lần đầu**, không chỉ code mới từ nay về sau — dùng lại đúng mẫu hình đã áp dụng cho `qa-reviewer-agent` (bước 3.2) sang cả Ruff (bước 3.4).
- **Xác minh trạng thái CI qua GitHub REST API công khai** (`curl https://api.github.com/repos/.../actions/runs/{id}`) thay vì chỉ tin log CLI báo lại — không cần đăng nhập nếu repo public, là kênh xác minh độc lập không phụ thuộc việc `gh` CLI có sẵn trên máy đang thao tác hay không.

## 7. Ước tính thời gian tiết kiệm so với làm thủ công

*(Ước tính định tính, chưa phải số đo chính xác — dùng tham khảo cho slide báo cáo lãnh đạo, không dùng làm cam kết ROI chính thức.)*

| Việc | Làm thủ công (ước tính) | Với Claude | Ghi chú |
|---|---|---|---|
| Xây module Auth + middleware RBAC (7 file, 943 dòng) | Vài ngày (tra cứu `streamlit-authenticator`, tự thiết kế truy vấn UNION nhiều bảng) | Trong 1 phiên, kèm tự đăng nhập thử thật để xác minh | Quyết định nghiệp vụ (phạm vi Admin) vẫn cần COO xác nhận — AI không tự quyết thay |
| Viết checklist bảo mật 9 mục + quét toàn bộ code cũ | Có thể mất nửa ngày đọc lại code thủ công từng file | Vài chục phút cho cả quét lẫn tự sửa 1 lỗi phát hiện được | Tách quyền review/sửa giúp kết quả đáng tin hơn là tự AI vừa kiểm vừa sửa lặng lẽ |
| Viết 13 test case + fixture SQLite cho module Auth | Có thể mất 1 ngày (thiết kế fixture, debug môi trường test) | Trong 1 phiên (2 lượt do prompt bị cắt), coverage đo được ngay | Vẫn cần Claude tự đọc kỹ logic thật (`scope.py`) trước khi seed dữ liệu test, không đoán |
| Thiết lập CI (Ruff + GitHub Actions) từ đầu | Có thể mất nửa ngày đến 1 ngày (tra cứu cú pháp workflow, tự debug lỗi môi trường CI) | Trong 1 phiên, phát hiện và fix đúng 1 lỗi CI-config thật | Lỗi `pythonpath` là loại lỗi chỉ lộ ra trên CI — vẫn cần chạy thật để biết, AI không đoán trước được 100% |

## 8. Bài học rút ra cho Tuần 4

- **Tạm dừng dài giữa các bước (9 ngày ở giữa Tuần 3) không gây rủi ro nếu điểm dừng được chốt bằng 1 đợt rà soát đầy đủ** — thói quen này (rà soát CLAUDE.md/agent/tracker mỗi khi tạm dừng) nên tiếp tục duy trì, đặc biệt quan trọng hơn nữa ở Tuần 4 khi bắt đầu module báo cáo (nhiều quyết định "Đã rõ"/"Cần làm rõ" dễ bị quên nếu không rà soát định kỳ).
- **"Chạy được cục bộ" chưa chắc "chạy được trên CI"** — bài học cụ thể từ lỗi `pythonpath`; áp dụng rộng hơn: bất kỳ code nào sắp chạy trong CI nên được test bằng đúng cách CI sẽ gọi nó, không phải cách tiện nhất lúc code (`python -m pytest` so với `pytest` trần là ví dụ điển hình).
- **Rủi ro "1 khách hàng gắn 2 nhân viên khác nhau ở 2 bảng khác nhau" (Manager/User scope suy luận từ UNION `sales_order`/`debt`/`price_request`)** đã được `auth-rbac-agent` tự nêu ở bước 3.1 nhưng chưa xử lý — cần nhớ lại đúng lúc bắt đầu module báo cáo Khách hàng ở Tuần 4, vì lúc đó rủi ro này mới thực sự ảnh hưởng đến số liệu hiển thị.
- **Prompt rất dài nên chủ động chia nhỏ ngay từ đầu**, không đợi bị cắt cụt rồi mới rút kinh nghiệm — áp dụng ngay từ Tuần 4 cho mọi prompt giao việc nhiều bước.

## 9. Việc cần làm tiếp (Tuần 4)

- Bước 4.1: bắt đầu module báo cáo đợt 1 (xem chi tiết trong `Lich_trinh_thuc_hien_8_tuan_LACCO.xlsx`).
- Trước khi code logic báo cáo Khách hàng: xử lý rủi ro "1 khách hàng gắn 2 nhân viên khác nhau" đã ghi nhận ở HD-11 (mục 8 phía trên).
- Chốt dần các mục còn mở trong `erd-tuan-02.md` liên quan trực tiếp đến nhóm báo cáo sắp code ở Tuần 4 — kiểm tra lại danh sách trước khi bắt đầu, ưu tiên các mục ảnh hưởng công thức hiển thị.
- Tạo user MySQL least-privilege thay cho `root` trong `.env` — tồn đọng từ Tuần 1, nhắc lại ở HD-11, vẫn chưa thực hiện (mức ưu tiên tăng dần vì RBAC/Auth nay đã chạy thật trên tài khoản `root`).
- `_DEV_FALLBACK_COOKIE_KEY` hardcoded trong `authentication.py:53` — cần đổi thành raise lỗi thay vì fallback êm trước khi có môi trường production thật (chưa cấp bách trong Giai đoạn 1, nhưng không nên quên qua nhiều tuần).
- `admin_actions.py` hiện 0% coverage test (ngoài phạm vi bước 3.3) — cân nhắc bổ sung khi module quản trị tài khoản thực sự được dùng đến (không cấp bách ngay Tuần 4).
