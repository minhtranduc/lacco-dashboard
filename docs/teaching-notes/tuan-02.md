# Nhật ký Tuần 2 — Data layer (schema, migration, import)

**Dự án:** Dashboard LACCO — Giai đoạn 1 (WebApp MVP) | **Tuần:** 2/8 | **Người thực hiện:** Minh Tran (COO) | **Ngày viết:** 22/08/2026

> Tài liệu này là nguyên liệu thô cho case study "Claude for Business" — ghi lại đúng những gì đã xảy ra (kể cả lỗi và đường vòng), không phải bản tường thuật lý tưởng hoá.

## 1. Tổng quan

Tuần 2 đặt mục tiêu: thiết kế ERD từ 12/14 yêu cầu "Đã rõ", sinh SQLAlchemy models, cấu hình Alembic + migration đầu tiên lên MySQL thật, và xây pipeline import Excel/CSV có validate. Đây là tầng dữ liệu (Data layer) — nền móng bắt buộc trước khi có thể xây báo cáo và RBAC ở các tuần sau.

**Kết quả:** 5/5 bước hoàn thành. Về mặt lịch, đây là điểm khác biệt đáng chú ý so với Tuần 1: khung dự kiến ban đầu là "03/08–09/08/2026", nhưng toàn bộ 5 bước (2.1 → 2.5) thực tế diễn ra dồn trong cùng 1 ngày làm việc — 22/08/2026 — thay vì trải dài như Tuần 1 (7 bước trải trên ~2.5 tuần lịch). Ghi nhận trung thực điều này: không phải vì Tuần 2 "nhanh hơn" về bản chất công việc, mà vì lịch làm việc thực tế của COO dồn vào 1 phiên dài — đúng tinh thần "không dồn ép tiến độ, có biên độ dự phòng" đã thống nhất từ Tuần 1, áp dụng theo cả 2 chiều (có thể trải dài, cũng có thể dồn lại tuỳ lịch thật).

## 2. Đối chiếu tiêu chí nghiệm thu

Tiêu chí ở mục 8 Kế hoạch triển khai vẫn là tiêu chí **cuối Giai đoạn 1**, chưa áp dụng từng tuần. Tuần 2 đặt nền móng như sau:

| Tiêu chí Giai đoạn 1 (mục 8) | Nền móng Tuần 2 đã đặt |
|---|---|
| 6 nhóm báo cáo hoạt động | Schema (18 bảng) phủ **5/6 nhóm**: kinh doanh, khách hàng, pricing, chi phí, công nợ. Nhóm "Dòng tiền" vẫn dời Giai đoạn 2 theo quyết định đã chốt từ Tuần 1 (chưa xác nhận được nguồn AMIS chính xác) — chưa có bảng tương ứng |
| RBAC 3 cấp theo A/B/C, Khối/Phòng | Bảng nền (`division`, `department`, `employee`, `users` với cột `role`, `customer.current_classification`) đã có trong DB thật — logic phân quyền thật chưa viết, đó là phạm vi Tuần 3 (bước 3.1) |
| Audit log, login history | Bảng `audit_log`, `login_history` đã tồn tại trong DB thật, đã test ghi/đọc bằng dữ liệu mẫu synthetic (30 dòng mỗi bảng) |
| Bộ tài liệu case study | HD-07 → HD-10 hoàn thành (4 tài liệu), nhật ký Tuần 2 (file này) là nhật ký thứ hai |
| Chuẩn bị dữ liệu mẫu (mục 9, đề xuất gốc) | Kế hoạch gốc đề xuất "dữ liệu mẫu đã ẩn danh hoá" — thực tế Tuần 2 dùng dữ liệu **hoàn toàn giả lập (synthetic)** thay vì ẩn danh hoá dữ liệu thật, vì chưa có sẵn export thật từ FT/AMIS ở thời điểm này (quyết định của COO khi được hỏi ở bước 2.4). Không sai lệch mục tiêu (vẫn phục vụ đúng việc test schema/pipeline), chỉ khác nguồn gốc dữ liệu |

## 3. Chi tiết 5 bước Tuần 2

| Bước | Tên | Trạng thái | Ngày hoàn thành thực tế | Mã HD |
|---|---|---|---|---|
| 2.1 | Thiết kế ERD & giao db-schema-agent | Hoàn thành | 22/08/2026 | HD-07 |
| 2.2 | Sinh SQLAlchemy models | Hoàn thành | 22/08/2026 | HD-08 |
| 2.3 | Cài Alembic, migration đầu tiên | Hoàn thành | 22/08/2026 | HD-09 |
| 2.4 | Pipeline import Excel/CSV | Hoàn thành | 22/08/2026 | HD-10 |
| 2.5 | Review & nhật ký Tuần 2 | Hoàn thành | 22/08/2026 | (file này) |

## 4. Quyết định kiến trúc & lý do

- **ERD 18 bảng, chỉ tạo bảng cho yêu cầu "Đã rõ"** (quyết định nghiệp vụ kế thừa từ Tuần 1) — 6 bảng danh mục, 8 bảng nghiệp vụ, 4 bảng bảo mật/audit bắt buộc theo CLAUDE.md.
- **Đổi tên bảng `order` → `sales_order`** (quyết định kỹ thuật, Claude tự phát hiện và sửa) — `ORDER` là từ khoá dành riêng trong MySQL 8.0, giữ tên gốc sẽ buộc escape bằng backtick ở mọi truy vấn.
- **FT và AMIS dùng chung 1 bộ mã Khối/Phòng/Nhân viên/Khách hàng** (quyết định nghiệp vụ, COO xác nhận trực tiếp) — cho phép các bảng nguồn AMIS (`cost`, `budget`, `personnel_cost`, `debt`) tham chiếu FK trực tiếp sang danh mục xây từ FT, không cần bảng mapping trung gian. Đây là rủi ro cao nhất trong ERD nếu sai, nên được ưu tiên xác nhận trước tiên.
- **`debt.aging_bucket` không lưu vật lý trong DB** (quyết định kỹ thuật, theo đúng nguyên tắc tách lớp CLAUDE.md mục 2) — giá trị này đổi theo ngày hiện tại nên tính động ở `src/services/` khi truy vấn, không nằm trong `src/db/`. Câu hỏi nghiệp vụ đi kèm ("xem theo hiện trạng hay snapshot import") vẫn còn treo, chưa chặn tiến độ.
- **`supplier_evaluation.score` dùng thang điểm 0–100** (quyết định nghiệp vụ, COO xác nhận chính thức ở bước 2.4/2.5) — trước đó `data-import-agent` tạm chọn làm mặc định để không chặn tiến độ viết Pandera schema; COO xác nhận giữ nguyên khi review.
- **Dữ liệu mẫu dùng synthetic thay vì anonymized-real** (quyết định nghiệp vụ, COO chọn khi được hỏi) — vì chưa có sẵn dữ liệu FT/AMIS đã ẩn danh hoá ở thời điểm này; đặt tên file tiền tố `synthetic_` để không nhầm với định dạng export thật.
- **Framework import dùng chung cho cả 18 bảng, không viết 18 hàm riêng lẻ** (quyết định kỹ thuật) — nhận tham số đường dẫn file + tên bảng đích + Pandera schema, giảm trùng lặp code đáng kể.
- **Thêm `.gitattributes` chuẩn hoá line-ending về LF** (quyết định kỹ thuật, phát sinh khi xác minh git status sau bước 2.4) — máy COO chạy Windows nên một số file được ghi bằng CRLF, gây lệch với bản đã commit (LF); không ảnh hưởng dữ liệu nhưng nên chuẩn hoá ngay để tránh commit thừa về sau.

## 5. Vấn đề gặp phải & cách Claude hỗ trợ giải quyết

| Vấn đề | Cách xử lý |
|---|---|
| Không gọi trực tiếp được subagent tuỳ biến (`db-schema-agent`, `data-import-agent`) theo tên qua Task tool — dù file `.claude/agents/*.md` đã đúng định dạng | Xác minh chắc chắn (kể cả ở phiên CLI hoàn toàn mới) đây là giới hạn cố định của harness, không phải lỗi cấu hình. Chốt quy ước chính thức: giao việc cho agent "general-purpose" kèm dán nguyên văn persona vào prompt — áp dụng nhất quán từ bước 2.2 trở đi, không cần thử lại theo tên (xem HD-07) |
| File `HD-07` bị bỏ sót chưa commit khi COO chuyển ngay sang việc khác | Claude Code CLI tự phát hiện và báo cáo lại (`git status` cho thấy file untracked); Claude xác minh độc lập rồi đưa prompt commit riêng, không gộp vào commit khác |
| Mật khẩu MySQL chứa ký tự đặc biệt (`@`, `%`) làm hỏng cú pháp connection string khi Alembic đọc qua `ConfigParser` | URL-encode mật khẩu, tạo engine trực tiếp bằng `create_engine()` trong `migrations/env.py` thay vì để Alembic tự ghép chuỗi từ `alembic.ini` |
| **Sự cố bảo mật:** mật khẩu MySQL thật bị dán nguyên văn vào chat khi giải thích lỗi Alembic ở trên | Flag ngay ở đầu phản hồi (trước mọi nội dung khác), khuyến nghị đổi mật khẩu + cập nhật `.env`/MCP, ghi lại thành bài học chính thức trong HD-09 (mô tả *dạng* lỗi thay vì trích giá trị thật khi báo cáo lỗi liên quan mật khẩu) |
| File Excel tracker bị khoá do đang mở trên máy COO (gặp 2 lần trong tuần) | Kiểm tra file `~$*.xlsx` trước mỗi lần ghi, dừng và yêu cầu đóng file, chỉ tiếp tục sau khi xác minh khoá đã hết và mtime khớp |
| Sau khi commit bước 2.4, `git status` cho thấy `.gitignore` và vài file CSV mẫu bị đánh dấu "modified" ngoài dự kiến | Kiểm tra kỹ bằng `git diff -b` và so byte đầu file — xác nhận chỉ khác line-ending (CRLF/LF), không mất dữ liệu thật; xử lý bằng cách thêm `.gitattributes` và `git add --renormalize .` |
| Lỗi nhỏ khi cập nhật tracker: giả định 1 ô Ghi chú đã có sẵn text để nối thêm, nhưng thực ra là rỗng (`None`) → `TypeError` | Lỗi xảy ra trước `wb.save()` nên không có state hỏng; sửa lại script gán thẳng giá trị thay vì nối chuỗi, chạy lại thành công |

## 6. Prompt tiêu biểu đã dùng trong tuần

- **Giao việc cho subagent tuỳ biến:** dùng agent "general-purpose", dán nguyên văn toàn bộ nội dung persona từ `.claude/agents/*.md` vào đầu prompt — mẫu này nên tái sử dụng cho mọi subagent tuỳ biến sau này trong harness hiện tại, không cần thử gọi theo tên trước.
- **Yêu cầu xác minh bằng hành động thật sau khi agent báo cáo xong:** luôn yêu cầu Claude Code tự chạy 1 câu lệnh xác minh độc lập (VD: `SELECT COUNT(*)`, đọc lại danh sách bảng trong `information_schema`) thay vì chỉ tin log "thành công" — áp dụng nhất quán từ MCP (Tuần 1) đến Alembic và pipeline import (Tuần 2).
- **Yêu cầu chủ động demo cả trường hợp lỗi, không chỉ đường thành công:** khi giao việc xây pipeline/validate, luôn yêu cầu agent tự tạo 1 ca dữ liệu lỗi cố ý và chạy thử, báo cáo nguyên văn thông báo lỗi — cách duy nhất để thực sự kiểm chứng "không nuốt lỗi âm thầm" thay vì chỉ tin lời khẳng định.

## 7. Ước tính thời gian tiết kiệm so với làm thủ công

*(Ước tính định tính, chưa phải số đo chính xác — dùng tham khảo cho slide báo cáo lãnh đạo, không dùng làm cam kết ROI chính thức.)*

| Việc | Làm thủ công (ước tính) | Với Claude | Ghi chú |
|---|---|---|---|
| Thiết kế ERD 18 bảng + review | ~1–2 ngày (họp bàn, vẽ tay, đối chiếu yêu cầu) | Vài giờ trong 1 phiên | Vẫn cần COO xác nhận các điểm nghiệp vụ quan trọng (mã dùng chung FT/AMIS, thang điểm) — AI không tự quyết thay |
| Sinh 871 dòng SQLAlchemy models (6 file) | Có thể mất 1 ngày gõ tay + tự kiểm tra chuẩn PEP8 | Vài chục phút, kèm tự review theo nguyên tắc đã định nghĩa | Việc để AI tự đề xuất cách chia file cho kết quả tổ chức tốt hơn dự kiến ban đầu |
| Cấu hình Alembic + debug lỗi password đặc biệt | Khó ước tính nếu tự tra cứu tài liệu Alembic/ConfigParser | Chẩn đoán và xử lý trong cùng phiên nhờ đọc trực tiếp thông báo lỗi | Đổi lại, chính sự cố này gây ra rủi ro bảo mật cần xử lý riêng |
| Xây pipeline import + Pandera schema cho 18 bảng, kèm demo lỗi | Có thể mất vài ngày (viết + test từng bảng) | Gói gọn trong 1 lượt giao việc + 1 lượt xác minh | Framework dùng chung giúp không phải lặp lại 18 lần logic tương tự |

## 8. Bài học rút ra cho Tuần 3

- **"Xác minh trước khi tin" cần áp dụng cả với những phần không nằm trong phạm vi được giao** — vấn đề line-ending chỉ lộ ra vì Claude chủ động chạy `git status` sau khi agent báo cáo xong, dù việc đó không thuộc nhiệm vụ được giao cho agent. Ở Tuần 3 (Auth & RBAC, có xử lý mật khẩu/bcrypt), nên giữ thói quen kiểm tra rộng hơn phạm vi hẹp của từng task.
- **Phân biệt quyết định kỹ thuật thuần tuý và quyết định cần input nghiệp vụ tiếp tục có hiệu quả** — các quyết định như đổi tên bảng, chọn kiểu dữ liệu, thêm `.gitattributes` được Claude tự xử lý; các quyết định như mã dùng chung FT/AMIS, thang điểm đánh giá NCC, nguồn dữ liệu mẫu đều dừng lại chờ COO — không có trường hợp nào bị lẫn lộn giữa 2 loại trong tuần này.
- **Sự cố bảo mật (mật khẩu lộ trong chat) vẫn chưa xác nhận đã khắc phục** — cần theo dõi tiếp tục sang Tuần 3, đặc biệt vì Tuần 3 sẽ làm việc trực tiếp với `bcrypt`/session, càng cần môi trường DB sạch.
- **Quy ước `.gitattributes`/line-ending nên thiết lập ngay từ đầu dự án** thay vì đợi phát hiện giữa chừng — bài học áp dụng được cho các dự án tương lai có COO dùng Windows, team dùng hệ điều hành khác nhau.

## 9. Việc cần làm tiếp (Tuần 3)

- Bước 3.1: Xây Auth & RBAC (HD-11) — đăng nhập, `bcrypt`, session; khung `streamlit-authenticator`; RBAC 3 cấp theo Khối/Phòng, KH A/B/C.
- **Đổi mật khẩu MySQL bị lộ trong chat ở bước 2.3** (chưa xác nhận đã thực hiện) — cập nhật lại `.env` và cấu hình MCP local sau khi đổi.
- Chốt dần các mục còn mở trong `erd-tuan-02.md` (8/10 mục, xem file để đầy đủ) — ưu tiên mục #6 (`debt.aging_bucket`: hiện trạng hay snapshot) trước khi có module báo cáo Công nợ, và mục #1/#2/#8 (danh sách giá trị enum cụ thể) trước khi RBAC/báo cáo cần lọc theo trạng thái.
- `requirements.txt` vẫn chưa tạo (đã dời từ bước 2.3) — nên tạo trước khi Tuần 3 thêm dependency mới (`streamlit-authenticator`, `bcrypt`).
- Tạo user MySQL riêng chỉ quyền cần thiết thay cho `root` (đã ghi từ Tuần 1, chưa thực hiện) — nên làm trước khi RBAC thật đi vào hoạt động.
