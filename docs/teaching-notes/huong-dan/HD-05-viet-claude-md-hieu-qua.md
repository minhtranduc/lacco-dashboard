# HD-05: Cách viết CLAUDE.md hiệu quả — checklist 6 mục

**Tuần:** 1 — Nền tảng & chốt yêu cầu | **Đối tượng phù hợp:** Cả hai (Lãnh đạo & IT/BA) | **Ngày thực hiện:** 13/08/2026

## Mục tiêu

Viết được `CLAUDE.md` v1 — file context Claude Code tự đọc ở đầu mỗi phiên làm việc — đủ rõ để AI hiểu bối cảnh nghiệp vụ, tech stack, quy ước code và quy tắc RBAC mà không cần giải thích lại từ đầu mỗi lần mở phiên mới.

## Checklist 6 mục cốt lõi

Đúc kết từ nội dung thực tế đã đưa vào `CLAUDE.md` v1 (dựa trên khung gợi ý ở mục 2.2, Kế hoạch triển khai):

| # | Mục | Vì sao cần |
|---|---|---|
| 1 | Bối cảnh nghiệp vụ & phạm vi dự án | AI cần biết công ty làm gì, dự án phục vụ ai, và quan trọng không kém: **phạm vi KHÔNG bao gồm gì** (ví dụ: không có Báo cáo Marketing ở Giai đoạn 1) — tránh AI tự ý mở rộng phạm vi |
| 2 | Kiến trúc & cấu trúc thư mục | AI biết đặt code mới vào đúng lớp (`src/app`, `src/services`, `src/db`, `src/auth`) mà không cần hỏi lại mỗi lần |
| 3 | Tech stack (lõi + bổ sung theo từng tuần) | Tránh AI tự chọn thư viện khác "cho tiện" — ví dụ không tự đổi Streamlit sang Dash dù về lý thuyết an toàn hơn cho multi-user |
| 4 | Quy ước code & lệnh thường dùng | PEP8, docstring, parameterized query bắt buộc — để mọi đoạn code AI sinh ra nhất quán như thể một người viết |
| 5 | RBAC & bảo mật — rủi ro cụ thể của dự án | Không chỉ ghi "phải bảo mật" chung chung, mà ghi đúng rủi ro đã biết trước (Streamlit chia sẻ cache giữa các phiên user) thành quy tắc thực thi được |
| 6 | Trạng thái yêu cầu nghiệp vụ (đã rõ / chưa rõ) | Ranh giới rõ ràng: phần nào AI được code logic thật, phần nào chỉ dựng khung — tránh AI đoán mò công thức khi dữ liệu phỏng vấn chưa đủ |

## Cách tiếp cận đã dùng

1. Tổng hợp nội dung từ 3 nguồn có sẵn thay vì hỏi lại thông tin đã biết: Tài liệu Kiến trúc Hệ thống (tech stack, kiến trúc, luồng dữ liệu), Kế hoạch triển khai Dashboard LACCO (checklist gốc mục 2.2, bảng công cụ bổ sung theo tuần, bảng rủi ro mục 7), Sheet 1 "Mẫu thu thập yêu cầu" (trạng thái Đã rõ/Cần làm rõ của 14 dòng yêu cầu báo cáo).
2. Đánh dấu tường minh phần "đã chốt" (✅ Đã rõ) và "chưa chốt" (⛔ Cần làm rõ) ngay trong CLAUDE.md bằng bảng trạng thái, thay vì chỉ liệt kê chung chung.
3. Đưa rủi ro bảo mật cụ thể của dự án (Streamlit cache chia sẻ state giữa các phiên người dùng, có thể lộ dữ liệu tài chính giữa các user) thành quy tắc bắt buộc, thay vì nguyên tắc bảo mật chung chung.
4. Ghi số phiên bản (v1) và ngày ngay đầu file, để lần cập nhật sau (v2, sau khi phỏng vấn Kế toán – Tài chính xong) có mốc so sánh.
5. Nhờ chính Claude Code CLI đọc và xác nhận CLAUDE.md khớp với cấu trúc thư mục thực tế trước khi commit — dùng AI để kiểm tra chéo nội dung mà chính nó sẽ dùng làm "luật chơi".

## Kết quả thu được

- `CLAUDE.md` v1 hoàn chỉnh, đặt tại gốc repo, gồm 9 phần (bối cảnh, kiến trúc, tech stack, quy ước code, lệnh thường dùng, RBAC & bảo mật, bảng trạng thái 14 dòng yêu cầu, việc tồn đọng, lịch sử phiên bản).
- Claude Code CLI tự đọc và xác nhận: cây thư mục mô tả trong file khớp 100% với thực tế (`docs/requirements`, `docs/architecture`, `docs/teaching-notes`, `src/app`, `src/services`, `src/db`, `src/auth`, `data/sample`, `tests`, `.claude/agents`, `scripts`), kể cả commit hash `2797514` trích dẫn đúng — không cần sửa gì trước khi commit.
- Commit `e0e0f69`, chỉ gồm đúng 1 file `CLAUDE.md`, không đụng 2 file HD đang untracked trong `docs/teaching-notes/huong-dan/`.

## Bài học rút ra

- `CLAUDE.md` không cần viết từ đầu — tận dụng nội dung đã có sẵn trong các tài liệu kế hoạch/kiến trúc trước đó, chỉ cần tổng hợp và cấu trúc lại cho đúng mục đích (AI đọc máy, không phải người đọc trình bày đẹp).
- Ghi rõ ràng "đã chốt / chưa chốt" ngay trong file context quan trọng hơn ghi đầy đủ mọi thứ cho có — giúp AI biết dừng đúng chỗ thay vì tự suy đoán công thức nghiệp vụ khi thiếu dữ liệu phỏng vấn.
- Đưa rủi ro kỹ thuật cụ thể (không phải nguyên tắc chung chung) vào CLAUDE.md biến nó thành rào chắn thực thi được — quy tắc "mọi `cache_data` phải gắn `user_id`/`role`" cụ thể và kiểm tra được, khác hẳn câu "phải bảo mật dữ liệu".
- Nhờ Claude Code tự review file trước khi commit (thay vì tự ý commit ngay) là bước kiểm tra chéo rẻ nhưng hiệu quả — nếu có mâu thuẫn giữa CLAUDE.md và cấu trúc thực tế, lỗi bị bắt trước khi trở thành thói quen sai xuyên suốt cả dự án.
- Giữ phạm vi commit hẹp (chỉ đúng 1 file thay đổi) tiếp tục được duy trì nhất quán từ bước 1.4 — thói quen tốt cho việc audit lịch sử Git sau này.

## Kết quả

`CLAUDE.md` v1 đã commit thành công (`e0e0f69`), sẵn sàng làm context cho mọi phiên Claude Code từ Tuần 2 trở đi. Cần cập nhật lên v2 sau khi hoàn tất phỏng vấn Kế toán – Tài chính (9/14 dòng yêu cầu còn "Cần làm rõ"), trước khi thiết kế schema chi tiết.
