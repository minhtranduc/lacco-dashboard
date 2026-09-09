# Nhật ký Tuần 5 — Module báo cáo đợt 2 & đồng bộ tài liệu (mốc giữa dự án)

## 1. Tổng quan

Tuần 5 hoàn thành cả 4 bước (5.1→5.4) trong 1 phiên làm việc dài, đạt mốc quan trọng nhất tính đến nay: **cả 6 nhóm báo cáo trong phạm vi Giai đoạn 1 đã hoạt động thật** (Kinh doanh, Khách hàng, Pricing, Chi phí, Công nợ — riêng Dòng tiền đã chốt dời Giai đoạn 2 từ bước 1.3, không tính vào phạm vi). Ngoài xây code, tuần này còn hình thành 1 tài liệu mới (SDD sống) và 1 persona mới (`doc-writer-agent`), và thực hiện checkpoint giữa dự án theo đúng lịch roadmap.

Về tiến độ: nội dung bám sát trình tự kế hoạch (23/25 bước Tuần 1-5 xong trước Tuần 5, nay 25/25 = 100% sau bước 5.4). Về lịch ngày: tiếp tục trễ so với mốc dự kiến gốc — Tuần 5 dự kiến kết thúc 30/08/2026, thực tế hoàn thành 09/09/2026, trễ 10 ngày. Xu hướng trễ 5 tuần gần nhất: +15, +13, +18, +15, +10 ngày — dao động ổn định quanh 2 tuần, KHÔNG xấu đi, phù hợp tinh thần "ngày là mốc linh hoạt, không phải deadline cứng" đã nêu từ dòng đầu tiên của tracker. Toàn dự án: **24/38 bước = 63,2%**.

## 2. Đối chiếu tiêu chí nghiệm thu (mục 8, Kế hoạch triển khai)

Nhắc lại: 7 tiêu chí là tiêu chí **cuối Giai đoạn 1** (8 tuần), không áp dụng riêng từng tuần. Tuần 5 đạt bước ngoặt cho 2 tiêu chí:

- **Tiêu chí #1** ("Tất cả 6 nhóm báo cáo... hoạt động"): **đạt đủ phạm vi Giai đoạn 1** — 5/5 nhóm trong phạm vi đã hoạt động thật, có RBAC (Kinh doanh, Khách hàng từ Tuần 4; Pricing, Chi phí, Công nợ từ bước 5.1). Nhóm thứ 6 (Dòng tiền) không tính vào tiêu chí này vì đã chốt dời Giai đoạn 2 (17/08/2026) — cần lưu ý khi đối chiếu cuối Giai đoạn 1, tránh hiểu nhầm "thiếu 1/6".
- **Tiêu chí #2** (RBAC 3 cấp): tiếp tục đúng cho 4 module mới, kể cả 2 mẫu RBAC mới chưa từng gặp (lọc theo nhân viên phụ trách thay vì khách hàng — Pricing; ẩn hẳn UI theo role — Chi phí).
- **Tiêu chí #3** (Audit log & login history): `login_history` đầy đủ từ bước 3.1 (đã kiểm chứng thật); `audit_log` cho thay đổi dữ liệu — **chưa được audit riêng trong case study này**, cần xác minh lại khi có tính năng ghi/sửa dữ liệu thật (hiện các module báo cáo đều chỉ đọc).
- **Tiêu chí #7** (Bộ tài liệu case study): +3 tài liệu tuần này (HD-15 phần bổ sung, HD-17, nhật ký này) — tổng 17 HD + 5 nhật ký tuần tính đến nay.
- Tiêu chí #4, #5, #6 (Export, tải 20 người dùng, backup/restore): chưa bắt đầu, đúng kế hoạch (Tuần 6-7).

## 3. Chi tiết các bước trong tuần

| Bước | Tên | Trạng thái | Ngày HT thực tế | Mã HD |
|---|---|---|---|---|
| 5.1 | Xây 4 module báo cáo còn lại (Đơn hàng, Pricing, Chi phí, Công nợ) | Hoàn thành | 09/09/2026 | HD-15 (bổ sung) |
| 5.2 | Đồng bộ tài liệu SDD | Hoàn thành | 09/09/2026 | HD-17 |
| 5.3 | Checkpoint giữa dự án | Hoàn thành | 09/09/2026 | — |
| 5.4 | Review & nhật ký Tuần 5 | Hoàn thành | 09/09/2026 | — |

Commit & CI (đều xác minh độc lập qua `git log`/`git show --stat` + GitHub REST API, không chỉ tin báo cáo CLI):

| Commit | Nội dung | CI |
|---|---|---|
| `325bbcd3` | 4 module báo cáo + fix `gen_debt()` | [`34367239192`](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34367239192) success |
| `6c35e194` | Bổ sung HD-15 (mở rộng multi-agent bước 5.1) | [`34368191871`](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34368191871) success |
| `a5a1131e` | SDD.md + README.md (fix encoding) + persona `doc-writer-agent` | [`34369331983`](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34369331983) success |
| `a0d2272a` | HD-17 | [`34369922058`](https://github.com/minhtranduc/lacco-dashboard/actions/runs/34369922058) success |

## 4. Quyết định kiến trúc & lý do

| Quyết định | Ai quyết | Lý do |
|---|---|---|
| Aging Công nợ tính động tại thời điểm xem, không lưu snapshot | **COO** (nghiệp vụ, qua `AskUserQuestion`) | Báo cáo công nợ cần phản ánh đúng hiện trạng quá hạn ngay lúc xem, không bị lỗi thời như snapshot cố định |
| RBAC Chi phí "Theo Khối": Admin/Manager theo Khối/Phòng mình, User bị ẩn hẳn | **COO** (nghiệp vụ, qua `AskUserQuestion`) | `cost`/`budget` không có dữ liệu cấp nhân viên — không có gì để User xem ở mức độ này |
| RBAC Chi phí "Theo Nhóm nhân sự": chỉ Admin | **COO** (nghiệp vụ, qua `AskUserQuestion`) | `personnel_cost` không có cột liên kết Khối/Phòng/NV — không thể lọc RBAC an toàn cho Manager/User |
| Chạy 2 đợt x 2 song song (không phải 4 song song 1 lần) cho bước 5.1 | **COO** (vận hành, qua `AskUserQuestion`) | Lần đầu vượt quy mô 2 instance — ưu tiên khả năng đối chiếu/kiểm soát hơn tốc độ |
| Pricing lọc RBAC theo nhân viên phụ trách (không theo `customer_ids`) | Claude (kỹ thuật) | `price_request`/`supplier_evaluation` không có khách hàng làm chủ thể chính (`customer_id` nullable) |
| Quyết định hiển thị/ẩn UI theo `scope.unrestricted` trực tiếp, không dựa vào bắt `PermissionError` | Claude (kỹ thuật) | Bắt exception chỉ nên là phòng vệ tầng 2, không phải cơ chế quyết định giao diện chính |
| SDD tách riêng khỏi `erd-tuan-02.md` (biên bản quyết định lịch sử, không sửa) | Claude (kỹ thuật/quy trình) | Tránh gộp 2 vai trò khác nhau (lịch sử đóng băng vs hiện trạng sống) vào 1 file |
| Không rush lịch, không cắt phạm vi dù trễ ~10-18 ngày/tuần | **COO** (định hướng ban đầu, tái xác nhận qua checkpoint 5.3) | Đúng tinh thần "ngày là mốc linh hoạt" đã nêu từ đầu tracker — ưu tiên chất lượng/đúng quy trình xác minh hơn tốc độ |

## 5. Vấn đề gặp phải & cách Claude hỗ trợ giải quyết

| # | Vấn đề | Cách xử lý |
|---|---|---|
| 1 | Agent Công nợ tự đóng khung "87% debt lệch phòng ban nhân viên" như câu hỏi nghiệp vụ cần hỏi COO | Đọc thẳng `gen_debt()` trước khi chuyển câu hỏi lên — phát hiện đây là lỗi sinh dữ liệu (division_id/department_id độc lập với employee_id), không phải thực tế nghiệp vụ. Bằng chứng thứ 2 (sau overlap KH/NV ở 4.1) cho nguyên tắc "không phải mọi con số đáng báo động đều là lỗi kiến trúc" |
| 2 | Sửa `gen_debt()` làm lệch dữ liệu của các bảng sinh SAU nó (`customer_classification_history`, `login_history`, `audit_log`) dù giữ nguyên `SEED=42` | Giải thích rõ nguyên nhân (cùng 1 chuỗi random, bớt 2 lệnh `random.choice()`/dòng làm lệch nhịp); re-verify toàn bộ bất biến đã xác lập trước đó (overlap 0%, dedup 0), không chỉ verify phần vừa sửa |
| 3 | `README.md` hiển thị toàn ký tự lỗi (mojibake) | Xác định đúng nguyên nhân bằng `file README.md` (UTF-16 LE, có thể do redirect PowerShell lúc khởi tạo repo) trước khi kết luận "nội dung hỏng" — decode đúng bằng `utf-16`, không mất dữ liệu gốc, viết lại bằng UTF-8 |
| 4 | Công cụ stage-file (device bridge) lỗi tạm thời HTTP 401 khi cần đưa file Excel/markdown vào workspace để sửa | Chuyển hướng: đọc/ghi trực tiếp trên máy người dùng qua shell của cầu nối thiết bị (Python + `openpyxl` + `soffice --headless` để recalc tại chỗ), vẫn giữ đúng quy trình an toàn (kiểm tra file khoá `~$...` trước/sau khi ghi) |
| 5 | `.git/index.lock` kẹt lại — tiếp tục lặp lại (đã ghi nhận từ Tuần 3-4) | Không đổi cách xử lý: luôn đưa vào VIỆC 1 của mỗi prompt CLI, không tự ý xử lý qua công cụ chẩn đoán |

## 6. Prompt tiêu biểu đã dùng trong tuần

- Hỏi gộp 4 quyết định RBAC/nghiệp vụ cùng lúc qua `AskUserQuestion` trước khi giao việc cho subagent (thay vì hỏi rải rác giữa chừng) — giảm số lần gián đoạn COO, và đảm bảo persona nhận đủ thông tin ngay từ đầu thay vì phải tự đoán rồi sửa lại.
- Prompt CLI 2 giai đoạn (build+test không commit → review độc lập → prompt commit riêng) tiếp tục áp dụng nhất quán cho cả 4 commit trong tuần, kể cả các thay đổi nhỏ (1 file HD).
- Prompt "sửa lỗi cụ thể" độc lập với prompt "build tính năng" khi phát hiện lỗi `gen_debt()` — tách riêng thay vì gộp chung để dễ đối chiếu trước/sau.

## 7. Ước tính thời gian tiết kiệm so với làm thủ công

Ước tính định tính (không phải số đo chính xác hay cam kết ROI chính thức): việc chạy 4 subagent theo 2 đợt song song, tự viết đủ RBAC/tách lớp theo checklist có sẵn, và tự phát hiện+sửa lỗi sinh dữ liệu qua đọc code — nếu làm thủ công (1 lập trình viên, tuần tự) nhiều khả năng cần nhiều ngày hơn cho riêng phần code, chưa kể công sức viết lại tài liệu kiến trúc từ đầu (SDD.md) thường bị trì hoãn/bỏ qua trong dự án thực tế vì tốn thời gian đối chiếu thủ công.

## 8. Bài học rút ra cho tuần sau

- **Checkpoint giữa dự án có giá trị nhất khi tách rõ 2 trục: tiến độ NỘI DUNG (thứ tự bước) và tiến độ LỊCH NGÀY** — trộn lẫn 2 trục dễ gây hoảng khi thấy "trễ 10 ngày" trong khi thực chất nội dung vẫn bám sát trình tự, không có bước nào bị bỏ qua hay làm ẩu.
- **Backlog bảo mật tồn đọng cần được gắn vào 1 mốc cụ thể trong roadmap (không chỉ "chưa cấp bách")** — checkpoint tuần này gắn rõ: phải xử lý trước bước 7.2 (Deploy), không để trôi tới cuối Giai đoạn 1 mới nhớ ra.
- **1 công cụ hạ tầng lỗi tạm thời không nên làm gián đoạn quy trình an toàn đã thiết lập** — khi `device_stage_files` lỗi 401, vẫn giữ nguyên nguyên tắc (kiểm tra lock file, recalc, xác minh sau khi ghi), chỉ đổi đường đi kỹ thuật.
- **Hình thành persona mới nên làm SAU khi tự tay làm việc đó ít nhất 1 lần**, không phải trước — áp dụng nhất quán từ `report-builder-agent` (bước 4.1) tới `doc-writer-agent` (bước 5.2), đảm bảo checklist trong persona phản ánh đúng vấn đề thật đã gặp.

## 9. Việc cần làm tiếp

- **Trước bước 7.2 (Deploy Windows Server) — ưu tiên xử lý**: tạo user MySQL least-privilege thay `root` trong `.env`; đổi `_DEV_FALLBACK_COOKIE_KEY` trong `authentication.py` thành raise lỗi thay vì fallback âm thầm.
- **Trước/trong bước 7.1 (Test suite cuối)**: bổ sung test tự động cho `src/services/report_*.py` (6 module, hiện 0% trong CI, chỉ đo `src/auth`) và cho `admin_actions.py` (0%).
- Xác nhận với COO/Trưởng phòng Vận hành các mục còn "cần xác nhận" tồn đọng (tổng hợp đầy đủ ở `docs/architecture/SDD.md` mục 9): danh sách `sales_order.status` đầy đủ, `invoice_status` độc lập hay không, tần suất snapshot phân loại KH, cách hiển thị nhóm "Chưa đến hạn" trong Công nợ, rủi ro nhân viên đổi phòng ban ảnh hưởng số liệu lịch sử Pricing/Chi phí.
- Tuỳ chọn (không bắt buộc): cập nhật lại ngày dự kiến Tuần 6-8 trong tracker cho thực tế hơn (dời khoảng +2 tuần) nếu COO muốn tracker phản ánh đúng lịch — không ảnh hưởng phạm vi 38 bước.
- Tuần 6 (bước 6.1-6.4): Export Excel/PDF, test tải 20 người dùng đồng thời, cấu hình Sentry — 3 việc kỹ thuật khác hẳn tính chất "xây báo cáo" của Tuần 4-5, cần chuẩn bị persona/công cụ mới phù hợp (VD: công cụ test tải, Sentry SDK) thay vì tái dùng `report-builder-agent`.
