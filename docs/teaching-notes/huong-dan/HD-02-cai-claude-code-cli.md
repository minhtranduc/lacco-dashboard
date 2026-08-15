# HD-02: Cài đặt & cấu hình Claude Code CLI lần đầu

**Tuần:** 1 — Nền tảng & chốt yêu cầu | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 03/08/2026

## Mục tiêu

Cài Claude Code CLI trên máy Windows, xác thực bằng tài khoản Claude Pro/Max, và mở được phiên làm việc đầu tiên ngay trong thư mục repo `lacco-dashboard`.

## Các bước đã thực hiện

1. Cài bằng native installer qua PowerShell (không cần Node.js — khác với cách cài cũ dùng npm).
2. Đóng và mở lại PowerShell để nhận PATH mới.
3. Kiểm tra cài đặt bằng `claude --version` và `claude doctor`.
4. `cd` vào đúng thư mục repo, chạy `claude` để đăng nhập lần đầu qua trình duyệt bằng tài khoản Pro/Max.
5. Xác nhận "Trust this folder" khi được hỏi — vì đây là thư mục dự án đáng tin cậy.

## Lệnh đã dùng

```powershell
irm https://claude.ai/install.ps1 | iex

# (đóng và mở lại PowerShell)

claude --version
claude doctor

cd "D:\Minh\AI\Projects\Lacco Dashboard\lacco-dashboard"
claude
```

## Kết quả thu được

```
claude --version  →  2.1.220 (Claude Code)
claude doctor     →  "No installation issues found."
```

Đăng nhập qua trình duyệt thành công, giao diện Claude Code v2.1.220 hiện ra ngay trong thư mục `lacco-dashboard`.

## Bài học rút ra

- Cách cài Claude Code đã đơn giản hoá đáng kể so với các phiên bản cũ: installer gốc (native) không còn phụ thuộc Node.js, giảm 1 lớp cài đặt trung gian — ít điểm có thể lỗi hơn.
- Luôn chạy `claude` lần đầu **ngay trong thư mục dự án** (không phải thư mục Home) — vì Claude Code gắn bối cảnh làm việc theo thư mục hiện hành, và bước "Trust this folder" chỉ cần xác nhận 1 lần cho mỗi thư mục.
- `claude doctor` là lệnh hữu ích để tự chẩn đoán môi trường — nên chạy lại bất cứ khi nào nghi ngờ có lỗi cài đặt, trước khi đi tìm nguyên nhân phức tạp hơn.

## Kết quả

Claude Code CLI đã sẵn sàng, đăng nhập đúng tài khoản, mở đúng ngữ cảnh repo `lacco-dashboard`. Sẵn sàng cho Bước 1.3 — thu thập yêu cầu nghiệp vụ.
