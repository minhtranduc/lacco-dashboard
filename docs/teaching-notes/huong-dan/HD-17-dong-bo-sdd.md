# HD-17: Đồng bộ tài liệu kiến trúc (SDD) theo code thực tế

**Tuần:** 5 — Module báo cáo đợt 2 | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 09/09/2026

## Mục tiêu

Sau khi 6/6 module báo cáo đã hoạt động thật (bước 4.1→5.1), tài liệu kiến trúc gốc của dự án (2 file `.docx` viết trước khi redesign ERD ở bước 2.1) đã lỗi thời nghiêm trọng — không phản ánh schema, RBAC, hay danh sách module thực tế. Bước 5.2 tạo và đưa vào vận hành **SDD sống** (`docs/architecture/SDD.md`) — tài liệu kiến trúc cập nhật dần theo code thật, thay vì đóng băng tại 1 thời điểm — cùng lúc sửa `README.md` và hình thành persona `doc-writer-agent` cho việc đồng bộ này ở các lần sau.

## Giải thích khái niệm: SDD "sống" khác gì tài liệu quyết định lịch sử

Dự án đã có `docs/architecture/erd-tuan-02.md` — đây là **biên bản quyết định** (decision record): ghi lại chính xác quyết định ERD tại bước 2.1, kèm ngày và lý do, và **không nên sửa lại** vì giá trị của nó chính là "quyết định lúc đó là gì". SDD (System Design Document) đóng vai trò khác: là bức tranh **hiện trạng** hệ thống tại thời điểm đọc, phải luôn cập nhật theo code thật (CLAUDE.md mục 2 xếp `docs/architecture/` là nơi chứa "SDD, cập nhật dần"). Vì vậy SDD.md không lặp lại nội dung erd-tuan-02.md mà tóm tắt + dẫn chiếu — 2 tài liệu bổ sung cho nhau: 1 trả lời "hệ thống hiện tại trông như thế nào", 1 trả lời "vì sao nó được thiết kế như vậy tại 1 mốc cụ thể".

## Cách tiếp cận / Quy trình đã dùng

1. Xác định đúng phạm vi qua tracker (bước 5.2, mã HD-17, tool "Cowork (doc-writer-agent)") — khác các bước 3.x-5.1 vốn giao cho Claude Code CLI thật (cần MySQL/pytest thật), bước này thuần đọc code + viết tài liệu nên thực hiện trực tiếp trong phiên Cowork (đọc code qua cầu nối thiết bị), không cần môi trường CLI đầy đủ.
2. Đọc trực tiếp toàn bộ nguồn sự thật trước khi viết 1 dòng nào: `src/db/models/*.py` (18 bảng), `src/auth/scope.py` (RBAC), `requirements.txt` (tech stack), `.github/workflows/ci.yml` (CI thật chạy gì — phát hiện coverage hiện chỉ đo `src/auth`, không phải toàn bộ `src/services/`), toàn bộ 6 cặp service+trang báo cáo.
3. Viết `docs/architecture/SDD.md` theo cấu trúc: tổng quan, kiến trúc 3 lớp, tech stack, ERD tóm tắt (dẫn chiếu erd-tuan-02.md), RBAC 3 cấp, bảng 6 module, danh sách quyết định nghiệp vụ đã chốt (có ngày), danh sách vấn đề còn mở, testing/CI, liên kết tài liệu.
4. Trong lúc kiểm tra `README.md` để mở rộng nội dung, phát hiện file bị lỗi encoding (xem bảng lỗi bên dưới) — xử lý luôn trong cùng bước vì cùng thuộc phạm vi "tài liệu gốc repo".
5. Soạn persona `doc-writer-agent` (qua CLI, vì `.claude/` bị chặn ghi qua device bridge) — hình thức hoá vai trò "đồng bộ tài liệu" thành 1 subagent tái sử dụng được cho các lần cập nhật SDD sau này (tương tự cách `report-builder-agent` được hình thành sau khi làm 2 module đầu ở bước 4.1).

### Lỗi thật gặp phải

| # | Lỗi | Nguyên nhân | Cách phát hiện | Cách xử lý |
|---|---|---|---|---|
| 1 | `README.md` hiển thị toàn ký tự lỗi (mojibake) khi đọc bằng công cụ mặc định (UTF-8) | File được ghi bằng `UTF-16 LE` (dấu hiệu: có BOM `\xff\xfe` + byte `\x00` xen giữa mỗi ký tự) — khả năng cao do lệnh redirect PowerShell (`>`) mặc định dùng UTF-16 khi khởi tạo repo ngày 27/07/2026, không phải lỗi nội dung | Chạy `file README.md` xác nhận "UTF-16, little-endian" trước khi kết luận, thay vì đoán "nội dung bị hỏng"; decode bằng `utf-16` để đọc được nội dung gốc (chỉ 3 dòng, không hề mất dữ liệu) | Đọc lại đúng bằng `utf-16`, viết lại tường minh bằng `utf-8`, mở rộng thêm nội dung còn thiếu (tổng quan, cài đặt, liên kết tài liệu) |

## Kết quả thu được

Commit `a5a1131e` (3 file, +173 dòng): `docs/architecture/SDD.md` (mới, 143 dòng), `README.md` (sửa encoding UTF-16→UTF-8 + mở rộng nội dung, 292→2392 byte), `.claude/agents/doc-writer-agent.md` (persona mới, 30 dòng). CI xanh — xác minh độc lập qua GitHub REST API, run [`34369331983`](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34369331983), `conclusion: success`.

SDD.md tổng hợp: 18 bảng ERD (3 nhóm), RBAC 3 cấp + 4 mẫu RBAC mới từ bước 5.1 (lọc theo nhân viên, ẩn hẳn UI theo role, chặn hoàn toàn khi không lọc được theo scope), bảng 6 module báo cáo, 9 quyết định nghiệp vụ đã chốt (có ngày), 10 vấn đề/giả định kỹ thuật còn mở (tổng hợp từ `erd-tuan-02.md` + phát sinh bước 5.1), và phát hiện khoảng trống test: CI hiện chỉ đo coverage cho `src/auth`, toàn bộ `src/services/report_*.py` (6 module) chưa có test tự động — ghi nhận là rủi ro hồi quy thật, chưa xử lý.

## Bài học rút ra

- **Tài liệu kiến trúc cần phân biệt rõ 2 loại: "biên bản quyết định" (đóng băng theo thời gian) và "SDD sống" (luôn cập nhật)** — gộp chung 2 vai trò vào 1 file khiến người đọc không biết đoạn nào còn đúng, đoạn nào chỉ là lịch sử. Giữ `erd-tuan-02.md` nguyên vẹn và tạo `SDD.md` riêng tránh được nhầm lẫn này.
- **"Đồng bộ tài liệu theo code" là công việc thuần đọc-viết, không cần môi trường CLI đầy đủ (MySQL/pytest thật)** — khác các bước xây module trước đó, thực hiện trực tiếp trong phiên Cowork qua cầu nối thiết bị là đủ, không cần giao việc cho Claude Code CLI của người dùng.
- **Luôn kiểm tra encoding thật của file text trước khi kết luận nó "sai"/"hỏng"** — 1 file hiển thị toàn ký tự lỗi không có nghĩa nội dung bị mất, chỉ cần xác định đúng encoding (`file <tên file>` hoặc đọc byte đầu) trước khi xử lý; nếu vội viết đè bằng encoding mặc định mà không đọc lại nội dung gốc trước, sẽ mất thật nội dung cũ.
- **Hình thành persona SAU khi đã tự làm công việc đó ít nhất 1 lần** (không phải trước) — cách này đảm bảo persona phản ánh đúng nguyên tắc đã kiểm chứng thực tế (VD: cảnh báo về sự cố encoding README) thay vì suy đoán trước những vấn đề chưa từng gặp.

## Kết quả

Bước 5.2 hoàn thành: `docs/architecture/SDD.md` trở thành nguồn tham chiếu kiến trúc hiện tại của dự án, `README.md` đọc được đúng và đầy đủ hơn, persona `doc-writer-agent` sẵn sàng tái sử dụng cho các lần đồng bộ tài liệu sau (dự kiến cuối mỗi giai đoạn lớn, hoặc khi thêm module/đổi RBAC đáng kể).
