# Nhật ký Tuần 4 — Báo cáo Kinh doanh & Khách hàng (đợt 1)

**Thời gian thực hiện thực tế:** 07/09/2026 (dồn trong 1 ngày, tương tự Tuần 2) | **Khung dự kiến gốc:** 17/08 – 23/08/2026

## 1. Tổng quan

Tuần 4 xây 2/6 module báo cáo nghiệp vụ (Kinh doanh, Khách hàng) — lần đầu tiên trong dự án dùng cách chạy 2 subagent thật sự song song thay vì tuần tự, cộng thêm 1 vòng audit bảo mật độc lập và 1 vòng đối chiếu KPI với tài liệu gốc. Cả 4 bước (4.1→4.4) hoàn thành **cùng ngày 07/09/2026** — tiếp tục đúng pattern đã thấy ở Tuần 2 và nửa sau Tuần 3: khi đã có đủ nền tảng (persona, quy trình xác minh, tracker), một tuần theo kế hoạch gốc có thể dồn vào 1 phiên làm việc thực tế, miễn là mỗi bước vẫn được xác minh đầy đủ trước khi coi là xong — không đánh đổi tốc độ lấy chất lượng xác minh.

Tuần 4 hoàn thành **4/4 bước = 100%**. Tổng tiến độ dự án sau Tuần 4: **20/38 bước = 52,6%** — qua nửa chặng đường Giai đoạn 1.

## 2. Đối chiếu tiêu chí nghiệm thu (mục 8 Kế hoạch triển khai)

Nhắc lại: 7 tiêu chí ở mục 8 là tiêu chí **cuối Giai đoạn 1** (8 tuần), không áp dụng riêng từng tuần. Tuần 4 đặt thêm nền móng cho:

- **Tiêu chí #1** ("Tất cả 6 nhóm báo cáo... hoạt động"): 2/6 nhóm (Kinh doanh, Khách hàng) đã hoạt động thật, có RBAC, có đủ KPI theo Phụ lục B SDD gốc. Còn 4/6 (Đơn hàng, Pricing, Chi phí, Công nợ, Dòng tiền — thực ra là 5 nhóm còn lại theo bảng roadmap) dự kiến ở Tuần 5.
- **Tiêu chí #2** ("RBAC 3 cấp hoạt động đúng theo phân loại KH A/B/C và Khối/Phòng"): được kiểm chứng lại thật sự end-to-end lần đầu qua UI (không chỉ qua code) ở bước 4.1, và audit riêng phần cache (rủi ro rò dữ liệu qua `@st.cache_data`) ở bước 4.2 — 2 lớp kiểm tra bổ sung cho tiêu chí này, không phải chỉ dừng ở thiết kế ban đầu (Tuần 3).
- **Tiêu chí #7** ("Có bộ tài liệu case study..."): thêm HD-15, HD-16 và nhật ký này.

Chưa chạm tới: tiêu chí #3 (audit log/login history — đã có từ Tuần 3, không đổi), #4 (Export Excel/PDF — Tuần 6), #5 (tải 20 user — Tuần 6), #6 (backup/restore — Tuần 7).

## 3. Bảng chi tiết các bước trong tuần

| Bước | Tên | Trạng thái | Ngày hoàn thành | Mã HD |
|---|---|---|---|---|
| 4.1 | Chạy song song 2 module báo cáo | Hoàn thành | 07/09/2026 | HD-15 |
| 4.2 | Áp dụng cache an toàn multi-user | Hoàn thành | 07/09/2026 | HD-16 |
| 4.3 | Đối chiếu KPI & UI | Hoàn thành | 07/09/2026 | (không có, thuộc HD-15/16) |
| 4.4 | Review & nhật ký Tuần 4 | Hoàn thành | 07/09/2026 | — |

Commit chính trong tuần (đều đã xác minh độc lập qua `git show --stat` + GitHub REST API, CI xanh cho cả 4):

| Commit | Nội dung | CI |
|---|---|---|
| `be61e51` | Module Kinh doanh + Khách hàng, fix generator + fix migration | [34107578768](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34107578768) success |
| `5146ceb` | HD-15 | [34108435875](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34108435875) success |
| `a28de5c` | HD-16 | [34109507858](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34109507858) success |
| `09e5f09` | Bổ sung 4 KPI theo Phụ lục B (bước 4.3) | [34127220319](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34127220319) success |

## 4. Quyết định kiến trúc & lý do

| Quyết định | Ai quyết | Lý do |
|---|---|---|
| Chạy 2 instance `report-builder-agent` song song, ranh giới đúng 2 file/instance | Claude (kỹ thuật) | 2 module độc lập hoàn toàn về logic và file — tiết kiệm thời gian thật so với làm tuần tự, miễn là ranh giới tường minh trong persona (không suy luận ngầm) |
| Loại trừ đơn `status="Huỷ"` khỏi doanh thu/lãi lỗ | **COO** (nghiệp vụ, qua `AskUserQuestion`) | Đơn huỷ không phản ánh doanh thu/lãi lỗ thật — vẫn giữ số liệu riêng theo dõi tỷ lệ huỷ đơn |
| Sửa bộ sinh dữ liệu mẫu: NV phụ trách chính cố định + "NV thứ 2" theo mốc `handover_date` (thay vì random độc lập mỗi giao dịch) | Claude (kỹ thuật) | Root-cause qua đọc code: random độc lập theo giao dịch gây overlap RBAC ảo lên tới 73-80%, không phản ánh nghiệp vụ thật; cách mới mô phỏng đúng tình huống thật (NV nghỉ việc/chuyển phòng) và không bị tích luỹ xác suất theo số giao dịch |
| Sửa thứ tự `DROP` trong `migrations/.../downgrade()` | Claude (kỹ thuật) | Lỗi có sẵn từ Tuần 2, chỉ lộ ra khi thật sự cần chạy `downgrade base` lần đầu — an toàn để sửa vì `downgrade()` chưa từng chạy thành công trước đó |
| Audit cache multi-user giao riêng cho `qa-reviewer-agent` (không dùng lại tự-review của `report-builder-agent`) | Claude (kỹ thuật/quy trình) | Tách vai trò người viết code và người audit — đúng nguyên tắc đã dùng ở bước 3.2, không coi 1 lần tự-review nhanh là đủ cho rủi ro bảo mật lớn nhất dự án |
| Dùng danh mục KPI ở Phụ lục B (SDD gốc) làm chuẩn đối chiếu, nhưng bỏ qua phần schema/module cũ trong cùng tài liệu | Claude (kỹ thuật) | SDD gốc là bản trước redesign ERD (còn nhắc `WeeklySales`, `Treemap` đã bị thay thế) — danh mục KPI (Revenue, Profit, Profit Margin, Top Employee/Department, Trend) vẫn là KPI nghiệp vụ hợp lệ, tách biệt khỏi phần schema đã lỗi thời |
| Giữ nguyên ISO week (không đổi theo quy ước AMIS/FT riêng) cho biểu đồ Trend theo Tuần | **COO** (nghiệp vụ, qua `AskUserQuestion`) | Xác nhận công ty không có quy ước tuần tài chính khác biệt cần áp dụng |
| Hiển thị "N/A" thay vì "0.0%" khi revenue=0 ở metric Tỷ suất lợi nhuận | Claude (kỹ thuật/UX) | "0.0%" dễ gây hiểu lầm "có doanh thu nhưng lãi bằng 0" trong khi thực chất là "không có dữ liệu trong phạm vi lọc" |

## 5. Vấn đề gặp phải & cách Claude hỗ trợ giải quyết

| # | Vấn đề | Nguyên nhân | Cách xử lý |
|---|---|---|---|
| 1 | Sau lần sửa random đầu tiên (20%/giao dịch dùng NV khác), overlap KH/NV vẫn tới 57,1%, vượt xa dự kiến | Nhầm "tỉ lệ random mỗi giao dịch" với "tỉ lệ khách hàng bị ảnh hưởng" — xác suất dính chéo tích luỹ theo số giao dịch/KH (1-0,8^k), không cố định 20% | Tính tay đối chiếu công thức lý thuyết với số đo thực tế trước khi kết luận; thiết kế lại: random ở cấp khách hàng (1 lần/KH), không phải cấp giao dịch |
| 2 | `alembic downgrade base` lỗi MySQL 1553 (không xoá được index vì FK constraint còn tham chiếu) | Lỗi có sẵn từ Tuần 2 trong `downgrade()`, thứ tự `DROP INDEX` trước `DROP CONSTRAINT` sai — chưa từng lộ ra vì chưa ai chạy `downgrade base` thật trước đó | Sửa thứ tự, lấy tên FK thật từ `information_schema`, xác nhận `upgrade()` không đổi qua `git diff`, chạy thật lại toàn bộ chu trình downgrade→upgrade→import |
| 3 | Lỗi encoding console Windows khi in tiếng Việt (không phải lỗi logic) | Console Windows mặc định không dùng UTF-8 | Chạy lại với `PYTHONIOENCODING=utf-8` / ghi file bằng `encoding='utf-8'` |
| 4 | `qa-reviewer-agent` tự mâu thuẫn trong báo cáo audit cache: kết luận "8/8 PASS" nhưng bảng chi tiết liệt kê đúng 9 hàm | Lỗi đếm tổng trong câu tóm tắt của agent — nội dung bảng chi tiết vẫn đúng | Tự đối chiếu bằng đếm lại bảng + `grep` độc lập trên code thật — xác nhận 9/9 đều PASS, không phải lỗi bảo mật, chỉ là lỗi đếm |
| 5 | Tài liệu "Phụ lục B (SDD gốc)" nằm trong `Archive/`, và bản thân tài liệu đã lỗi thời (schema `WeeklySales`/`Treemap` cũ) | SDD được viết trước khi redesign ERD ở bước 2.1, chưa cập nhật lại | Đọc trực tiếp toàn bộ tài liệu trước khi áp dụng — chỉ dùng phần danh mục KPI (không phụ thuộc schema), bỏ qua phần module/CSDL đã lỗi thời, ghi rõ lý do trong tracker để phiên sau không hiểu lầm SDD này còn đúng 100% |
| 6 | `.git/index.lock` kẹt lại nhiều lần trong tuần (ít nhất 3 lần) | Công cụ chẩn đoán chạy `git status`/`git log` qua cầu nối thiết bị không có quyền tự xoá file lock nó tạo ra | Luôn đưa VIỆC dọn dẹp lock vào đầu mỗi prompt CLI; xác nhận là file 0 byte, không có tiến trình git chạy, trước khi yêu cầu xoá |
| 7 | Không tự động hoá được qua UI để test trường hợp `revenue=0` (widget `st.date_input` không nhận nhập liệu trực tiếp qua tool) | Giới hạn của công cụ tự động hoá trình duyệt với widget lịch popup của Streamlit | Verify bằng script Python độc lập gọi đúng hàm sản xuất (`get_revenue_profit_by_service` với khoảng ngày không có dữ liệu) thay vì ép test qua UI — vẫn đủ tin cậy vì gọi đúng code thật |

## 6. Prompt tiêu biểu đã dùng trong tuần

- **Giao 2 subagent cùng persona chạy song song**: prompt nêu rõ "Agent 1 phụ trách đúng 2 file X, Y — Agent 2 phụ trách đúng 2 file A, B — không đụng phạm vi của nhau" — gửi trong cùng 1 lượt (không tuần tự).
- **Prompt có ngưỡng dừng rõ ràng cho việc thử-sửa random/thống kê**: "nếu con số đo được vượt quá X%, DỪNG LẠI, không tự sửa thêm, báo cáo chi tiết" — giúp CLI biết chính xác khi nào cần dừng để hỏi thay vì tự ý tiếp tục hoặc đoán mò hướng sửa tiếp theo.
- **Prompt audit độc lập bằng persona khác** (không phải người vừa viết code): dùng lại đúng `qa-reviewer-agent` (chỉ đọc) để audit toàn bộ dự án, không chỉ code mới trong tuần — tránh coi tự-review của người viết code là đủ cho rủi ro bảo mật.
- **Prompt commit luôn kèm sẵn message đầy đủ + footer attribution** — giảm rủi ro CLI tự soạn message thiếu chi tiết hoặc quên footer.

## 7. Ước tính thời gian tiết kiệm so với làm thủ công

*(Ước tính định tính, không phải số đo chính xác hay cam kết ROI chính thức.)* Xây 2 module báo cáo hoàn chỉnh (service + UI + RBAC + cache đúng chuẩn) theo cách thủ công thường cần 1 lập trình viên vài ngày làm việc mỗi module; ở đây 2 module hoàn thành song song, cùng ngày, cộng thêm phát hiện và sửa 2 lỗi kỹ thuật nền tảng (generator, migration) không nằm trong phạm vi ban đầu. Phần audit bảo mật (bước 4.2) và đối chiếu KPI (bước 4.3) — vốn dễ bị bỏ qua hoặc làm qua loa trong dự án thủ công vì tốn thời gian — được thực hiện đầy đủ, có bằng chứng cụ thể, nhờ chi phí thực hiện thấp hơn khi giao cho subagent chuyên trách.

## 8. Bài học rút ra cho tuần sau

- **Tài liệu gốc (SDD, Kế hoạch...) không mặc định còn đúng 100% theo thời gian** — luôn đọc trực tiếp trước khi dùng làm chuẩn đối chiếu, tách phần nội dung còn giá trị (ở đây: danh mục KPI) khỏi phần đã lỗi thời (schema/module cũ), thay vì bỏ qua cả tài liệu hoặc tin tưởng mù quáng toàn bộ.
- **Đặt ngưỡng dừng cụ thể (con số %, không phải "nếu thấy bất thường")** khi giao việc có yếu tố thống kê/random cho subagent — giúp subagent tự biết chính xác khi nào cần dừng lại báo cáo thay vì tự ý đoán tiếp hoặc tự sửa sai hướng.
- **Audit độc lập vẫn cần tự đối chiếu số liệu cụ thể** — 1 báo cáo "N/N PASS" đẹp không tự động đúng, phát hiện lệch đếm 8 vs 9 ở bước 4.2 là ví dụ cụ thể cho nguyên tắc "xác minh trước khi tin" áp dụng ngay cả với chính các agent chuyên trách kiểm tra.
- **Chạy song song hiệu quả nhưng không miễn phí về mặt kiểm soát** — cần ranh giới file tường minh viết thành quy tắc trong persona, và vẫn cần kiểm tra riêng (không phải bằng chứng "0 xung đột file" mặc nhiên) trước khi mở rộng số lượng agent chạy đồng thời ở Tuần 5.

## 9. Việc cần làm tiếp

- **Tồn đọng từ các tuần trước (chưa xử lý, không cấp bách trong Giai đoạn 1)**: tạo user MySQL least-privilege thay `root` trong `.env`; đổi `_DEV_FALLBACK_COOKIE_KEY` trong `authentication.py` thành raise lỗi thay vì fallback âm thầm trước khi có production thật; thêm test coverage cho `admin_actions.py` (hiện 0%).
- **Tuần 5 (bước 5.1)**: xây 5 module báo cáo còn lại (Đơn hàng, Pricing, Chi phí, Công nợ, Dòng tiền) — tiếp tục HD-15 ở quy mô multi-agent lớn hơn (nhiều hơn 2 instance chạy song song). Cần cân nhắc trước: giới hạn hợp lý về số agent chạy đồng thời (tài nguyên, độ khó review kết quả khi có >2 instance cùng lúc) trước khi quyết định chạy toàn bộ 5 module cùng lúc hay chia theo đợt nhỏ hơn.
- Khi mở rộng sang nhiều module hơn, cân nhắc liệu Phụ lục B (SDD gốc) có định nghĩa KPI cho các module còn lại (Đơn hàng, Pricing, Chi phí, Công nợ, Dòng tiền) hay không — nếu SDD gốc không có, cần lấy chuẩn KPI từ mẫu yêu cầu đã "Đã rõ" ở bước 1.3 thay vì tự suy diễn.
