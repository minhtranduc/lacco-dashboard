# HD-13: Viết test tự động cùng Claude Code — bắt đầu từ đâu

**Tuần:** 3 — Auth, RBAC & bảo mật | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 03/09/2026

## Mục tiêu

Cài `pytest` + `pytest-cov` và viết bộ test tự động đầu tiên của dự án, cho module `src/auth/` (đã xây ở bước 3.1) — vừa để có "lưới an toàn" khi sửa code sau này, vừa để chuẩn bị nền tảng bắt buộc cho GitHub Actions CI ở bước 3.4 (CI không có quyền/khả năng kết nối vào MySQL "lacco" nội bộ của công ty, nên test phải tự chạy được độc lập).

## Cách tiếp cận / Quy trình đã dùng

1. Không giao việc này cho 1 subagent riêng (khác 4 việc trước) — bước này thuộc dạng "kỹ năng nền" (viết test), không phải 1 tầng kiến trúc riêng như `db-schema-agent`/`auth-rbac-agent`, nên giao trực tiếp cho Claude Code qua 1 prompt tự chứa đầy đủ.
2. Quyết định kỹ thuật quan trọng nhất trước khi viết dòng test đầu tiên: **test có được phép kết nối MySQL "lacco" thật không?** Câu trả lời là KHÔNG, vì lý do rất cụ thể — bước 3.4 sắp tới sẽ chạy test này trong GitHub Actions, môi trường đó không có VPN/mạng nội bộ để chạm vào MySQL của công ty. May mắn là `authenticate_and_log()` và `compute_data_scope()` (viết ở bước 3.1) đã có sẵn tham số `engine=None` "dùng trong test" — cho thấy lúc thiết kế bước 3.1 đã có ý thức chừa chỗ cho việc này, dù lúc đó chưa viết test.
3. Vì vậy chọn kiến trúc test: SQLite in-memory (`sqlalchemy.create_engine("sqlite:///:memory:")`) thay vì mock thủ công từng hàm DB — tận dụng nguyên bộ model SQLAlchemy thật đã có (`Base.metadata.create_all()`), test chạy đúng logic ORM thật, không phải logic giả lập tay.
4. Viết `tests/conftest.py` với 2 fixture dùng chung: `db_engine` (engine SQLite sạch cho mỗi test) và `seeded_scope_data` (dữ liệu mẫu tối thiểu đủ phân biệt 3 nhánh RBAC: Admin/Manager/User).
5. Viết 3 file test tương ứng 3 file nguồn: `test_hashing.py`, `test_scope.py`, `test_authentication.py` — 13 test case, seed dữ liệu qua ORM (không dùng raw SQL, kể cả trong test, theo đúng CLAUDE.md mục 4).
6. Chạy `pytest --cov=src/auth --cov-report=term-missing` để vừa xác nhận test pass vừa đo được đang che phủ bao nhiêu % code thật.

### Lỗi thật gặp phải

| # | Lỗi | Nguyên nhân | Cách phát hiện | Cách xử lý |
|---|---|---|---|---|
| 1 | Prompt giao việc dài bị cắt cụt giữa chừng khi dán vào Claude Code — CLI chỉ nhận được tới VIỆC 1–2 (cài đặt), mất hẳn VIỆC 3 trở đi (nội dung test case cụ thể) | Giới hạn thực tế của việc copy-paste 1 khối văn bản rất dài (~150 dòng) qua giao diện chat — không phải lỗi của CLI hay của nội dung prompt | CLI tự nhận ra thiếu và báo lại qua recap: "waiting on you to resend the cut-off VIỆC 3 instructions" thay vì tự đoán bừa | Không mở phiên CLI mới (mất ngữ cảnh `conftest.py` vừa viết) — dán tiếp đúng phần còn thiếu (VIỆC 3→7) vào cùng cửa sổ đang chạy. Bài học thao tác: với prompt rất dài, nên cân nhắc chia nhỏ theo từng VIỆC ngay từ đầu thay vì gộp 1 khối, đặc biệt khi qua giao diện chat có thể cắt bớt |

Ngoài lỗi thao tác trên, phần code test tự nó không phát sinh lỗi/sửa đi sửa lại — 13/13 test pass ngay từ lần chạy đầu tiên báo cáo lại.

### Lưu ý kỹ thuật đáng chú ý (không phải lỗi, nhưng dễ mắc nếu không biết trước)

SQLite `:memory:` là cơ sở dữ liệu gắn theo **từng connection**, không phải theo tên file — nếu tạo engine kiểu mặc định, mỗi lần SQLAlchemy lấy 1 connection mới từ connection pool sẽ nhận về 1 database rỗng hoàn toàn khác (dữ liệu seed ở fixture "biến mất" một cách khó hiểu). Cách xử lý (đã đưa thẳng vào yêu cầu ngay từ đầu, không phải sửa sau khi gặp lỗi): ép SQLAlchemy dùng `poolclass=StaticPool` + `connect_args={"check_same_thread": False}`, để toàn bộ vòng đời 1 test chỉ dùng đúng 1 connection/1 database.

## Kết quả thu được

Commit `f4d1078` — 6 file, 376 dòng thêm mới (`requirements.txt`, `tests/conftest.py` 154 dòng, `tests/auth/test_hashing.py` 32 dòng, `tests/auth/test_scope.py` 106 dòng, `tests/auth/test_authentication.py` 78 dòng; xoá `tests/.gitkeep` vì thư mục đã có file thật).

Kết quả chạy `pytest tests/ -v --cov=src/auth --cov-report=term-missing`:

| File | Số dòng lệnh | Coverage | Ghi chú phần chưa che phủ |
|---|---|---|---|
| `hashing.py` | 6 | **100%** | — |
| `scope.py` | 48 | **96%** | Dòng 144–150 — 1 nhánh phụ chưa test (chấp nhận, không thuộc 3 nhánh chính RBAC) |
| `authentication.py` | 50 | **76%** | `build_credentials()`/`get_authenticator()` (dòng 65–77) — hàm dựng widget `streamlit_authenticator`, không nằm trong luồng `authenticate_and_log()` đã test |
| `admin_actions.py` | 12 | **0%** | Chưa có test — nằm ngoài phạm vi bước 3.3 (chỉ giao "viết test cho module auth", không phải toàn bộ `src/auth/`), không tự ý mở rộng phạm vi |
| **Tổng `src/auth/`** | **116** | **78%** | |

**13/13 test pass**, không phát hiện bug thật nào trong code `src/auth/` hiện có (không phải sửa lại `scope.py`/`authentication.py`/`hashing.py`).

Tự xác minh độc lập (đọc lại code, không chỉ tin báo cáo CLI):
- Đọc `git show --stat f4d1078` — đúng khớp danh sách 6 file đã báo cáo, `tests/.gitkeep` bị xoá (không phải "quên xoá" như lo ngại ban đầu).
- Đọc trực tiếp `tests/conftest.py`, `test_scope.py`, `test_authentication.py` — xác nhận fixture seed đúng cấu trúc phân biệt Manager (theo `department_id`) và User (theo `employee_id`) như đã yêu cầu, assertion cụ thể (so sánh đúng tập `customer_ids` kỳ vọng), không phải test hình thức (test rỗng hoặc chỉ `assert True`).
- Không tự chạy lại `pytest` được từ môi trường của Claude (máy ảo Linux dùng để cầu nối với máy người dùng không có cùng virtualenv/gói đã cài trên máy Windows thật) — đây là giới hạn môi trường đã biết (tương tự việc không nạp được MCP ở bước 3.1), xác minh bằng đọc code thay cho chạy lại được chấp nhận là đủ tin cậy trong trường hợp này.

## Bài học rút ra

- **Thiết kế "chừa chỗ cho test" ngay từ lúc viết code nghiệp vụ (bước 3.1) giúp bước viết test (3.3) rẻ hơn nhiều** — tham số `engine=None` thêm vào từ đầu chỉ tốn vài dòng lúc đó, nhưng giúp bước 3.3 không phải quay lại sửa `src/auth/` hay dựng mock phức tạp.
- **Ưu tiên SQLite in-memory (dùng ORM thật) hơn mock tay từng hàm DB** cho loại test này — vừa test được đúng hành vi ORM thật (không phải logic giả lập), vừa chạy nhanh, vừa không phụ thuộc mạng/DB nội bộ — điều kiện bắt buộc để chạy được trong CI ở bước 3.4.
- **Prompt giao việc quá dài có rủi ro bị cắt cụt khi dán qua chat** — nên chủ động chia nhỏ theo từng phần việc (VIỆC 1, 2, 3...) ngay từ đầu; nếu bị cắt, tiếp tục trong cùng phiên CLI đang chạy thay vì mở phiên mới, để không mất ngữ cảnh phần đã làm.
- **"13/13 pass" không đủ để coi module đã được test đầy đủ** — vẫn cần nhìn coverage % theo từng file để biết rõ đang test cái gì và CHƯA test cái gì (ở đây `admin_actions.py` 0% là biết trước và chấp nhận được, không phải bị bỏ sót ngoài ý muốn).

## Kết quả

Bộ test tự động đầu tiên của dự án đã chạy thật: 13 test cho `src/auth/`, 100% pass, coverage 78% toàn module (96–100% cho phần lõi RBAC/hashing, phần thấp hơn là các hàm ngoài luồng chính đã biết trước). Toàn bộ chạy trên SQLite in-memory, không đụng MySQL "lacco" thật — sẵn sàng để bước 3.4 (GitHub Actions CI) chạy lại đúng bộ test này mà không cần cấu hình gì thêm về kết nối DB.
