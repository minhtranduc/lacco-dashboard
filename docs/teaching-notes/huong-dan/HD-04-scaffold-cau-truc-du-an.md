# HD-04: Scaffold cấu trúc dự án theo kiến trúc 3 lớp

**Tuần:** 1 — Nền tảng & chốt yêu cầu | **Đối tượng phù hợp:** Cả hai (Lãnh đạo & IT/BA) | **Ngày thực hiện:** 13/08/2026

## Mục tiêu

Tạo "khung xương" thư mục chuẩn cho dự án `lacco-dashboard` theo kiến trúc 3 lớp (3-layer architecture — mô hình tách code thành 3 tầng riêng biệt: Application/giao diện, Service/nghiệp vụ, Data/dữ liệu), làm nền tảng để các bước code sau này (Tuần 2 trở đi) có chỗ để đặt vào đúng vị trí — mà không phải đợi chốt xong 100% yêu cầu nghiệp vụ, và không đụng tới các tài liệu/config đã có sẵn.

## Yêu cầu đã đặt ra cho Claude Code CLI

Prompt scaffold được ra ràng buộc rõ ràng để tránh AI "tự ý sáng tạo" ngoài phạm vi:

1. Tạo cấu trúc thư mục theo kiến trúc 3 lớp — không viết logic nghiệp vụ, chỉ tạo khung.
2. Không đụng vào `docs/teaching-notes/` — kể cả 2 file đang untracked sẵn có (HD-02, HD-03).
3. Không sửa `README.md`, `.gitignore` gốc của repo.
4. Không tạo mới hoặc sửa `CLAUDE.md`.
5. Commit riêng, chỉ gồm đúng các file scaffold — không gộp lẫn với thay đổi khác.

## Kết quả thu được

Claude Code CLI đã scaffold đúng **10 file**, commit thành công (`2797514`), message: `chore: scaffold project structure theo kien truc 3 lop`.

| Nhóm | File/Thư mục đã tạo | Vai trò |
|---|---|---|
| Tài liệu | `docs/requirements/README.md`, `docs/architecture/README.md` | Mô tả ngắn nội dung sẽ đặt ở từng khu vực tài liệu |
| Tầng ứng dụng (Application layer) | `src/app/__init__.py` | Nơi đặt giao diện/dashboard, điểm vào của người dùng |
| Tầng nghiệp vụ (Service layer) | `src/services/__init__.py` | Nơi đặt logic tính toán, xử lý nghiệp vụ (doanh thu, công nợ, v.v.) |
| Tầng dữ liệu (Data layer) | `src/db/__init__.py` | Nơi đặt kết nối & truy vấn database |
| Xác thực & phân quyền | `src/auth/__init__.py` | Nơi đặt logic đăng nhập, RBAC (Role-Based Access Control — phân quyền theo vai trò) |
| Thư mục trống giữ chỗ | `data/sample/.gitkeep`, `tests/.gitkeep`, `.claude/agents/.gitkeep`, `scripts/.gitkeep` | Đánh dấu thư mục sẽ dùng ở bước sau (dữ liệu mẫu, kiểm thử, agent AI, script tiện ích) — Git mặc định không lưu thư mục rỗng nên cần file `.gitkeep` để giữ chỗ |

**Không đụng đến** (đúng như yêu cầu): `docs/teaching-notes/` (2 file HD-02, HD-03 vẫn untracked như cũ), `README.md` và `.gitignore` gốc, không có `CLAUDE.md` nào được tạo/sửa.

## Giải thích: Tại sao cần Scaffold dự án trước, dù chưa chốt xong yêu cầu nghiệp vụ?

**1. Tách "khung" ra khỏi "nội dung" — hai việc độc lập nhau.** Scaffold chỉ tạo thư mục và file rỗng đánh dấu vai trò từng tầng, hoàn toàn không đụng đến logic nghiệp vụ (doanh thu tính sao, công nợ cảnh báo ở ngưỡng nào...). Vì vậy làm được ngay cả khi mới thu thập được 5/14 yêu cầu (như HD-03 đã ghi nhận) — đúng tinh thần "không cần đợi phỏng vấn xong 100% mới bắt đầu code".

**2. Kiến trúc 3 lớp giúp mọi thay đổi sau này có chỗ để vào, tránh code lộn xộn.** Nếu không có khung từ đầu, càng về sau càng dễ xảy ra tình trạng logic nghiệp vụ, truy vấn database và giao diện trộn lẫn vào cùng một file — khó bảo trì, khó phân công cho người khác (kể cả AI agent) làm tiếp mà không giẫm chân nhau. Tách riêng `src/app`, `src/services`, `src/db`, `src/auth` ngay từ đầu nghĩa là:
   - Đổi giao diện dashboard không ảnh hưởng logic tính doanh thu.
   - Đổi công thức tính công nợ không phải sửa code kết nối database.
   - Thêm phân quyền RBAC (ưu tiên ở Tuần 3, theo tiêu chí khách hàng A/B/C đang chờ phỏng vấn) có sẵn một thư mục `src/auth` riêng để làm, không phải chèn ngang vào chỗ khác.

**3. Định hướng rõ cho AI agent (Claude Code) ở các bước sau.** Mỗi thư mục có `__init__.py` kèm 1 dòng comment mô tả vai trò — nghĩa là từ bước tiếp theo trở đi, khi ra prompt cho Claude Code (ví dụ "viết hàm tính doanh thu theo dịch vụ"), AI đã biết ngay phải đặt code vào `src/services/`, không cần giải thích lại cấu trúc dự án mỗi lần. Giảm rủi ro AI đặt sai chỗ hoặc tạo cấu trúc tuỳ tiện mỗi lần được giao việc mới.

**4. Tách bạch code dự án và tài liệu học tập.** Việc cố tình không đụng `docs/teaching-notes/`, `README.md`, `.gitignore` gốc đảm bảo 2 mạch song song không giẫm lên nhau: một bên là code thực của dashboard, một bên là nhật ký học Claude Code (các file HD-0x này) — để sau này nhìn lại lịch sử commit vẫn phân biệt rõ đâu là thay đổi code, đâu là ghi chép quá trình.

## Bài học rút ra

- Ra ràng buộc rõ ràng trong prompt (danh sách "không được đụng vào") hiệu quả hơn nhiều so với yêu cầu chung chung — Claude Code tuân thủ chính xác cả 10/10 file, không lấn sang phạm vi khác.
- Dùng `.gitkeep` là quy ước chuẩn của Git để giữ chỗ cho thư mục rỗng (Git không tự lưu thư mục không có file bên trong).
- Scaffold sớm không có nghĩa là "làm ẩu cho xong" — vẫn cần tư duy trước cấu trúc (3 lớp) phù hợp với hướng phát triển đã định (ví dụ chừa sẵn `src/auth` vì biết Tuần 3 sẽ cần RBAC), tránh phải đảo lại cấu trúc giữa chừng.
- Yêu cầu commit riêng, chỉ chứa đúng phạm vi thay đổi (10 file scaffold, không gộp việc khác) giúp lịch sử Git dễ theo dõi — mỗi commit ứng với đúng 1 bước trong kế hoạch.

## Kết quả

Khung dự án 3 lớp đã sẵn sàng, commit `2797514` thành công, không ảnh hưởng tài liệu/config sẵn có. Sẵn sàng cho các bước tiếp theo của Tuần 1 (hoàn tất đợt phỏng vấn Kế toán – Tài chính, 9/14 dòng yêu cầu còn "Cần làm rõ") trước khi bước sang thiết kế database schema chi tiết ở Tuần 2.
