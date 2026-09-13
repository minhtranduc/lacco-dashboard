# HD-20: Cấu hình Sentry giám sát lỗi runtime

**Tuần:** 6 — Export, hiệu năng, giám sát lỗi | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 13/09/2026

## Mục tiêu

Cấu hình Sentry SaaS (free tier, quyết định đã chốt với COO — không self-host) để giám sát lỗi runtime, bắc cầu log Loguru hiện có (CLAUDE.md mục 4) sang Sentry, và xác minh THẬT bằng lỗi thử nghiệm xuất hiện trên dashboard sentry.io — không dừng ở code lý thuyết.

## Sai lệch phát hiện so với giả định ban đầu (quan trọng)

Prompt giao việc giả định dự án "đã có class Pydantic Settings dùng python-dotenv" và chỉ cần thêm 2 field vào đó. Kiểm tra thật (`grep -rl "BaseSettings"` toàn repo) cho thấy **KHÔNG có file nào như vậy** — cấu hình MySQL vẫn đọc trực tiếp qua `os.environ` trong `src/services/db_connection.py::build_mysql_url()`, dùng `python-dotenv` nhưng KHÔNG dùng Pydantic Settings. Bảng tech stack (CLAUDE.md mục 3) liệt kê "Config/biến môi trường: python-dotenv + Pydantic Settings" từ trước nhưng phần Pydantic Settings chưa từng được code thật.

**Xử lý:** tạo mới `src/services/config.py` làm class Pydantic Settings ĐẦU TIÊN của dự án (chỉ chứa `sentry_dsn`, `app_environment` — đúng phạm vi bước 6.3), đặt cùng layer `src/services/` như `db_connection.py` (tiền lệ đã có cho mối quan tâm hạ tầng/kết nối). KHÔNG refactor `db_connection.py` sang dùng class này — ngoài phạm vi bước 6.3, để riêng cho 1 bước sau nếu cần đồng bộ.

## Cách tiếp cận / Quy trình đã dùng

1. `pip index versions` xác nhận bản mới nhất ổn định tại thời điểm làm: `sentry-sdk==2.69.1`, `pydantic-settings==2.15.0` — pin cả 2 vào `requirements.txt` (xen alphabetically theo đúng quy ước file hiện có).
2. `src/services/config.py` — class `Settings(BaseSettings)` với `sentry_dsn: str | None = None`, `app_environment: str = "development"`, field đặt snake_case (PEP8) — `pydantic-settings` tự map case-insensitive sang biến môi trường viết hoa `SENTRY_DSN`/`APP_ENVIRONMENT`, không cần khai `alias` thủ công.
3. `.env.example` — thêm 2 dòng mẫu kèm comment giải thích lấy DSN ở sentry.io (Settings → Client Keys).
4. `src/services/monitoring.py` — hàm `init_sentry()`: chỉ init nếu có `SENTRY_DSN`, ngược lại log 1 dòng `logger.warning(...)` và return `False`, không raise. Tham số bắt buộc theo CLAUDE.md mục 6: `send_default_pii=False`, `include_local_variables=False`, `traces_sample_rate=0`, `environment=settings.app_environment`.
5. Bắc cầu Loguru → Sentry: **chọn Cách A** (Loguru sink riêng `_sentry_loguru_sink`, gọi thẳng `capture_exception()`/`capture_message()`) thay vì Cách B (propagate Loguru ngược về `logging` chuẩn) — lý do: Cách B cần thêm 1 lớp `PropagateHandler` trung gian và tự quản lý mapping level 2 chiều, dễ vỡ; Cách A tường minh, dễ test độc lập.
6. `src/app/main.py` — gọi `init_sentry()` ngay sau khối import, trước `st.set_page_config()` và mọi logic khác của app.
7. `scripts/test_sentry_integration.py` — script chẩn đoán rời (như `scripts/load_test_services.py` ở bước 6.2): raise `ValueError` thật trong try/except gọi `capture_exception()`, và `logger.error(...)` để test cầu nối Cách A. Chạy thật, `sentry_sdk.flush(timeout=10)` để đảm bảo event rời máy trước khi script thoát.

## Vướng mắc thật phát hiện khi test (không phải chờ đoán trước) — quan trọng nhất của bước này

Chạy `scripts/test_sentry_integration.py` lần đầu, kiểm tra dashboard `lacco.sentry.io/issues/` bằng `claude-in-chrome` (đăng nhập sẵn trong Chrome của COO) thấy **3 issue** xuất hiện thay vì 2 issue kỳ vọng (1 cho `capture_exception()`, 1 cho log ERROR qua Loguru):

- `LACCO-DASHBOARD-2` — `ValueError` từ `capture_exception()` (đúng kỳ vọng).
- `LACCO-DASHBOARD-1` — message sạch từ sink `_sentry_loguru_sink` (đúng kỳ vọng, Cách A).
- `LACCO-DASHBOARD-3` — **THÊM 1 issue không mong muốn**, nội dung là chuỗi Loguru đã format sẵn (`"2026-09-13 23:16:21.906 | ERROR | ... "`) — không phải do code tự viết.

**Nguyên nhân xác minh bằng cách đọc source `sentry_sdk`:** bản `sentry-sdk==2.69.1` có sẵn `sentry_sdk.integrations.loguru.LoguruIntegration`, và `sentry_sdk.init(...)` mặc định `auto_enabling_integrations=True` — tự động bật integration này ngay khi phát hiện package `loguru` đã cài trong môi trường, **kể cả không khai báo gì thêm**. Integration này tự bắt log Loguru cấp `ERROR+` (mặc định `event_level=40`) — trùng hoàn toàn với việc tự viết sink Cách A, gây gửi 2 event lên Sentry cho cùng 1 lỗi thật.

**Cách xử lý:** thêm `disabled_integrations=[LoguruIntegration()]` tường minh vào `sentry_sdk.init(...)` trong `init_sentry()` để tắt hẳn integration tự động, giữ đúng 1 đường bắt log duy nhất (sink tự viết). Xác minh lại bằng script ad-hoc (dedup check) — dashboard cho `LACCO-DASHBOARD-6` chỉ 1 event, không có issue "trùng định dạng raw" đi kèm — và chạy lại `scripts/test_sentry_integration.py` lần 2, xác nhận 2 sự kiện mới gộp vào đúng 2 issue cũ (`LACCO-DASHBOARD-1`, `LACCO-DASHBOARD-2`, tăng event count lên 2/issue do Sentry group theo fingerprint/stacktrace giống nhau) — **không** phát sinh issue thứ 3 nào nữa cho lần chạy sau khi đã tắt.

## Bằng chứng xác minh trên dashboard (thật, không phải mô tả lý thuyết)

Kiểm tra qua `claude-in-chrome`, project Sentry `lacco.sentry.io`, mục Issues → Feed, sau khi chạy đủ các script thử nghiệm ở trên:

| Issue | LACCO-DASHBOARD-# | Nội dung | Events |
|---|---|---|---|
| `ValueError` — lỗi thử nghiệm `capture_exception()` | 2 | `[test_sentry_integration] Lỗi thử nghiệm bước 6.3/HD-20 — xác minh sentry_sdk.capture_exception() hoạt động thật.` | 2 (2 lần chạy script, cùng stacktrace nên Sentry gộp) |
| Message sạch từ sink Cách A | 1 | `[test_sentry_integration] Lỗi thử nghiệm bước 6.3/HD-20 — xác minh cầu nối Loguru -> Sentry (Cách A...)` | 2 |
| Message raw trùng lặp (TRƯỚC khi tắt auto-integration) | 3 | `2026-09-13 23:16:21.906 \| ERROR \| ... — xác minh cầu nối Loguru...` | 1 (chỉ xuất hiện ở lần chạy TRƯỚC fix, không lặp lại sau fix) |
| Verify event_id thủ công (trước fix, có trùng) | 4, 5 | `[verify] test bridge event id capture` (2 issue riêng cho 1 lần log — bằng chứng lỗi trùng) | 1 mỗi issue |
| Verify dedup sau fix (đúng, không trùng) | 6 | `[verify-fix] dedup check after disabling auto LoguruIntegration` | 1 (không có issue song sinh) |

Event ID thật đã ghi nhận trong log chạy: `capture_exception()` → `496b144c483c4e8aac580eaa11187307` (lần 1) và `bac4ec4c66f943cfb97c4adb5d750cbe` (lần 2, sau fix); sink verify → `ac098bf9615446d99b56682a73e8e168`; dedup verify → `73a80cc90f17449d9eba17b5f9602def`.

## Kiểm tra bảo mật `.env`

Xác nhận thật (không giả định) bằng `git check-ignore -v .env` → khớp `.gitignore:151:.env` — file `.env` được Git bỏ qua đúng như kỳ vọng, `SENTRY_DSN` thật không lọt vào commit nào (đã kiểm tra `git status`/`git diff --stat` trước khi `git add` — chỉ 6 file dự kiến, không có `.env`).

## Bài học rút ra

- **Đừng tin giả định trong prompt giao việc nếu chưa xác minh bằng code thật** — prompt giả định đã có class Pydantic Settings, nhưng `grep` toàn repo cho thấy không có; may là phát hiện sớm (trước khi sửa nhầm file không tồn tại), không phải sau khi code sai.
- **`sentry_sdk.init()` mặc định TỰ BẬT nhiều integration theo package đã cài (`auto_enabling_integrations=True`), kể cả khi không khai báo gì** — đây là hành vi ẩn dễ gây trùng dữ liệu (ở đây là trùng event Loguru) nếu tự viết thêm tích hợp thủ công cho cùng 1 thư viện mà SDK đã hỗ trợ sẵn. Bài học áp dụng rộng hơn Sentry: khi tự viết cầu nối cho 1 thư viện log/monitoring, luôn kiểm tra xem SDK đích có tự động tích hợp sẵn thư viện đó không trước khi giả định "không viết thì không có gì xảy ra".
- **Xác minh bằng dashboard thật, không dừng ở "code chạy không lỗi"** — nếu chỉ kiểm tra script chạy xong không exception (không lỗi ở tầng code), sẽ KHÔNG phát hiện được lỗi trùng event — lỗi này chỉ lộ ra khi thật sự vào dashboard sentry.io đếm số issue, đúng tinh thần yêu cầu "test xác nhận hoạt động, không chỉ code lý thuyết" của bước này.

## Kết quả

Bước 6.3 hoàn thành: Sentry SaaS free tier đã cấu hình đúng 5 tham số bắt buộc (CLAUDE.md mục 6), cầu nối Loguru → Sentry hoạt động thật qua Cách A (sink riêng), đã phát hiện và xử lý 1 vướng mắc thật (SDK tự bật `LoguruIntegration` gây trùng event) bằng `disabled_integrations=[LoguruIntegration()]`. Xác minh bằng 4 lượt chạy thật + kiểm tra trực tiếp dashboard `lacco.sentry.io` (6 issue, event ID cụ thể ghi ở trên). `ruff check`/`ruff format --check` xanh trước commit, `pytest tests/` 13/13 pass (không ảnh hưởng), CI GitHub Actions xanh ngay lần push đầu (không lặp lại sự cố bỏ sót lint như HD-19).
