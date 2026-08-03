# HD-01: Tạo & cấu hình GitHub repo cho dự án AI-assisted

**Tuần:** 1 — Nền tảng & chốt yêu cầu | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 03/08/2026

## Mục tiêu

Có 1 GitHub repo riêng tư (private) tên `lacco-dashboard`, đã clone về máy, xác thực Git hoạt động (push được), sẵn sàng để cài Claude Code CLI ở bước tiếp theo.

## Các bước đã thực hiện

1. Tạo repo `lacco-dashboard` trên GitHub qua giao diện web — chế độ **Private**, kèm README.md và `.gitignore` (template Python), không chọn license (mã nguồn nội bộ công ty).
2. Clone repo về máy qua HTTPS vào đúng thư mục dự án.
3. Cấu hình định danh Git (`user.name`, `user.email`) — chỉ làm 1 lần trên máy.
4. Cài GitHub CLI (`gh`) để xử lý xác thực khi push, thay vì dùng Personal Access Token thủ công.
5. Xác thực qua `gh auth login` (đăng nhập bằng trình duyệt).
6. Thử nghiệm: sửa nhẹ README, `git add` → `git commit` → `git push`, kiểm tra thay đổi hiển thị đúng trên GitHub.

## Lệnh đã dùng

```powershell
cd "D:\Minh\AI\Projects\Lacco Dashboard"
git clone https://github.com/<username>/lacco-dashboard.git
cd lacco-dashboard

git config --global user.name "Minh Tran"
git config --global user.email "trandminh@gmail.com"

winget install --id GitHub.cli
gh auth login

git add README.md
git commit -m "test commit"
git push
```

## Vướng mắc gặp phải & cách xử lý

| Vướng mắc | Nguyên nhân | Cách xử lý |
|---|---|---|
| `gh auth login` báo "term 'gh' is not recognized" | GitHub CLI chưa được cài trên máy Windows (môi trường kiểm tra qua kết nối từ xa trước đó khác với PowerShell thực tế trên máy) | Cài qua `winget install --id GitHub.cli`, sau đó **đóng và mở lại PowerShell** để nhận PATH mới |
| `windget install ...` báo "not recognized" | Gõ nhầm tên lệnh (`windget` thay vì `winget`) | Kiểm tra lại chính tả câu lệnh trước khi kết luận là lỗi hệ thống |

## Bài học rút ra

- Môi trường kiểm tra từ xa (qua kết nối máy tính của trợ lý AI) và môi trường PowerShell thực tế trên máy người dùng **có thể khác nhau** (công cụ có sẵn ở nơi này chưa chắc có ở nơi kia) — luôn xác nhận lại bằng lệnh kiểm tra trực tiếp (`--version`) trước khi giả định.
- Đa số lỗi "command not recognized" ở bước đầu triển khai đến từ 2 nguyên nhân: (1) công cụ chưa cài, hoặc (2) gõ nhầm chính tả — nên kiểm tra nguyên nhân (2) trước vì nhanh hơn.
- Sau khi cài công cụ mới qua `winget`/`gh`, luôn cần mở lại terminal để nhận biến môi trường PATH mới — quên bước này là nguyên nhân phổ biến gây lỗi "not recognized" dù đã cài đúng.

## Kết quả

Repo private `lacco-dashboard` hoạt động đầy đủ: clone/commit/push thành công, sẵn sàng cho Bước 1.2 — Cài đặt Claude Code CLI.
