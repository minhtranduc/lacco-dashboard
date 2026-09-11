# CLAUDE.md — lacco-dashboard

> File context gốc repo, giúp Claude Code hiểu dự án ngay từ đầu mỗi phiên, không cần giải thích lại từ đầu.
> **Phiên bản:** v9 — 11/09/2026 | **Nguồn:** Tài liệu Kiến trúc Hệ thống, Kế hoạch triển khai Dashboard LACCO, Sheet 1 "Mẫu thu thập yêu cầu" (Bieu_mau_Yeu_cau_va_RACI_LACCO.xlsx — 12/14 dòng "Đã rõ", 2/14 chốt chuyển sang Giai đoạn 2). Bảng trạng thái yêu cầu chi tiết: xem `.claude/rules/trang-thai-yeu-cau.md`.
> Phỏng vấn thu thập yêu cầu (bước 1.3) đã hoàn thành 17/08/2026. Chỉ còn 2 báo cáo ngoài phạm vi Giai đoạn 1: **CRM** (chưa có dữ liệu trên hệ thống) và **Dòng tiền** (nguồn AMIS chưa xác nhận) — cả hai đã chốt dời sang Giai đoạn 2, không dựng logic/schema cho 2 phần này ở Giai đoạn 1.

## 1. Bối cảnh dự án

LACCO là công ty Logistics & Giao nhận vận tải. Dự án xây dựng WebApp Dashboard hỗ trợ ra quyết định, cung cấp báo cáo kinh doanh/chi phí/khách hàng/đơn hàng gần thời gian thực cho Ban Lãnh đạo, Trưởng phòng và nhân viên.

- **Phạm vi Giai đoạn 1 (hiện tại):** 5 nhóm báo cáo — Kinh doanh, Khách hàng, Pricing, Chi phí, Công nợ — cộng với tình trạng đơn hàng và tình trạng xuất hóa đơn. (Dòng tiền đã chốt dời Giai đoạn 2, xem ghi chú đầu file — trước bản v3 mục này liệt kê nhầm 6 nhóm gồm cả Dòng tiền, mâu thuẫn với ghi chú đầu file, đã sửa.)
- **KHÔNG thuộc phạm vi Giai đoạn 1:** Báo cáo Marketing (đã xác nhận 20/07/2026, có thể xét lại ở Giai đoạn 2). Không tự ý code phần này.
- **Người dùng:** một mình COO trực tiếp điều khiển Claude; không có đội dev backup — ưu tiên code rõ ràng, dễ đọc lại sau này hơn là tối ưu sớm.
- **Nguồn dữ liệu:** Hệ thống FT (nghiệp vụ kinh doanh/đơn hàng) và AMIS (chi phí, công nợ, dòng tiền) — import qua Excel/CSV, không kết nối trực tiếp hệ thống nguồn ở Giai đoạn 1.

## 2. Kiến trúc & cấu trúc thư mục

Kiến trúc 3 lớp (đã scaffold ở bước 1.4, commit `2797514`):

```
lacco-dashboard/
├── CLAUDE.md                # file này
├── docs/
│   ├── requirements/        # tài liệu nghiệp vụ gốc
│   ├── architecture/        # SDD, cập nhật dần
│   └── teaching-notes/      # nhật ký học tập — KHÔNG chứa logic dự án, không phụ thuộc vào
├── src/
│   ├── app/                 # Presentation layer — Streamlit pages
│   │   └── pages/           # Trang multi-page native của Streamlit (từ Tuần 4, bước 4.1) —
│   │                        # mỗi module báo cáo 1 file, đặt tên "<N>_<Ten_trang>.py"
│   ├── services/            # Business Logic layer — tính KPI, xử lý nghiệp vụ
│   ├── db/                  # Data layer — SQLAlchemy models, migrations (Alembic)
│   └── auth/                # RBAC, bcrypt, session
├── data/sample/              # dữ liệu mẫu ĐÃ ẨN DANH — không đưa dữ liệu thật vào đây
├── tests/                    # pytest, chạy trên SQLite in-memory (từ Tuần 3, HD-13)
├── .claude/agents/           # định nghĩa subagent chuyên biệt
├── .github/workflows/        # CI (lint + test tự động khi push/PR, từ Tuần 3, HD-14)
└── scripts/
```

Luồng dữ liệu: `Excel/CSV → Import → MySQL → SQLAlchemy → Pandas → Plotly → Streamlit → Browser`

Nguyên tắc bắt buộc: **không trộn lẫn 3 lớp** — code truy vấn DB không được nằm trong `src/app/`, logic tính KPI không được nằm trong `src/db/`. Việc này để đổi giao diện không ảnh hưởng logic nghiệp vụ, và ngược lại.

**Lưu ý vận hành khi giao việc cho subagent (`.claude/agents/*.md`):** harness Claude Code hiện tại KHÔNG hỗ trợ gọi subagent tuỳ biến trực tiếp theo tên qua Task tool — đã xác nhận chắc chắn ở bước 2.2 (kể cả phiên CLI hoàn toàn mới), xem `docs/teaching-notes/huong-dan/HD-07-giao-nhiem-vu-subagent.md`. Quy ước chính thức: luôn giao việc qua agent loại "general-purpose", dán nguyên văn toàn bộ nội dung persona từ file `.claude/agents/*.md` liên quan vào đầu prompt — không cần thử gọi theo tên trước.

**Chạy nhiều instance cùng 1 persona song song (từ Tuần 4, bước 4.1, xem HD-15):** khi giao việc cho >1 instance cùng persona (ví dụ nhiều `report-builder-agent` xây nhiều module báo cáo cùng lúc), BẮT BUỘC chỉ định rõ trong prompt đúng phạm vi file mỗi instance được tạo/sửa (thường 2 file/instance: 1 service + 1 trang) — không để instance tự suy luận ranh giới. Đã kiểm chứng thật: 0 xung đột file khi ranh giới tường minh. **Mở rộng ở bước 5.1 (Tuần 5, xem HD-15 mục bổ sung):** đã thử thành công quy mô lớn hơn — 4 module/2 đợt x 2 instance song song (thay vì 2 instance/1 đợt như Tuần 4) — vẫn 0 xung đột file với cùng nguyên tắc ranh giới tường minh; đây là quy mô khuyến nghị mặc định khi cần >2 module cùng lúc, trừ khi có lý do cụ thể để chọn khác.

**Persona `doc-writer-agent` (từ Tuần 5, bước 5.2, xem HD-17):** chuyên trách đồng bộ `docs/architecture/SDD.md` (tài liệu kiến trúc "sống") và `README.md` gốc theo code thực tế — KHÔNG đụng `erd-tuan-02.md` (biên bản quyết định lịch sử, không sửa lại), `CLAUDE.md`, hay bất kỳ file `.claude/`. Dùng khi code đã đổi đủ nhiều (thêm module, đổi RBAC, đổi schema) cần đồng bộ lại tài liệu kiến trúc — không dùng cho HD-0x/nhật ký tuần (việc của skill `lacco-hd-doc-writer`).

**Tính năng phụ thuộc hạ tầng ngoài tầm kiểm soát code (từ Tuần 6, bước 6.1, xem HD-18):** khi 1 tính năng cần 1 thành phần hạ tầng không ổn định trên mọi môi trường (ví dụ `kaleido` cần khởi động Chrome headless để render ảnh chart cho PDF — có thể treo/crash tuỳ máy, tuỳ phần mềm bảo mật cài trên máy, không xác định được nguyên nhân dứt điểm), KHÔNG ép tính năng đó chạy bằng mọi giá. Bắt buộc thiết kế graceful fallback (timeout tường minh + phương án dự phòng không có phần phụ thuộc đó) để tính năng chính không bao giờ thất bại hoàn toàn. Áp dụng cho mọi tính năng tương tự sau này, không chỉ export PDF.

## 3. Tech stack

**Lõi (đã chốt trong Tài liệu Kiến trúc Hệ thống):** Python 3.12, Streamlit, MySQL 8.0, SQLAlchemy + mysql-connector-python, Pandas, Plotly, bcrypt.

**Bổ sung theo kế hoạch (không tự ý đổi sang thư viện khác ngoài danh sách này):**

| Nhóm | Công cụ | Thêm từ |
|---|---|---|
| Migration DB | Alembic | Tuần 2 |
| Validate dữ liệu import | Pandera | Tuần 2 |
| Testing | pytest + pytest-cov | Tuần 3 |
| Lint/Format | Ruff | Tuần 3 (bước 3.4) |
| CI/CD | GitHub Actions | Tuần 3–4 |
| Khung đăng nhập | streamlit-authenticator | Tuần 3 |
| Logging | Loguru | Ngay khi cần log |
| Config/biến môi trường | python-dotenv + Pydantic Settings | Ngay khi cần config |
| Giám sát lỗi | Sentry (free/self-host) | Trước go-live (Tuần 7) |
| Export Excel | openpyxl (đã chốt, không dùng XlsxWriter) | Tuần 6 (bước 6.1) |
| Export PDF | ReportLab (đã chốt thay WeasyPrint — tránh phụ thuộc cài GTK3 runtime riêng trên Windows Server, xem HD-18) | Tuần 6 (bước 6.1) |
| Render ảnh chart Plotly cho PDF | kaleido (pin `==0.2.1` — bản `1.4.0` lỗi `BrowserFailedError` trên máy test) | Tuần 6 (bước 6.1) — **rủi ro môi trường đã ghi nhận (xem HD-18): cần khởi động Chrome headless ổn định, chưa xác nhận được trên máy dev hiện tại lẫn Windows Server thật, phải kiểm tra độc lập trước go-live (bước 7.2); tính năng có graceful fallback nên không chặn tiến độ** |

**Không đổi framework nền** (Streamlit, SQLAlchemy) trong Giai đoạn 1 — quyết định đã cân nhắc trong Kế hoạch triển khai, tránh phát sinh thời gian học kiến trúc mới giữa lộ trình 8 tuần.

## 4. Quy ước code

- Tuân thủ PEP8; docstring cho mọi function/class public.
- Đặt tên biến/hàm/class bằng tiếng Anh; label hiển thị UI và comment giải thích nghiệp vụ có thể dùng tiếng Việt.
- Dùng Loguru để log, không dùng `print()` cho việc theo dõi lỗi/luồng chạy.
- Xử lý lỗi bằng `except` cụ thể theo loại lỗi, không dùng bare `except:`; lỗi nghiệp vụ phải vừa log vừa hiển thị thông báo rõ ràng cho người dùng (không nuốt lỗi âm thầm).
- **Mọi truy vấn SQL bắt buộc qua SQLAlchemy (parameterized query)** — cấm nối chuỗi SQL thủ công dưới mọi hình thức, kể cả khi "chỉ để test nhanh".
- **PEP8/import-order được kiểm tra tự động bằng Ruff** (từ bước 3.4, `pyproject.toml`) — chạy `ruff check` + `ruff format --check` cục bộ trước khi commit, tránh để CI (mục 5) phát hiện thay. Không tắt/nới lỏng rule đã bật trong `pyproject.toml` mà không ghi lý do vào đây.

## 5. Lệnh thường dùng

*(Migration và import đã chạy thật từ Tuần 2 — xem HD-09, HD-10. Lệnh app đã có code thật từ bước 3.1 (Auth & RBAC) — xem HD-11. Lệnh test đã có test thật cho `src/auth/` từ bước 3.3 — xem HD-13. Lệnh lint/format thêm từ bước 3.4 — xem HD-14.)*

```bash
# Chạy app local (có code thật từ bước 3.1 — trang demo đăng nhập + hiển thị phạm vi RBAC, xem HD-11)
streamlit run src/app/main.py

# Chạy test (13 test cho src/auth/, chạy trên SQLite in-memory — không đụng MySQL "lacco" thật, xem HD-13)
pytest tests/ -v --cov=src/auth --cov-report=term-missing

# Lint + format (chạy trước khi commit — CI ở .github/workflows/ci.yml sẽ chạy lại "ruff check", xem HD-14)
ruff check src/ tests/ scripts/
ruff format src/ tests/ scripts/

# Migration (đã chạy thật lên MySQL "lacco", bước 2.3)
alembic upgrade head

# Sinh dữ liệu mẫu synthetic cho 18 bảng theo ERD (bước 2.4)
python scripts/generate_synthetic_sample_data.py

# Demo import + validate Pandera vào MySQL "lacco", gồm cả ca lỗi cố ý (bước 2.4)
python scripts/run_synthetic_import_demo.py
```

## 6. RBAC & bảo mật — BẮT BUỘC, không thương lượng

- **3 cấp quyền:** Admin (quản trị hệ thống) / Manager (chỉnh sửa, cập nhật dữ liệu và xem báo cáo) / User (chỉ xem báo cáo). **Admin luôn xem toàn bộ dữ liệu (`unrestricted=True`), không giới hạn theo Khối/Phòng dù có gắn `employee_id` hay không** — quyết định chốt tại bước 3.1 (25/08/2026), xem HD-11. Phạm vi Khối/Phòng/A-B-C bên dưới chỉ áp dụng cho Manager/User.
- **Phân quyền theo Khối/Phòng và loại khách hàng A/B/C** — KH loại A do Giám đốc Khối quản lý, loại B do Trưởng phòng, loại C do nhân viên kinh doanh. **Tiêu chí xếp loại A/B/C đã "Đã rõ" (17/08/2026):** dùng nguyên trường **"Phân loại"** đã có sẵn trong hệ thống FT — không tự định nghĩa lại ngưỡng xếp hạng, chỉ đọc giá trị có sẵn. Đã có thể code phần lọc/RBAC theo A/B/C dựa trên trường này.
- **Rủi ro bảo mật nghiêm trọng nhất của dự án** (đã ghi trong Kế hoạch triển khai, mục 7): Streamlit chia sẻ state ở cấp module giữa các phiên người dùng. Nếu `cache_data`/`cache_resource` không gắn tham số theo user, dữ liệu tài chính của user A có thể lộ sang user B.
  - **Quy tắc bắt buộc:** mọi `@st.cache_data` / `@st.cache_resource` PHẢI nhận tham số gắn với `user_id` hoặc `role`.
  - **Cấm tuyệt đối:** biến global chứa dữ liệu nghiệp vụ (số liệu tài chính, danh sách khách hàng...).
  - Đây là checklist bắt buộc của `qa-reviewer-agent` trước mọi lần merge — không merge nếu vi phạm quy tắc này.
- Mật khẩu: bcrypt. Mọi phiên đăng nhập ghi vào `LoginHistory`, mọi thay đổi dữ liệu ghi vào `AuditLog`.
- **Dữ liệu tài chính/công nợ thật KHÔNG được đưa vào Claude Chat (bản public)** — chỉ xử lý trong Claude Code chạy local/server nội bộ khi thật sự cần thiết. Dữ liệu dùng cho demo/case study giảng dạy phải là dữ liệu đã ẩn danh hoá.

## 7. Danh sách báo cáo bắt buộc — trạng thái yêu cầu

Nguyên tắc: chỉ code phần logic khi trạng thái là **Đã rõ**; phần "Cần làm rõ" chỉ dựng khung UI/schema, không hardcode công thức đoán mò.

Chi tiết đầy đủ (bảng 14 dòng, trạng thái Đã rõ/Cần làm rõ, ghi chú công thức) đã tách sang `.claude/rules/trang-thai-yeu-cau.md` — **tự động nạp khi làm việc trong `src/services/`, `src/db/`, hoặc `docs/requirements/`**, không tải khi làm việc ở chỗ khác (auth, deploy, UI...) để tiết kiệm ngữ cảnh. Sau đợt phỏng vấn 17/08/2026: 12/14 dòng "Đã rõ" — chỉ còn **CRM** và **Dòng tiền** ở trạng thái "Cần làm rõ", cả hai đã chốt dời sang Giai đoạn 2 (không phải "chưa phỏng vấn" mà là "ngoài phạm vi Giai đoạn 1") — không code logic, không cần dựng cả UI/schema cho 2 phần này ở Giai đoạn 1.

**2 quyết định công thức đã chốt tại bước 4.1/4.3 (Tuần 4), áp dụng cho MỌI module tính doanh thu/lãi lỗ/xu hướng theo thời gian, không chỉ báo cáo Kinh doanh:**
- **Đơn `sales_order.status = "Huỷ"` LOẠI TRỪ khỏi mọi tổng doanh thu/lãi lỗ** (COO xác nhận 07/09/2026) — vẫn có thể hiển thị riêng số lượng/giá trị đơn Huỷ để theo dõi tỷ lệ huỷ đơn, nhưng không cộng vào tổng chính. Các giá trị `status` khác (Mới tạo/Đang xử lý/Đang vận chuyển/Đã giao) vẫn CHƯA được Trưởng phòng Vận hành xác nhận đầy đủ (xem `docs/architecture/erd-tuan-02.md` mục 1) — không tự suy diễn cách xử lý cho các giá trị này, tiếp tục hỏi nếu phát sinh.
- **Nhóm theo Tuần trong biểu đồ xu hướng dùng ISO week** (MySQL `%x-%v`, tuần bắt đầu Thứ Hai) — COO xác nhận 07/09/2026 không cần đổi theo quy ước AMIS/FT riêng.

**3 quyết định công thức/RBAC mới chốt tại bước 5.1 (Tuần 5, 09/09/2026), khi xây 4 module Đơn hàng/Pricing/Chi phí/Công nợ:**
- **Công nợ — nhóm tuổi nợ (aging bucket) tính ĐỘNG tại thời điểm xem** (0-30/31-60/61-90/>90 ngày, hàm thuần `compute_aging_bucket(due_date, as_of_date)`, không lưu thành cột vật lý trong DB) — COO xác nhận, chọn phương án khuyến nghị. Áp dụng cho mọi báo cáo Công nợ, nhất quán với nguyên tắc tách lớp mục 2.
- **Chi phí "Theo Khối" — Manager chỉ xem Khối của mình, User bị ẨN HẲN tab này** (không phải hiện rồi báo lỗi) — vì bảng `cost`/`budget` không có dữ liệu cấp nhân viên. Quyết định UI ẩn/hiện dựa trực tiếp vào `scope.unrestricted`/`scope.division_id` TRƯỚC khi gọi service, không dựa vào bắt exception.
- **Chi phí "Theo Nhóm nhân sự" — CHỈ Admin xem được** — bảng `personnel_cost` không có bất kỳ khoá ngoại nào tới nhân viên/phòng/khối để phân quyền thấp hơn. `_require_admin()` raise `PermissionError` chỉ là lớp phòng vệ thứ 2; quyết định ẩn/hiện tab thật vẫn phải kiểm tra `scope.unrestricted` ở tầng UI.

**3 mẫu lọc RBAC mới (bổ sung cho mẫu `scope.customer_ids` gốc), dùng khi module không có "khách hàng" làm chủ thể phân quyền tự nhiên** — xem code mẫu tại `src/services/report_pricing.py`, `report_chi_phi.py`, `report_cong_no.py`:
1. Lọc theo `Employee.department_id`/`employee_id` (khi bảng không có customer_id ý nghĩa, ví dụ Pricing).
2. Lọc theo `scope.division_id` kèm ẩn hẳn tab theo role (Chi phí "Theo Khối").
3. Lọc trực tiếp trên cột `division_id`/`department_id`/`employee_id` sẵn có của chính bảng (Công nợ) — ưu tiên cách này khi bảng đã có sẵn cột, không suy luận qua UNION nhiều bảng như `scope.customer_ids`.

**Ngưỡng hiệu năng đã chốt tại bước 6.2 (Tuần 6, 11/09/2026, xem HD-19):** Kế hoạch triển khai mục 8 chỉ ghi tiêu chí định tính "chịu tải 20 người dùng đồng thời không lỗi" — COO xác nhận bổ sung ngưỡng định lượng để có cơ sở đo: **p95 (95th percentile thời gian phản hồi) < 3 giây/hàm, tỷ lệ lỗi/timeout = 0%, không có lỗi pool connection timeout**. Áp dụng cho bước kiểm thử cuối (7.1) và mọi lần đo tải tương tự sau này — không cần hỏi lại COO riêng cho ngưỡng này. Kết quả đo thực tế ở bước 6.2 (481–488 lượt gọi/60 giây tuỳ lần đo, 0 lỗi, p95 tối đa 0.011s) đạt dư khá xa ngưỡng — nhưng dữ liệu đo là dữ liệu mẫu quy mô nhỏ, cần đo lại khi có khối lượng gần thực tế hơn trước go-live.

## 8. Hướng dẫn khi Compact

Khi chạy `/compact` (kể cả không kèm chỉ dẫn thủ công), luôn ưu tiên giữ lại:

- **Danh sách file đã sửa/tạo** trong phiên hiện tại (đường dẫn cụ thể, không chỉ tên chung chung).
- **Quyết định kiến trúc hoặc kỹ thuật đã chốt**, kèm lý do — không chỉ kết luận, phải giữ cả "vì sao chọn cách này, không chọn cách khác".
- **Việc còn dang dở / TODO chưa hoàn thành**, ghi rõ đang ở bước nào, còn thiếu gì mới coi là xong.
- **Bước đang thực hiện trong roadmap** (mã bước, ví dụ 1.5, 2.1...) — đối chiếu với `Lich_trinh_thuc_hien_8_tuan_LACCO.xlsx`.
- **Lệnh/câu prompt vừa dùng thành công** nếu là một pattern nên tái sử dụng (ví dụ prompt scaffold, prompt review trước commit).

Nếu nội dung sắp bị tóm tắt liên quan đến quyết định RBAC, bảo mật, hoặc công thức nghiệp vụ đã "Đã rõ" — giữ nguyên văn, không diễn giải lại, vì sai lệch ở đây ảnh hưởng trực tiếp đến logic sẽ code sau này.

## 9. Lịch sử phiên bản

- **v1 (13/08/2026):** Bản đầu tiên, soạn sau bước 1.4 (scaffold). Dựa trên yêu cầu đã "Đã rõ" của nhóm Kinh doanh (5/14). Phần RBAC A/B/C và Chi phí/Công nợ/Dòng tiền còn khung, chưa có công thức.
- **v1.1 (13/08/2026):** Bổ sung mục 9 — Hướng dẫn khi Compact. Lý do: chạy `/compact` không kèm chỉ dẫn thủ công, rủi ro mất chi tiết context giữa các phiên làm việc dài.
- **v1.2 (13/08/2026):** Tách bảng trạng thái 14 dòng yêu cầu (trước là mục 7+8) sang `.claude/rules/trang-thai-yeu-cau.md`, dùng cơ chế path-scoped rules của Claude Code — nội dung thay đổi thường xuyên, không nên nằm trong file "luật chơi" chính. CLAUDE.md giảm còn 9 mục, ~100 dòng.
- **v2 (17/08/2026):** Cập nhật sau khi hoàn thành bước 1.3 (phỏng vấn thu thập yêu cầu). Kết quả: 12/14 dòng yêu cầu "Đã rõ" (tăng từ 5/14), gồm cả tiêu chí xếp loại KH A/B/C (mục 6 — dùng trường "Phân loại" có sẵn trong FT, đã có thể code RBAC A/B/C) và nguồn khách hàng. Chỉ còn 2/14 "Cần làm rõ" — **CRM** và **Dòng tiền** — cả hai đã chốt dời sang Giai đoạn 2 (ngoài phạm vi, không phải chờ trả lời thêm). Bảng chi tiết đã đồng bộ tại `.claude/rules/trang-thai-yeu-cau.md`.
- **v3 (22/08/2026):** Cập nhật sau khi hoàn thành Tuần 2 (schema, migration, import — 5/5 bước). ERD 18 bảng đã thiết kế và gần chốt xong (8/10 mục "cần xác nhận" còn mở, không mục nào chặn tiến độ — chi tiết `docs/architecture/erd-tuan-02.md`), SQLAlchemy models + Alembic migration đã chạy thật lên MySQL "lacco", pipeline import Pandera đã test cả đường thành công lẫn đường lỗi cố ý. 3 thay đổi trong bản này: (1) sửa mục 1 — còn 5/6 nhóm báo cáo trong phạm vi Giai đoạn 1 (Dòng tiền dời Giai đoạn 2), bản v1/v2 liệt kê nhầm 6 nhóm mâu thuẫn với ghi chú đầu file; (2) thêm lưu ý vận hành ở mục 2 về giới hạn không gọi được subagent tuỳ biến theo tên qua Task tool trong harness hiện tại (xem HD-07); (3) cập nhật mục 5 với các lệnh migration/sinh dữ liệu/import thật đã dùng ở Tuần 2, thay placeholder cũ.
- **v4 (25/08/2026):** Cập nhật sau bước 3.1 (Auth & RBAC) và 3.2 (qa-reviewer-agent). 2 thay đổi: (1) mục 5 — lệnh `streamlit run src/app/main.py` không còn là placeholder, đã có code thật (đăng nhập bcrypt + hiển thị phạm vi RBAC) từ bước 3.1; lệnh `pytest` vẫn placeholder, chờ bước 3.3; (2) mục 6 — ghi rõ quyết định "Admin luôn xem toàn bộ dữ liệu, không giới hạn theo Khối/Phòng" đã chốt tại bước 3.1, tránh lặp lại tình huống agent phải tự đoán như lúc `auth-rbac-agent` mới code lần đầu.
- **v5 (03/09/2026):** Cập nhật sau bước 3.3 (test đầu tiên, HD-13). Mục 5 — lệnh `pytest` không còn placeholder: 13 test cho `src/auth/` (hashing, scope, authentication), coverage 78% toàn `src/auth/` (96% `scope.py`, 100% `hashing.py`, 76% `authentication.py` — phần thiếu là các hàm widget `streamlit_authenticator` không dùng trong luồng đăng nhập chính). Toàn bộ test chạy trên SQLite in-memory qua tham số `engine=` đã thiết kế sẵn từ bước 3.1, không kết nối MySQL "lacco" thật — chuẩn bị sẵn cho GitHub Actions CI ở bước 3.4.
- **v6 (03/09/2026, chốt Tuần 3):** Phát hiện khi chạy quy trình "chốt tuần" mới (`lacco-week-closeout`) — bước 3.4 (Ruff + CI) đã hoàn thành và commit code thật từ trước, nhưng CLAUDE.md chưa được cập nhật để phản ánh việc này (thiếu sót do bước 3.4 không tự động kèm sửa CLAUDE.md). 4 thay đổi: (1) mục 2 — thêm `.github/workflows/` vào cây thư mục; (2) mục 3 — thêm dòng "Lint/Format | Ruff | Tuần 3 (bước 3.4)" vào bảng tech stack bổ sung; (3) mục 4 — thêm nguyên tắc PEP8/import-order được Ruff kiểm tra tự động, chạy trước khi commit; (4) mục 5 — thêm lệnh `ruff check`/`ruff format`. Bài học: khi thêm 1 công cụ/tầng hạ tầng mới (không phải code nghiệp vụ), vẫn cần tự hỏi "CLAUDE.md có cần cập nhật không" ngay trong lúc làm, không chỉ chờ đến lúc chốt tuần mới phát hiện.
- **v7 (07/09/2026, chốt Tuần 4):** Phát hiện khi chạy `lacco-week-closeout` cho Tuần 4 — 2 quyết định nghiệp vụ đã chốt với COO ở bước 4.1/4.3 (loại trừ đơn Huỷ, giữ ISO week) chưa được ghi vào CLAUDE.md, chỉ nằm trong nhật ký/commit message — rủi ro agent Tuần 5 (xây Đơn hàng/Pricing/Chi phí/Công nợ, có thể cũng tính tổng liên quan `sales_order`) phải tự suy luận lại hoặc hỏi lại COO câu đã trả lời. 4 thay đổi: (1) mục 2 — thêm `src/app/pages/` vào cây thư mục, thêm quy tắc bắt buộc chỉ định ranh giới file khi chạy nhiều instance cùng persona song song (HD-15); (2) mục 7 — thêm 2 quyết định công thức đã chốt (loại trừ Huỷ khỏi doanh thu/lãi lỗ toàn dự án, ISO week cho nhóm theo tuần), áp dụng mọi module tính doanh thu/lãi lỗ chứ không chỉ Kinh doanh; (3) đồng bộ `.claude/rules/trang-thai-yeu-cau.md` (dòng "Kinh doanh") và `.claude/agents/report-builder-agent.md` (mục "không tự loại trừ dữ liệu") qua CLI — 2 file này bị chặn ghi qua device bridge. Bài học: quyết định nghiệp vụ chốt qua `AskUserQuestion` trong lúc code cần được ghi ngay vào CLAUDE.md/persona, không đợi đến lúc chốt tuần mới rà soát — nếu không, chính agent đã tạo ra quyết định đó ở tuần này cũng không "nhớ" được cho tuần sau.
- **v8 (09/09/2026, chốt Tuần 5):** Phát hiện khi chạy `lacco-week-closeout` cho Tuần 5 — 3 quyết định công thức/RBAC mới chốt với COO ở bước 5.1 (aging động cho Công nợ, ẩn tab Chi phí "Theo Khối" cho User, Chi phí "Theo Nhóm" chỉ Admin) và 3 mẫu lọc RBAC mới (employee/department-scoped, division-scoped kèm ẩn tab, lọc cột trực tiếp) chưa được ghi vào CLAUDE.md hay persona — cùng dạng rủi ro đã gặp ở chốt Tuần 4 (v7), lặp lại đúng 1 tuần sau dù đã có bài học trước đó. 3 thay đổi: (1) mục 2 — ghi nhận quy mô song song mới (4 module/2 đợt x 2, bước 5.1) và persona mới `doc-writer-agent` (bước 5.2, đồng bộ SDD.md/README.md); (2) mục 7 — thêm 3 quyết định công thức/RBAC bước 5.1 và 3 mẫu lọc RBAC mới, áp dụng cho mọi module tương tự sau này; (3) đồng bộ `.claude/rules/trang-thai-yeu-cau.md` (dòng "Công nợ", thêm mục quy ước bổ sung Tuần 5) và `.claude/agents/report-builder-agent.md` (thêm 3 quyết định + 3 mẫu lọc) qua CLI — 2 file này vẫn bị chặn ghi qua device bridge. Bài học: việc "ghi quyết định vào CLAUDE.md ngay khi COO chốt qua AskUserQuestion, không đợi chốt tuần" (bài học đã rút ra ở v7) CHƯA thực sự trở thành thói quen tự động trong lúc code bước 5.1 — cần coi bước này là 1 checklist item bắt buộc ngay trong prompt giao việc cho `report-builder-agent`, không chỉ là "bài học" nằm im trong changelog.
- **v9 (11/09/2026, chốt Tuần 6):** Cập nhật sau khi hoàn thành Tuần 6 (bước 6.1 xuất Excel/PDF — HD-18, bước 6.2 test tải — HD-19). 3 thay đổi: (1) mục 2 — thêm nguyên tắc graceful fallback cho tính năng phụ thuộc hạ tầng không ổn định trên mọi môi trường, rút ra từ sự cố `kaleido`/Chrome headless treo ở bước 6.1; (2) mục 3 — cập nhật bảng tech stack: chốt ReportLab (không phải WeasyPrint) cho Export PDF và openpyxl cho Export Excel, thêm dòng `kaleido` kèm rủi ro môi trường Windows Server chưa xác nhận (mang sang bước 7.2); (3) mục 7 — thêm ngưỡng hiệu năng định lượng đã chốt với COO ở bước 6.2 (p95<3 giây/hàm, 0% lỗi), bổ sung cho tiêu chí định tính sẵn có ở Kế hoạch triển khai mục 8. **Không sửa** `.claude/rules/trang-thai-yeu-cau.md` hay `.claude/agents/report-builder-agent.md` tuần này — rà soát cho thấy Tuần 6 không phát sinh quyết định công thức/RBAC báo cáo mới (2 việc chính thuộc hạ tầng export/kiểm thử, không phải xây module báo cáo) và không có dòng "Cần làm rõ" nào chuyển trạng thái. Bài học: không phải tuần nào cũng cần đồng bộ cả 3 file luật (CLAUDE.md + 2 file `.claude/`) như Tuần 4/5 — điều quan trọng là tự hỏi đúng câu "quyết định tuần này thuộc phạm vi file nào", thay vì mặc định sửa cả 3 hoặc mặc định không sửa file nào.
