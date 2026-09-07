# HD-15: Chạy nhiều subagent song song — chia việc không giẫm chân nhau

**Tuần:** 4 — Báo cáo Kinh doanh & Khách hàng | **Đối tượng phù hợp:** Cả hai (Lãnh đạo/BA + IT) | **Ngày thực hiện:** 07/09/2026

## Mục tiêu

Xây đồng thời 2 module báo cáo độc lập (Kinh doanh: doanh thu/lãi lỗ; Khách hàng: xu hướng phân loại A/B/C + nguồn) bằng cách chạy 2 instance của cùng 1 persona subagent (`report-builder-agent`) **song song trong cùng 1 lượt giao việc**, thay vì làm tuần tự từng module như các bước trước — bài học chính là chia phạm vi file rõ ràng ngay từ đầu để 2 tiến trình không đụng nhau khi gộp kết quả.

## Giải thích khái niệm: vì sao chạy song song, và điều kiện để làm an toàn

Các bước trước (2.1→3.4) đều giao việc tuần tự — 1 subagent, 1 việc, xong mới sang việc tiếp. Với 4.1, 2 module (Kinh doanh, Khách hàng) hoàn toàn độc lập về logic nghiệp vụ và không dùng chung file, nên chạy song song tiết kiệm thời gian thật (2 subagent làm cùng lúc thay vì nối đuôi). Điều kiện bắt buộc để làm an toàn — không phải chạy song song lúc nào cũng được:

- **Mỗi instance phải có ranh giới file tường minh, không chồng lấn** — không suy luận ngầm định "chắc không đụng nhau đâu". Persona `report-builder-agent` được viết lại với 1 mục riêng ("Bạn phụ trách ĐÚNG 1 module") liệt kê chính xác 2 file mỗi instance được tạo/sửa, cấm chạm vào `src/auth/`, `src/db/models/`, `src/app/main.py`, hay file của module khác dù "thấy tiện sửa luôn".
- **Cùng 1 persona, khác tham số giao việc** — không cần viết 2 persona riêng cho Kinh doanh và Khách hàng, chỉ cần prompt giao việc nói rõ module nào + đúng 2 tên file, phần nguyên tắc bắt buộc (RBAC, tách lớp, cache theo user) dùng chung.
- **Giao trong cùng 1 lượt** (2 lệnh Task/Agent gửi cùng lúc, không tuần tự) để thực sự chạy song song, không phải "gọi 2 lần liên tiếp" — nếu gọi tuần tự thì không có gì khác bước làm tuần tự thông thường, mất hết lợi ích thời gian.

## Cách tiếp cận / Quy trình đã dùng

1. Viết persona `.claude/agents/report-builder-agent.md` (qua CLI, vì `.claude/` bị chặn ghi qua device bridge) — trọng tâm là mục ranh giới file và mục "không tự loại trừ dữ liệu theo giả định" / "không tự xử lý nếu phát hiện 1 KH thuộc phạm vi nhiều NV" — 2 quy tắc này hoá ra chính là thứ giúp phát hiện đúng vấn đề thật ở bước sau, không phải quy tắc thừa.
2. Tạo `src/app/pages/` (quy ước multi-page gốc của Streamlit) làm nơi chứa trang của cả 2 module.
3. Giao việc cho 2 instance cùng lúc: Agent 1 phụ trách `report_kinh_doanh.py` + trang 1, Agent 2 phụ trách `report_khach_hang.py` + trang 2 — mỗi agent nhận đúng 2 tên file, không thấy phạm vi của agent còn lại.
4. Cả 2 agent hoàn thành không đụng file nhau (xác nhận bằng `git status`/liệt kê file trước khi commit) — nhưng đúng theo thiết kế persona, **cả 2 đều dừng lại và liệt kê "cần xác nhận" thay vì tự đoán**, tổng cộng 5 mục, trong đó 2 mục là quyết định nghiệp vụ thật và 2 mục hoá ra là lỗi kỹ thuật cần phân biệt rõ (xem bảng dưới).

### Phân loại 4 phát hiện — nghiệp vụ vs kỹ thuật, xử lý khác nhau

| Phát hiện | Loại | Cách xử lý |
|---|---|---|
| `sales_order.status = "Huỷ"` có tính vào doanh thu/lãi lỗ không? | **Nghiệp vụ** — cần COO quyết | Hỏi qua `AskUserQuestion`, COO chọn "loại trừ (khuyến nghị)" — áp trực tiếp vào `report_kinh_doanh.py`, có số liệu riêng theo dõi số đơn/giá trị Huỷ |
| ~73-80% khách hàng mẫu thuộc phạm vi RBAC của >1 nhân viên/phòng | Ban đầu tưởng là kiến trúc RBAC sai — **thực chất là lỗi kỹ thuật** | Đọc thẳng `scripts/generate_synthetic_sample_data.py` trước khi kết luận: `employee_id` được random độc lập với `customer_id` ở từng giao dịch — sinh dữ liệu không có ý nghĩa nghiệp vụ, không phải RBAC/`compute_data_scope()` sai |
| `customer_classification_history` có 2 dòng cùng (customer_id, ngày) khác hạng | **Lỗi kỹ thuật** thuần tuý | Thiếu khử trùng lặp ở vòng lặp sinh dữ liệu thứ 2 — sửa bằng retry chống trùng cặp |
| Giá trị `sales_order.status` thực tế gặp (Mới tạo/Đang xử lý/.../Huỷ) chưa được Trưởng phòng Vận hành xác nhận chính thức | Nghiệp vụ, **chưa chặn tiến độ** | Giữ nguyên cảnh báo "cần xác nhận" trong docstring, không tự ý coi là đã chốt |

Bài học ở đây: **không phải mọi con số "đáng báo động" đều là lỗi kiến trúc** — trước khi đưa 1 phát hiện lên thành câu hỏi nghiệp vụ cho COO, cần tự hỏi "đây có phải hệ quả của cách sinh/xử lý dữ liệu không?" và đọc code gốc để kiểm chứng, đúng tinh thần "xác minh trước khi tin" đã áp dụng xuyên suốt dự án.

### Lỗi thật gặp phải khi xử lý phát hiện kỹ thuật #1 (overlap KH/NV)

| # | Lỗi | Nguyên nhân | Cách phát hiện | Cách xử lý |
|---|---|---|---|---|
| 1 | Sửa lần 1 (random 20%/giao dịch dùng NV khác) vẫn cho overlap 57,1%, vượt xa ước tính | Nhầm "tỉ lệ ngẫu nhiên mỗi giao dịch" với "tỉ lệ khách hàng bị ảnh hưởng" — với KH có k giao dịch, xác suất dính chéo ít nhất 1 lần là 1-0,8^k (phép thử Bernoulli độc lập tích luỹ theo k), không phải cố định 20% | Tính tay đối chiếu công thức lý thuyết với số đo thực tế (53% dự đoán ≈ 57,1% đo được) trước khi kết luận | Đổi hẳn thiết kế: random ở **cấp khách hàng** (1 lần/KH, không phải 1 lần/giao dịch) — ~85% KH chỉ 1 NV phụ trách suốt lịch sử, ~15% có "NV thứ 2" tiếp quản từ 1 mốc `handover_date` cố định. Overlap không còn phụ thuộc số giao dịch/KH |
| 2 | `alembic downgrade base` (cần để tái tạo dữ liệu sạch) lỗi MySQL 1553: không xoá được index vì FK constraint còn tham chiếu | Lỗi có sẵn từ Tuần 2 trong `migrations/versions/02f963b388c8_...py`, hàm `downgrade()` — DROP INDEX đặt trước DROP FK CONSTRAINT trên cùng cột, sai thứ tự MySQL yêu cầu. `downgrade()` chưa từng chạy thành công lần nào trước đó nên lỗi này chưa từng lộ ra | Chạy thật `alembic downgrade base` lần đầu trong dự án (không phải suy luận) | Sửa thứ tự: thêm `op.drop_constraint()` (tên FK lấy thật từ `information_schema` của DB "lacco") ngay trước từng `op.drop_index()` liên quan. Xác nhận bằng `git diff` rằng `upgrade()` không đổi gì, rồi chạy thật lại `downgrade base` → `upgrade head` → import lại dữ liệu, thành công |

## Kết quả thu được

Commit `be61e51` (18 file, +1553/−268 dòng): fix bộ sinh dữ liệu mẫu (overlap + dedup), fix migration `downgrade()`, thêm `report_kinh_doanh.py` + `report_khach_hang.py` + 2 trang Streamlit tương ứng + `report-builder-agent.md`. CI xanh — xác minh độc lập qua GitHub REST API, run [`34107578768`](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34107578768), `conclusion: success`.

Kiểm chứng RBAC end-to-end thật (không chỉ đọc code) cho 3 vai trò, cả qua UI thật lẫn đối chiếu độc lập bằng `compute_data_scope()`:

| Vai trò | Số khách hàng thấy được | Đối chiếu độc lập |
|---|---|---|
| Admin | 30 (toàn bộ) | `fetch_all_customer_ids()` = 30 |
| Manager (phòng 4) | 7 | `fetch_customer_ids_for_department(4)` = 7 |
| User (nhân viên 5) | 1 | `fetch_customer_ids_for_employee(5)` = 1 |

Đúng quan hệ thu hẹp dần **User ⊆ Manager ⊆ Admin** — đúng thiết kế RBAC 3 cấp đã chốt từ bước 3.1.

## Bài học rút ra

- **Chạy song song chỉ an toàn khi ranh giới file được viết thành quy tắc tường minh trong persona, không phải "tự hiểu ngầm"** — kết quả 0 xung đột file ở lần chạy thật đầu tiên xác nhận cách tiếp cận đúng, nhưng không nên coi đó là mặc định cho mọi cặp việc; vẫn cần đánh giá lại ranh giới mỗi lần giao việc mới.
- **Persona thiết kế "liệt kê cần xác nhận, không tự đoán" trả giá trị thật** — nếu agent tự ý loại đơn Huỷ hoặc tự ý "xử lý" overlap KH/NV, sẽ mất cơ hội phát hiện 2 lỗi kỹ thuật thật (tích luỹ xác suất, migration bug) đang nằm ẩn trong dự án.
- **"Phát hiện nghiêm trọng" từ subagent cần được phân loại nghiệp vụ vs kỹ thuật trước khi hành động** — chỉ hỏi COO đúng phần nghiệp vụ thật (loại trừ đơn Huỷ), phần kỹ thuật (lỗi sinh dữ liệu, lỗi migration) tự điều tra tận gốc bằng cách đọc code nguồn rồi tự quyết, không làm phiền COO với câu hỏi không cần thiết.
- **Sửa 1 tham số random đơn lẻ (tỉ lệ %) có thể không đủ nếu không nghĩ về cách nó tích luỹ qua nhiều lần lặp** — bài học thống kê cụ thể: xác suất "dính ít nhất 1 lần" trong k lần thử độc lập tăng theo cấp số nhân bù (1-(1-p)^k), luôn tính thử bằng số trước khi tin 1 tỉ lệ % nhỏ là an toàn.
- **Một đường code (như `downgrade()`) tồn tại trong repo không có nghĩa là nó đã được kiểm chứng chạy được** — chỉ phát hiện lỗi migration có sẵn từ Tuần 2 khi thực sự cần dùng đến ở Tuần 4, củng cố nguyên tắc "chạy thật để xác minh" áp dụng cho mọi phần code, không chỉ code mới viết.

## Kết quả

Bước 4.1 hoàn thành: 2 module báo cáo (Kinh doanh, Khách hàng) chạy được thật, RBAC lọc đúng theo scope cho cả 3 vai trò, doanh thu/lãi lỗ loại trừ đúng đơn Huỷ theo quyết định COO. Phát sinh và xử lý dứt điểm 2 lỗi kỹ thuật nền tảng (bộ sinh dữ liệu mẫu, migration `downgrade()`) phát hiện được chính nhờ quy trình "không tự đoán, liệt kê cần xác nhận" của persona `report-builder-agent`. Lần đầu tiên trong dự án chạy 2 subagent thật sự song song (không tuần tự), 0 xung đột file.
