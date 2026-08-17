# Nhật ký Tuần 1 — Nền tảng & chốt yêu cầu

**Dự án:** Dashboard LACCO — Giai đoạn 1 (WebApp MVP) | **Tuần:** 1/8 | **Người thực hiện:** Minh Tran (COO) | **Ngày viết:** 17/08/2026

> Tài liệu này là nguyên liệu thô cho case study "Claude for Business" — ghi lại đúng những gì đã xảy ra (kể cả lỗi và đường vòng), không phải bản tường thuật lý tưởng hoá.

## 1. Tổng quan

Tuần 1 đặt mục tiêu: dựng nền tảng repo + công cụ (GitHub, Claude Code CLI), chốt yêu cầu nghiệp vụ, scaffold cấu trúc dự án, viết context cho AI (CLAUDE.md), và kết nối MCP tới MySQL. Đây là các điều kiện tiên quyết bắt buộc trước khi Tuần 2 có thể bắt đầu thiết kế schema thật.

**Kết quả:** 7/7 bước hoàn thành. Về mặt lịch, tiến độ thực tế trải dài từ 03/08 đến 17/08/2026 (~2.5 tuần lịch) thay vì gọn trong khung "27/07–02/08" ghi trong lộ trình gốc — đúng với nguyên tắc đã thống nhất từ đầu dự án: *"không cần dồn ép tiến độ, có biên độ dự phòng"* (mục 4, Kế hoạch triển khai). Ghi nhận trung thực điều này vì đây là dữ liệu thật cho case study, không nên làm đẹp lại thành "đúng 1 tuần".

## 2. Đối chiếu tiêu chí nghiệm thu

Tiêu chí ở mục 8 Kế hoạch triển khai ("Tiêu chí nghiệm thu MVP Giai đoạn 1") là **tiêu chí cuối Giai đoạn 1 (8 tuần)**, không phải checkpoint hàng tuần — ví dụ "RBAC 3 cấp hoạt động đúng", "chịu tải 20 người dùng", "xuất được Excel/PDF" đều là kết quả cần có hệ thống thật mới đo được, chưa áp dụng ở Tuần 1. Tuần 1 chỉ có trách nhiệm đặt đúng nền móng để các tiêu chí đó khả thi sau này:

| Tiêu chí Giai đoạn 1 (mục 8) | Nền móng Tuần 1 đã đặt |
|---|---|
| 6 nhóm báo cáo hoạt động | 12/14 yêu cầu báo cáo đã "Đã rõ" (bước 1.3) — đủ dữ liệu để thiết kế ERD Tuần 2 |
| RBAC 3 cấp theo A/B/C, Khối/Phòng | Tiêu chí phân loại KH A/B/C đã chốt (cột "Phân loại" có sẵn trong FT) — ghi vào CLAUDE.md mục 6 |
| Audit log, login history | Đã có trong ERD dự kiến bước 2.1 (bảng `users`, `loginhistory` — dù cần dựng lại mới, xem mục 5) |
| Bộ tài liệu case study | HD-01 → HD-06 đã hoàn thành, nhật ký Tuần 1 (file này) là nhật ký đầu tiên |

## 3. Chi tiết 7 bước Tuần 1

| Bước | Tên | Trạng thái | Ngày hoàn thành thực tế | Mã HD |
|---|---|---|---|---|
| 1.1 | Tạo GitHub repo | Hoàn thành | 03/08/2026 | HD-01 |
| 1.2 | Cài Claude Code CLI | Hoàn thành | 03/08/2026 | HD-02 |
| 1.3 | Thu thập yêu cầu nghiệp vụ | Hoàn thành | 17/08/2026 | HD-03 |
| 1.4 | Scaffold cấu trúc dự án | Hoàn thành | 13/08/2026 | HD-04 |
| 1.5 | Viết CLAUDE.md v1 (→ v2) | Hoàn thành | 13/08/2026 (v2: 17/08) | HD-05 |
| 1.6 | Cấu hình MCP–MySQL | Hoàn thành | 17/08/2026 | HD-06 |
| 1.7 | Review & nhật ký Tuần 1 | Hoàn thành | 17/08/2026 | (file này) |

## 4. Quyết định kiến trúc & lý do

- **Kiến trúc 3 lớp** (Presentation/Business Logic/Data, `src/app` · `src/services` · `src/db`) — giữ nguyên như Tài liệu Kiến trúc Hệ thống gốc, để đổi giao diện không ảnh hưởng logic nghiệp vụ.
- **CLAUDE.md tách thành 2 file** (`CLAUDE.md` + `.claude/rules/trang-thai-yeu-cau.md`) — vì bảng trạng thái 14 dòng yêu cầu thay đổi thường xuyên (5/14 → 12/14 trong 1 tuần), không nên nằm trong file "luật chơi" chính; dùng cơ chế path-scoped rules để tiết kiệm ngữ cảnh khi Claude làm việc ngoài `src/services/`, `src/db/`.
- **CRM và Dòng tiền dời sang Giai đoạn 2** — quyết định nghiệp vụ (COO xác nhận), không phải do AI tự suy đoán: CRM chưa có dữ liệu trên hệ thống, Dòng tiền chưa xác nhận được nguồn AMIS chính xác.
- **9 bảng thử nghiệm cũ trong database "lacco" sẽ bị xoá, tạo lại từ đầu ở bước 2.1** — quyết định của COO để đảm bảo schema mới bám sát đúng ERD thiết kế theo yêu cầu đã "Đã rõ", tránh kế thừa cấu trúc thử nghiệm không rõ nguồn gốc.
- **MCP server MySQL đăng ký ở scope Local** (không lên Git) — vì hiện chỉ một mình COO code, không có nhu cầu chia sẻ cấu hình kết nối DB qua repo dùng chung.

## 5. Vấn đề gặp phải & cách Claude hỗ trợ giải quyết

| Vấn đề | Cách xử lý |
|---|---|
| Prompt cập nhật `.claude/rules/` chứa placeholder chưa điền, Claude Code CLI đúng đắn từ chối chạy | Nhận diện lỗi, xin lỗi, đưa lại prompt đầy đủ nội dung thay vì tham chiếu "nội dung ở tin nhắn trước" (CLI không có ngữ cảnh đó) |
| Claim "chỉ còn dòng 18 (Dòng tiền) chưa xong" không khớp thực tế file (dòng 8, 9, 10 cũng chưa xong) | Không cập nhật tracker theo lời khai — đối chiếu trực tiếp file Excel, hỏi lại người dùng, chỉ cập nhật sau khi xác minh khớp với file thật |
| Cấu hình MCP–MySQL gặp liên tiếp 6 lỗi (sai thư mục scope, sai tên biến môi trường, sai vị trí cờ `-e`, cần restart CLI, MySQL service chưa chạy, mật khẩu để trống) | Xử lý từng lỗi bằng cách xác minh trực tiếp (đọc README gốc của gói thay vì đoán, kiểm tra service bằng PowerShell, test kết nối độc lập bằng `mysql.exe` trước khi sửa lại MCP) — toàn bộ hành trình ghi tại HD-06 |
| Claude Code CLI từ chối nhận mật khẩu MySQL qua kênh hỏi-đáp thông thường | Tôn trọng hành vi bảo mật này — hướng dẫn người dùng tự chạy lệnh trực tiếp bằng tiền tố `!`, không tìm cách "lách" |
| File Excel bị khoá do đang mở trong Excel trên máy người dùng | Kiểm tra file `~$*.xlsx` trước mỗi lần ghi, yêu cầu đóng file khi phát hiện khoá, xác minh mtime không đổi trước khi ghi lại |

## 6. Prompt tiêu biểu đã dùng trong tuần

- **Scaffold cấu trúc dự án:** yêu cầu Claude Code tạo đúng cây thư mục theo kiến trúc 3 lớp đã thiết kế sẵn, không tự ý thêm/bớt thư mục ngoài kế hoạch.
- **Viết CLAUDE.md:** tổng hợp từ 3 nguồn có sẵn (Tài liệu Kiến trúc, Kế hoạch triển khai, Sheet yêu cầu) thay vì hỏi lại thông tin đã biết; sau đó nhờ chính Claude Code tự đọc và đối chiếu CLAUDE.md với cấu trúc thư mục thực tế trước khi commit — dùng AI kiểm tra chéo nội dung mà chính nó sẽ dùng làm "luật chơi".
- **Cấu hình MCP:** luôn yêu cầu Claude Code xác minh bằng 1 câu query thật (SELECT) thay vì chỉ tin trạng thái "Connected" — mẫu prompt này nên tái sử dụng cho mọi lần tích hợp MCP mới sau này.

## 7. Ước tính thời gian tiết kiệm so với làm thủ công

*(Ước tính định tính, chưa phải số đo chính xác — dùng tham khảo cho slide báo cáo lãnh đạo, không dùng làm cam kết ROI chính thức.)*

| Việc | Làm thủ công (ước tính) | Với Claude | Ghi chú |
|---|---|---|---|
| Soạn CLAUDE.md v1 (tổng hợp 3 nguồn tài liệu) | ~0.5–1 ngày | ~1–2 giờ | Chủ yếu tiết kiệm công tổng hợp/viết lại |
| Viết 6 tài liệu HD-01→HD-06 | ~2–3 ngày (nếu tự viết song song code) | Gần như đồng thời với lúc code, không tốn thêm buổi riêng | Nhờ nguyên tắc "vừa làm vừa ghi", không tách rời |
| Debug MCP-MySQL (6 lỗi liên tiếp) | Khó ước tính nếu tự tra cứu — nhiều khả năng mất nhiều thời gian hơn vì phải tự đọc README/tài liệu cộng đồng | Có AI cùng chẩn đoán từng lỗi theo triệu chứng cụ thể | Tự bản thân Claude cũng đưa sai thông tin 1 lần (tên biến môi trường) — không phải tuyệt đối, cần luôn xác minh |

## 8. Bài học rút ra cho Tuần 2

- Luôn xác minh bằng hành động thật (query, đọc file, chạy lệnh) thay vì tin theo trạng thái/lời khai — áp dụng cho cả dữ liệu do người dùng báo lẫn thông tin do chính Claude tra cứu.
- Ngày hoàn thành thực tế lệch khá xa so với lịch dự kiến ban đầu (2.5 tuần thay vì 1 tuần) — Tuần 2 nên tiếp tục cho phép biên độ tương tự, không siết deadline cứng.
- Bảng trạng thái yêu cầu và CLAUDE.md cần đồng bộ ngay khi có thay đổi — độ trễ giữa "biết thông tin mới" và "cập nhật vào file context" càng ngắn càng tránh AI dùng thông tin cũ khi code.

## 9. Việc cần làm tiếp (Tuần 2)

- Bước 2.1: Thiết kế ERD & giao db-schema-agent — **nhớ DROP 9 bảng thử nghiệm cũ trước khi tạo bảng mới** (đã ghi trong tracker).
- Tạo user MySQL riêng chỉ quyền `SELECT` thay cho `root`, trước khi vào Tuần 3 (RBAC thật).
- Cân nhắc tạo `docs/teaching-notes/prompt-library.md` (đề xuất trong Kế hoạch triển khai mục 6) để lưu các prompt hiệu quả nhất — chưa thực hiện trong Tuần 1, có thể bắt đầu từ Tuần 2 nếu muốn.
