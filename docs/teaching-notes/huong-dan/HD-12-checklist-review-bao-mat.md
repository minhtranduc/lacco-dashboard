# HD-12: Checklist code review bảo mật do subagent thực hiện

**Tuần:** 3 — Auth, RBAC & bảo mật | **Đối tượng phù hợp:** Cả hai | **Ngày thực hiện:** 25/08/2026

## Mục tiêu

Thiết lập `qa-reviewer-agent` — subagent chuyên trách review bảo mật/chất lượng code theo 1 checklist cố định 9 mục (bám sát CLAUDE.md), đóng vai "chốt chặn cuối trước khi merge". Chạy lần đầu trên toàn bộ `src/` đã có từ Tuần 2 đến bước 3.1, để vừa kiểm chứng agent hoạt động đúng vừa dọn sạch code hiện tại trước khi Tuần 3 code tiếp.

## Cách tiếp cận

1. Viết persona `qa-reviewer-agent.md` — khác 3 subagent trước (`db-schema-agent`, `data-import-agent`, `auth-rbac-agent` đều có quyền Write/Edit để tự viết code), agent này **chỉ có quyền Read/Grep/Glob/Bash — không có Write/Edit**, đúng vai trò review-only: phát hiện và báo cáo, không tự sửa. Đây là điểm thiết kế quan trọng để tránh vừa đá bóng vừa thổi còi.
2. Checklist 9 mục lấy thẳng từ CLAUDE.md (không tự nghĩ thêm tiêu chí ngoài luật đã có): không nối chuỗi SQL thủ công, cache state theo user, không biến global chứa dữ liệu nghiệp vụ, không bare `except`, bcrypt cho mật khẩu, tách lớp 3 tầng, dùng Loguru thay `print()`, không secret lọt git, docstring cho function/class public.
3. Chạy review trên toàn bộ `src/` hiện có (không chỉ code mới của bước 3.2) — vì đây là lần đầu checklist tồn tại, cần bao phủ ngược lại những gì đã viết ở Tuần 2 và bước 3.1.
4. Với phát hiện Fail: tự (Claude Code, không qua agent review vì agent đó không có quyền sửa) xác nhận lại là vi phạm thật trước khi sửa, phân loại lỗi kỹ thuật thuần tuý (tự sửa) hay cần quyết định nghiệp vụ (dừng lại hỏi COO).
5. Tự chạy lại độc lập 3 mục quan trọng nhất (SQL injection, cache theo user, secret lọt git) bằng grep trực tiếp — không chỉ tin báo cáo của agent review, đúng nguyên tắc "ai review cũng cần được xác minh chéo".

## Kết quả thu được

Commit `55c7927` (tạo `qa-reviewer-agent.md`, 26 dòng), `18d7e92` (sửa lỗi phát hiện được).

Kết quả 9 mục (chạy trên toàn bộ `src/` — bao gồm cả code từ bước 2.2, 2.4, 3.1):

| # | Hạng mục | Kết quả |
|---|---|---|
| 1 | Không nối chuỗi SQL thủ công | PASS |
| 2 | Cache state theo user | PASS |
| 3 | Không biến global chứa dữ liệu nghiệp vụ | PASS |
| 4 | Không bare `except:` | PASS |
| 5 | Mật khẩu bcrypt, không log/lưu plaintext | PASS |
| 6 | Tách lớp đúng CLAUDE.md mục 2 | PASS |
| 7 | Dùng Loguru, không `print()` | PASS |
| 8 | Không secret thật lọt code/git | PASS |
| 9 | Docstring cho function/class public | **FAIL** — `main()` ở `src/app/main.py:106` thiếu docstring |

Lỗi duy nhất (mục 9) là kỹ thuật thuần tuý, không cần quyết định nghiệp vụ — đã sửa ngay (thêm docstring cho `main()`), xác nhận qua `git show` sau khi commit.

**Lưu ý phụ (không phải Fail, không chặn merge):** `src/auth/authentication.py:53` có `_DEV_FALLBACK_COOKIE_KEY` hardcoded khi thiếu biến môi trường `AUTH_COOKIE_KEY` — agent khuyến nghị nên raise lỗi thay vì fallback êm khi triển khai thật, đã có comment "CHỈ dùng cho dev/demo cục bộ" sẵn trong code (không phải secret thật bị lộ). Ghi nhận làm việc cần làm trước khi có môi trường production thật (chưa tới trong 8 tuần Giai đoạn 1), không tự ý mở rộng phạm vi bước 3.2 để xử lý ngay.

Tự xác minh độc lập (không chỉ tin báo cáo agent):
- Mục 1: grep `execute(f"..."`, `text(f"..."` toàn `src/` → 0 kết quả.
- Mục 2: grep `st.cache_data`/`st.cache_resource` → đúng 1 decorator thật, chữ ký `_cached_data_scope(user_id: int, role_value: str)` — có tham số như yêu cầu.
- Mục 8: `git ls-files | grep .env` → rỗng; grep secret có giá trị thật trong file đã commit → rỗng.

## Bài học rút ra

- **Tách quyền "review" khỏi quyền "sửa" ở cấp subagent** (chỉ cấp Read/Grep/Glob/Bash, không cấp Write/Edit) là cách chắc chắn nhất để đảm bảo checklist được tuân thủ đúng tinh thần "chốt chặn cuối" — nếu agent review có thể tự sửa, sẽ khó phân biệt "đã kiểm tra kỹ" với "đã tự vá cho qua".
- **Chạy checklist mới lần đầu tiên nên quét toàn bộ code cũ, không chỉ code mới** — nếu chỉ áp dụng từ nay về sau, những vi phạm nhỏ đã lọt qua ở Tuần 2 (may mắn là không có) sẽ không bao giờ bị phát hiện.
- **Ngay cả agent chuyên trách review cũng cần được xác minh chéo** — tiếp tục nguyên tắc "xác minh trước khi tin" áp dụng cho chính công cụ kiểm tra, không phải chỉ cho code được kiểm tra.
- **Phân biệt "Fail của checklist" và "khuyến nghị cải thiện thêm"** giúp không bị cuốn vào sửa lan man ngoài phạm vi đã định — lưu ý về `_DEV_FALLBACK_COOKIE_KEY` là ví dụ hợp lý để ghi nhận mà không xử lý ngay.

## Kết quả

`qa-reviewer-agent` đã hoạt động và đã dùng thật để quét toàn bộ code Tuần 2 + bước 3.1 — 8/9 mục Pass ngay từ lần đầu, 1 Fail (thiếu docstring) đã sửa. Checklist này áp dụng bắt buộc từ nay về sau trước mọi lần merge, đúng theo CLAUDE.md mục 6.
