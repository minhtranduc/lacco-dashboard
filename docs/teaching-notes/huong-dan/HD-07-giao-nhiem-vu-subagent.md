# HD-07: Giao nhiệm vụ thiết kế database cho subagent — thực tế và giới hạn

**Tuần:** 2 — Data layer (schema, migration, import) | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 22/08/2026

## Mục tiêu

Thiết kế ERD (sơ đồ quan hệ thực thể) cho toàn bộ 12 yêu cầu báo cáo đã "Đã rõ", và thực hành kỹ thuật multi-agent orchestration: định nghĩa 1 subagent chuyên biệt (`db-schema-agent`) trong `.claude/agents/`, giao việc review ERD cho subagent đó thay vì tự Claude Code làm hết trong 1 luồng chung.

## Quy trình đã dùng

1. **Thiết kế ERD nháp trước** (không phải Claude Code tự làm từ đầu) — tổng hợp 12/14 yêu cầu "Đã rõ" trong `.claude/rules/trang-thai-yeu-cau.md` thành 18 bảng: 6 bảng danh mục (division, department, employee, service, customer, supplier), 8 bảng nghiệp vụ (sales_order, price_request, supplier_evaluation, cost, budget, personnel_cost, debt, customer_classification_history), 4 bảng bảo mật/audit bắt buộc theo CLAUDE.md mục 6 (users, login_history, audit_log, import_history). Không tạo bảng cho CRM và Dòng tiền (đã chốt dời Giai đoạn 2).
2. **Viết file `.claude/agents/db-schema-agent.md`** — định nghĩa subagent với phạm vi rõ ràng theo từng bước roadmap (2.1 chỉ thiết kế ERD, không viết code; 2.2 mới sinh SQLAlchemy models), kèm nguyên tắc bắt buộc (chỉ code phần "Đã rõ", luôn liệt kê giả định thành mục "cần xác nhận" thay vì tự đoán).
3. **Giao việc review ERD nháp cho subagent** ngay trong cùng phiên Claude Code CLI vừa tạo file subagent.

## Giới hạn thực tế gặp phải — quan trọng cho các bước sau

Claude Code CLI báo: **không gọi trực tiếp được subagent tuỳ biến `db-schema-agent` bằng tên** ("không nằm trong danh sách loại agent khả dụng" của harness) — dù file `.claude/agents/db-schema-agent.md` đã tồn tại đúng định dạng. CLI tự xử lý bằng cách giao việc cho 1 agent loại "general-purpose", nhưng dán kèm toàn bộ nội dung persona/nguyên tắc từ `db-schema-agent.md` vào prompt — kết quả review vẫn tuân đúng các ràng buộc đã định nghĩa, chỉ là không thông qua đúng cơ chế subagent-theo-tên như kế hoạch ban đầu.

**Đã xác minh ở bước 2.2 (22/08/2026, phiên CLI hoàn toàn mới):** không phải do phiên cũ chưa nạp lại — mở phiên mới và gọi trực tiếp `db-schema-agent` theo tên vẫn thất bại, lỗi rõ ràng: `Agent type 'db-schema-agent' not found — Available agents: claude, claude-code-guide, Explore, general-purpose, Plan, statusline-setup`.

**Kết luận chính thức:** harness đang dùng chỉ cho phép gọi 1 danh sách cố định các loại agent tích hợp sẵn qua công cụ Task — **không** hỗ trợ gọi trực tiếp subagent tuỳ biến định nghĩa trong `.claude/agents/*.md` bằng tên, bất kể phiên mới hay cũ. Đây là giới hạn cố định của môi trường đang dùng, không phải lỗi cấu hình hay cần restart.

**Quy ước chính thức từ đây về sau:** mọi lần giao việc cho subagent tuỳ biến (`data-import-agent` ở bước 2.4, `auth-rbac-agent` ở bước 3.1, v.v.) đều dùng cách "general-purpose + dán nguyên văn persona từ file `.claude/agents/*.md` vào prompt" ngay từ đầu — không cần thử gọi theo tên trước rồi mới rơi vào workaround nữa, việc này đã được xác minh chắc chắn, không cần lặp lại thử nghiệm.

## Kết quả review (thực hiện qua workaround nêu trên)

Subagent (dưới dạng workaround) sửa 5 chỗ trong ERD nháp:

- Đổi tên bảng `order` → `sales_order` — vì `ORDER` là từ khoá dành riêng (reserved keyword) trong MySQL 8.0, đặt tên trùng sẽ buộc escape bằng backtick ở mọi truy vấn, dễ gây lỗi khi sinh SQLAlchemy model ở bước 2.2. **Bài học chung:** kiểm tra tên bảng dự kiến có trùng từ khoá SQL không ngay ở bước thiết kế ERD, không để phát hiện muộn lúc code.
- Đổi `order.cost` → `order_cost`, `price_request.order_id` → `sales_order_id` (đồng bộ theo tên bảng mới).
- Thống nhất `budget.budget_amount` → `amount` (khớp quy ước đặt tên cột số tiền với các bảng khác).
- Cập nhật lại sơ đồ Mermaid theo tên mới.
- Không phát hiện bảng/cột nào vi phạm nguyên tắc loại trừ CRM/Dòng tiền; FK khớp hoàn toàn với sơ đồ.

Bổ sung 6 mục "cần xác nhận" mới (tổng 9 mục, xem đầy đủ tại `docs/architecture/erd-tuan-02.md`) — đáng chú ý nhất:

- **Giả định mã khoá dùng chung giữa FT và AMIS** (mục #4) — các bảng nguồn AMIS (cost, budget, personnel_cost, debt) tham chiếu FK sang danh mục xây từ dữ liệu FT (division, department, employee, customer). Nếu 2 hệ thống không dùng chung mã, cần thêm bảng mapping trung gian. Đây là rủi ro cao nhất vì ảnh hưởng toàn bộ nhóm báo cáo Chi phí và Công nợ — **ưu tiên xác nhận trước khi sang bước 2.2**.
- `debt.aging_bucket` (ngưỡng quá hạn) là giá trị tính động theo ngày hiện tại, không nên là cột vật lý trong DB theo đúng nguyên tắc tách lớp của CLAUDE.md (logic không nằm trong `src/db/`) — cần COO xác nhận báo cáo Công nợ xem theo "hiện trạng" hay "snapshot import" để quyết định thiết kế đúng.

## Bài học rút ra

- **Luôn thiết kế ERD trên giấy/tài liệu trước khi giao cho AI sinh code** — bắt được lỗi đặt tên trùng reserved keyword ở giai đoạn rẻ nhất để sửa (đổi tên trong tài liệu) thay vì lúc code đã chạy.
- **"Giao việc cho subagent chuyên biệt" trong Claude Code CLI không phải lúc nào cũng hoạt động như tài liệu mô tả** — luôn chuẩn bị phương án dự phòng (persona nhúng thẳng vào prompt cho agent chung) để không bị chặn tiến độ khi gặp giới hạn thật của công cụ.
- **Yêu cầu subagent luôn liệt kê giả định thành mục "cần xác nhận"** (đã ghi rõ trong `db-schema-agent.md`) tạo ra kết quả có thể tin cậy hơn nhiều so với để AI âm thầm tự quyết — 9 mục cần xác nhận thu được là bằng chứng nguyên tắc này hoạt động đúng.

## Kết quả

ERD hoàn chỉnh (18 bảng, sơ đồ Mermaid, 9 mục cần xác nhận) đã lưu tại `docs/architecture/erd-tuan-02.md`, đã review bằng subagent (qua workaround), đã commit `cc61d19`. Trước khi sang bước 2.2, COO cần xác nhận ít nhất mục #4 (mã khoá dùng chung FT/AMIS) — ảnh hưởng rộng nhất nếu sai.
