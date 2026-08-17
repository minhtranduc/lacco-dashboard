# CLAUDE.md — lacco-dashboard

> File context gốc repo, giúp Claude Code hiểu dự án ngay từ đầu mỗi phiên, không cần giải thích lại từ đầu.
> **Phiên bản:** v2 — 17/08/2026 | **Nguồn:** Tài liệu Kiến trúc Hệ thống, Kế hoạch triển khai Dashboard LACCO, Sheet 1 "Mẫu thu thập yêu cầu" (Bieu_mau_Yeu_cau_va_RACI_LACCO.xlsx — 12/14 dòng "Đã rõ", 2/14 chốt chuyển sang Giai đoạn 2). Bảng trạng thái yêu cầu chi tiết: xem `.claude/rules/trang-thai-yeu-cau.md`.
> Phỏng vấn thu thập yêu cầu (bước 1.3) đã hoàn thành 17/08/2026. Chỉ còn 2 báo cáo ngoài phạm vi Giai đoạn 1: **CRM** (chưa có dữ liệu trên hệ thống) và **Dòng tiền** (nguồn AMIS chưa xác nhận) — cả hai đã chốt dời sang Giai đoạn 2, không dựng logic/schema cho 2 phần này ở Giai đoạn 1.

## 1. Bối cảnh dự án

LACCO là công ty Logistics & Giao nhận vận tải. Dự án xây dựng WebApp Dashboard hỗ trợ ra quyết định, cung cấp báo cáo kinh doanh/chi phí/khách hàng/đơn hàng gần thời gian thực cho Ban Lãnh đạo, Trưởng phòng và nhân viên.

- **Phạm vi Giai đoạn 1 (hiện tại):** 6 nhóm báo cáo — Kinh doanh, Khách hàng, Pricing, Chi phí, Công nợ, Dòng tiền — cộng với tình trạng đơn hàng và tình trạng xuất hóa đơn.
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
│   ├── services/            # Business Logic layer — tính KPI, xử lý nghiệp vụ
│   ├── db/                  # Data layer — SQLAlchemy models, migrations (Alembic)
│   └── auth/                # RBAC, bcrypt, session
├── data/sample/              # dữ liệu mẫu ĐÃ ẨN DANH — không đưa dữ liệu thật vào đây
├── tests/
├── .claude/agents/           # định nghĩa subagent chuyên biệt
└── scripts/
```

Luồng dữ liệu: `Excel/CSV → Import → MySQL → SQLAlchemy → Pandas → Plotly → Streamlit → Browser`

Nguyên tắc bắt buộc: **không trộn lẫn 3 lớp** — code truy vấn DB không được nằm trong `src/app/`, logic tính KPI không được nằm trong `src/db/`. Việc này để đổi giao diện không ảnh hưởng logic nghiệp vụ, và ngược lại.

## 3. Tech stack

**Lõi (đã chốt trong Tài liệu Kiến trúc Hệ thống):** Python 3.12, Streamlit, MySQL 8.0, SQLAlchemy + mysql-connector-python, Pandas, Plotly, bcrypt.

**Bổ sung theo kế hoạch (không tự ý đổi sang thư viện khác ngoài danh sách này):**

| Nhóm | Công cụ | Thêm từ |
|---|---|---|
| Migration DB | Alembic | Tuần 2 |
| Validate dữ liệu import | Pandera | Tuần 2 |
| Testing | pytest + pytest-cov | Tuần 3 |
| CI/CD | GitHub Actions | Tuần 3–4 |
| Khung đăng nhập | streamlit-authenticator | Tuần 3 |
| Logging | Loguru | Ngay khi cần log |
| Config/biến môi trường | python-dotenv + Pydantic Settings | Ngay khi cần config |
| Giám sát lỗi | Sentry (free/self-host) | Trước go-live (Tuần 7) |
| Export Excel | XlsxWriter / openpyxl | Tuần 6 |
| Export PDF | WeasyPrint / ReportLab | Tuần 6 |

**Không đổi framework nền** (Streamlit, SQLAlchemy) trong Giai đoạn 1 — quyết định đã cân nhắc trong Kế hoạch triển khai, tránh phát sinh thời gian học kiến trúc mới giữa lộ trình 8 tuần.

## 4. Quy ước code

- Tuân thủ PEP8; docstring cho mọi function/class public.
- Đặt tên biến/hàm/class bằng tiếng Anh; label hiển thị UI và comment giải thích nghiệp vụ có thể dùng tiếng Việt.
- Dùng Loguru để log, không dùng `print()` cho việc theo dõi lỗi/luồng chạy.
- Xử lý lỗi bằng `except` cụ thể theo loại lỗi, không dùng bare `except:`; lỗi nghiệp vụ phải vừa log vừa hiển thị thông báo rõ ràng cho người dùng (không nuốt lỗi âm thầm).
- **Mọi truy vấn SQL bắt buộc qua SQLAlchemy (parameterized query)** — cấm nối chuỗi SQL thủ công dưới mọi hình thức, kể cả khi "chỉ để test nhanh".

## 5. Lệnh thường dùng

*(Cập nhật khi có lệnh thật — hiện tại là placeholder cho Tuần 2 trở đi)*

```bash
# Chạy app local
streamlit run src/app/main.py

# Chạy test
pytest --cov=src

# Migration
alembic upgrade head
```

## 6. RBAC & bảo mật — BẮT BUỘC, không thương lượng

- **3 cấp quyền:** Admin (quản trị hệ thống) / Manager (chỉnh sửa, cập nhật dữ liệu và xem báo cáo) / User (chỉ xem báo cáo).
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
