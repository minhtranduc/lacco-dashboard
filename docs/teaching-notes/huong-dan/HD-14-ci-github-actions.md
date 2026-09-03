# HD-14: CI/CD tối giản cho dự án solo bằng GitHub Actions

**Tuần:** 3 — Auth, RBAC & bảo mật | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 03/09/2026

## Mục tiêu

Thiết lập pipeline CI tối giản trên GitHub Actions: tự động chạy lint (Ruff) + test (pytest, đã có từ bước 3.3) mỗi khi push/mở PR vào `main`/`dev` — để lỗi cú pháp hay test hỏng bị bắt ngay khi push, không phải đợi tự nhớ chạy tay.

## Giải thích khái niệm: vì sao "CI tối giản" thay vì đầy đủ CI/CD

Với dự án 1 người (không có team review chéo), giá trị lớn nhất của CI không phải là quy trình duyệt PR phức tạp, mà đơn giản là **1 người ngoài (máy chủ GitHub) chạy lại đúng test/lint trên 1 môi trường sạch**, không lẫn với bất kỳ cấu hình/dữ liệu nào chỉ có trên máy cá nhân. Vì vậy bước này CHỈ dừng ở lint + test tự động — chưa làm CD (tự động deploy), việc đó chưa cần thiết ở Giai đoạn 1 (chưa go-live).

## Cách tiếp cận / Quy trình đã dùng

1. Quyết định kỹ thuật (không phải quyết định nghiệp vụ, tự chốt không cần hỏi COO): chọn **Ruff** làm công cụ lint + format — CLAUDE.md mục 3/4 chưa chốt công cụ cụ thể, Ruff phù hợp vì nhanh, gộp cả lint và format trong 1 tool, ít cấu hình cho dự án học 1 mình.
2. Thêm `pyproject.toml` với cấu hình Ruff tối giản (`select = ["E", "F", "I", "W"]` — lỗi cú pháp, biến/import không dùng, sắp xếp import, style cơ bản; KHÔNG bật rule khắt khe như bắt buộc docstring theo 1 chuẩn cố định hay đo độ phức tạp hàm, để tránh phải sửa hàng loạt không cần thiết ở lần đầu áp dụng).
3. Chạy Ruff lần đầu trên TOÀN BỘ code cũ (Tuần 2 + bước 3.1–3.3), giống cách đã làm với checklist bảo mật ở bước 3.2 — công cụ kiểm tra mới ra thì phải quét ngược lại code đã có, không chỉ áp dụng từ nay về sau.
4. Viết `.github/workflows/ci.yml`: job `lint-and-test` chạy trên `ubuntu-latest`, Python 3.12 (đúng bản đã chốt ở CLAUDE.md mục 3), cài `requirements.txt`, chạy `ruff check`, chạy `pytest tests/ --cov=src/auth`. Không cấu hình MySQL service hay biến môi trường `.env` trong workflow — vì toàn bộ test ở bước 3.3 đã thiết kế nhận `engine=` SQLite in-memory, không gọi `get_engine()`/đọc `.env` (khoản đầu tư đúng lúc từ bước 3.3, trả lãi ngay ở bước này).
5. Trước khi commit, tách bước "chạy CI thật" thành việc kiểm tra bắt buộc cuối cùng — không coi file `.yml` tồn tại là "xong việc", phải xác nhận GitHub thực sự chạy và trả về xanh.

### Kết quả lần quét Ruff đầu tiên trên toàn bộ code cũ

| Loại | Số lượng | Xử lý |
|---|---|---|
| Lỗi tự sửa được (`--fix`) | 3 (đều import-order, rule `I`) | Tự sửa ở `tests/conftest.py`, `src/db/models/dimension.py`, `src/services/import_schemas/registry.py` — chạy lại test xác nhận không hỏng gì |
| Lỗi còn lại sau `--fix` | 9 (toàn bộ `E501` — dòng quá 88 ký tự, dài nhất 95 ký tự) | Xem xét từng dòng: 8/9 là code bình thường (chữ ký hàm/lệnh gọi hàm dài) → để `ruff format` tự động bọc lại; 1/9 là chuỗi f-string tiếng Việt tự nhiên (`src/app/main.py`) → giữ nguyên câu, thêm `# noqa: E501` kèm comment giải thích lý do, không ép xuống dòng làm vỡ câu |
| File cần format lại (`ruff format`) | 13/29 file | Chạy `ruff format` áp dụng thật — chỉ bọc lại dòng dài/comprehension, không đổi logic (xác nhận lại bằng chạy test sau format) |

### Lỗi thật gặp phải khi chạy CI lần đầu

| # | Lỗi | Nguyên nhân | Cách phát hiện | Cách xử lý |
|---|---|---|---|---|
| 1 | Run CI đầu tiên (`33717255503`) FAIL ở bước Test: `ModuleNotFoundError: No module named 'src'` khi pytest load `conftest.py` | Trên máy cá nhân, test luôn được chạy qua `python -m pytest` — cách này tự thêm thư mục hiện tại vào `sys.path`. Trong `ci.yml`, bước Test gọi thẳng lệnh `pytest` (console-script) — không tự thêm thư mục gốc dự án vào `sys.path`, nên `import src...` trong test thất bại. Đây là khác biệt hành vi giữa 2 cách gọi cùng 1 công cụ, không phải lỗi code hay lỗi test | GitHub Actions trả về log lỗi rõ ràng ngay ở bước Test, không mơ hồ | Thêm `[tool.pytest.ini_options]` với `pythonpath = ["."]` vào `pyproject.toml` — ép pytest luôn thêm thư mục gốc vào `sys.path` dù được gọi theo cách nào. Verify lại cục bộ bằng đúng lệnh `pytest` trần (giống hệt CI, không dùng `python -m`) trước khi push lại, để không lặp lại kiểu lỗi "chỉ lộ ra trên CI, máy mình không thấy" |

Run thứ 2 (`33717402791`) chạy xanh — đã tự xác minh lại bằng cách gọi thẳng GitHub REST API công khai (`GET /repos/.../actions/runs/{id}` và `.../jobs`), không chỉ tin log CLI báo lại: `conclusion: success` cho cả 2 bước Lint và Test.

## Kết quả thu được

Commit `66edfb4` (18 file: `pyproject.toml`, `.github/workflows/ci.yml`, `requirements.txt` + 13 file được Ruff format lại) và `302b2ed` (fix `pythonpath`, 1 file).

Pipeline CI thật trên GitHub: [run `33717402791`](https://github.com/minhtranduc/lacco-dashboard/actions/runs/33717402791) — trạng thái `completed / success`, cả 2 bước Lint (Ruff) và Test (pytest, 13 test, coverage `src/auth/` 78%) đều xanh, chạy trên `ubuntu-latest` + Python 3.12, không cần bất kỳ cấu hình MySQL/`.env` nào.

## Bài học rút ra

- **"File cấu hình CI đã viết xong" và "pipeline CI thực sự chạy được" là 2 việc khác nhau** — bước này chỉ được coi là hoàn thành sau khi có bằng chứng 1 lần chạy thật trả về xanh trên GitHub, không phải khi file `.yml` được tạo ra và trông có vẻ đúng cú pháp.
- **Môi trường CI luôn có ít nhất 1 khác biệt ngầm so với máy cá nhân, dù nhỏ** — ở đây là cách `sys.path` được thiết lập khi gọi `pytest` trực tiếp so với `python -m pytest`. Khoản đầu tư ở bước 3.3 (test không phụ thuộc MySQL/`.env`) đã loại bỏ được lớp khác biệt lớn nhất (kết nối DB), nhưng vẫn còn những khác biệt nhỏ hơn cần chính CI báo ra mới phát hiện được — không có cách nào lường trước 100% chỉ bằng suy luận.
- **Áp dụng 1 công cụ kiểm tra mới (Ruff) lên toàn bộ code cũ, không chỉ code mới** — tiếp tục đúng nguyên tắc đã dùng ở bước 3.2 với `qa-reviewer-agent`. Lần này phát hiện phần lớn "lỗi" chỉ là style (dòng dài), không phải lỗi thật — nhưng vẫn cần nhìn qua từng dòng trước khi quyết định cách sửa (bọc dòng tự động vs. giữ nguyên + `noqa`), không áp dụng máy móc 1 cách sửa cho mọi trường hợp.
- **Xác minh trạng thái CI qua GitHub REST API công khai** (không cần đăng nhập, chỉ cần repo public) là 1 kênh xác minh độc lập tốt, không phụ thuộc vào việc CLI cục bộ có cài/đăng nhập sẵn `gh` hay không — tương tự tinh thần "luôn có đường xác minh dự phòng" đã áp dụng từ bước 3.1 (khi MCP không nạp được, dùng `db_connection.py` thay thế).

## Kết quả

Pipeline CI cơ bản đã hoạt động thật trên GitHub Actions: mỗi lần push/PR vào `main`/`dev` đều tự động chạy Ruff (lint) và pytest (13 test, coverage 78% cho `src/auth/`) trên môi trường sạch `ubuntu-latest` + Python 3.12, không cần MySQL hay `.env`. Xác nhận độc lập qua GitHub API: run mới nhất `completed/success`. Gặp và xử lý đúng 1 lỗi CI-config thật (thiếu `pythonpath`), không phải lỗi code — case study điển hình cho việc "chạy được cục bộ" chưa chắc "chạy được trên CI".
