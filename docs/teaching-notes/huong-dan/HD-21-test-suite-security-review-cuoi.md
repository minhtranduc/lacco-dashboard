# HD-21: Test suite toàn diện & rà soát bảo mật lần cuối trước go-live

**Tuần:** 7 — Kiểm thử & triển khai | **Đối tượng phù hợp:** Cả hai | **Ngày thực hiện:** 22–23/09/2026

## Mục tiêu

Trước khi triển khai thật lên Windows Server (bước 7.2), dự án cần đạt 3 việc: (1) test suite tự động phủ đủ các module nghiệp vụ trước đó chưa có test (0% coverage), (2) xử lý dứt điểm 2 lỗ hổng bảo mật đã biết nhưng chưa sửa, (3) 1 vòng review bảo mật/chất lượng độc lập bởi `qa-reviewer-agent` trước khi coi là sẵn sàng go-live.

## Giải thích khái niệm

- **Coverage (độ phủ test):** tỷ lệ % dòng code được ít nhất 1 test chạy qua — đo bằng `pytest-cov`. Coverage cao KHÔNG đảm bảo logic đúng, chỉ đảm bảo có test chạm tới dòng code đó; vẫn cần đọc lại nội dung test để biết test có thật sự kiểm tra đúng hành vi mong muốn hay không.
- **Least-privilege (đặc quyền tối thiểu):** nguyên tắc bảo mật — mỗi tài khoản/tiến trình chỉ được cấp đúng quyền cần thiết cho đúng công việc của nó, không hơn. Áp dụng ở Fix B bên dưới: tách 1 tài khoản MySQL `root` (toàn quyền, có `GRANT OPTION`) đang dùng chung cho 2 việc khác nhau (app runtime + migration) thành 2 tài khoản riêng, mỗi tài khoản chỉ có đúng quyền việc đó cần.

## Cách tiếp cận / Quy trình đã dùng

COO chọn phương án "gộp làm 1 lần" (qua `AskUserQuestion`) thay vì tách 3 CLI prompt riêng cho test/fix/review — 1 prompt CLI duy nhất thực hiện tuần tự cả 3 phase:

| Phase | Nội dung | Cách làm |
|---|---|---|
| 1 — Test suite | Viết test cho 12 file trước đó 0% coverage (`src/services/*`, `src/auth/admin_actions.py`) | 2 đợt × 6 file/đợt, chạy song song nhiều subagent cùng persona (theo mẫu HD-15), mỗi subagent được giao rõ ranh giới file — không để tự suy luận |
| 2 — Fix A | Bỏ cookie key hardcode public trên GitHub (`_DEV_FALLBACK_COOKIE_KEY`) | Đổi `_cookie_key()` sang logic 3 nhánh: đọc `AUTH_COOKIE_KEY` từ `.env` nếu có → bắt buộc phải có nếu `APP_ENVIRONMENT=production` (raise `RuntimeError` nếu thiếu, không cho app khởi động) → sinh ngẫu nhiên 1 lần/process kèm cảnh báo log nếu môi trường khác |
| 2 — Fix B | Tách quyền MySQL — `root` (có `GRANT OPTION` trên `*.*`) đang dùng chung cho cả app runtime lẫn Alembic migration qua cùng 1 biến `.env` | Điều tra bằng `SHOW GRANTS FOR CURRENT_USER()` trước, đề xuất SQL tách 2 user (`lacco_app`: SELECT/INSERT/UPDATE/DELETE; `lacco_migrate`: thêm CREATE/ALTER/DROP/INDEX/REFERENCES), **chờ COO xác nhận qua `AskUserQuestion` mới áp dụng lên DB thật** — không tự ý đổi hạ tầng production |
| 3 — Review | `qa-reviewer-agent` chạy checklist 9 mục (CLAUDE.md mục 2 & 6) trên 32 file | Dán nguyên văn persona `.claude/agents/qa-reviewer-agent.md` vào 1 agent "general-purpose" (giới hạn harness hiện tại không gọi được subagent theo tên, xem HD-07) |

Sau khi Fix B chạy xong, bước test xác nhận qua UI thật (`streamlit run`, không chỉ chạy pytest) phát hiện thêm 1 bug ngoài phạm vi ban đầu (dòng cuối bảng lỗi bên dưới) — xử lý trong 1 prompt CLI riêng, tách khỏi commit Fix B.

## Kết quả thu được

- **Test suite:** 175/175 pass, 88% coverage tổng `src/` (tăng từ 12 file 0% coverage) — commit `f04880c`.
- **Fix A** (cookie key): commit `40bbce0`.
- **Fix B** (tách quyền MySQL): 2 user mới `lacco_app`/`lacco_migrate`, xác nhận qua `SHOW GRANTS` + chạy thử `alembic current` + đăng nhập UI thật — commit `954775a`.
- **Bug phụ phát sinh** (cache Streamlit không pickle được `DataScope`): commit `be4b417`.
- **CLAUDE.md** cập nhật lên v11 ghi nhận toàn bộ bước 7.1 + 1 gotcha bảo mật mới (`@st.cache_data`/pickle) — commit `7d32d70`.
- **qa-reviewer-agent:** 9/9 Pass trên 32 file — không vi phạm mục nào trong 9 tiêu chí (không nối chuỗi SQL thủ công; cache luôn keyed theo `user_id`/`role`; không biến global chứa dữ liệu nghiệp vụ; không bare `except:`; mật khẩu chỉ bcrypt, không log plaintext; tách đúng 3 lớp; dùng Loguru không `print()`; không lộ secret/credential; docstring đầy đủ cho hàm/class public).
- CI xanh cho toàn bộ 5 commit trên (mỗi lần ~1 phút).

## Bài học rút ra

| Tình huống thật gặp | Nguyên nhân | Cách xử lý / Bài học |
|---|---|---|
| SQLite (test) không chạy được `func.date_format()` — hàm chỉ MySQL hỗ trợ, dùng trong các module báo cáo để nhóm theo ISO week | Test suite chạy trên SQLite in-memory (quy ước từ Tuần 3, HD-13), nhưng code nghiệp vụ viết cho MySQL thật | Đăng ký hàm SQL tương đương ngay trong từng test qua `sqlite3.Connection.create_function`, KHÔNG sửa code nghiệp vụ hay `conftest.py` — giữ nguyên tắc code production viết đúng cho MySQL thật, chỉ vá ở lớp test |
| `UnserializableReturnValueError` khi cache `DataScope` — chỉ xuất hiện khi test qua UI thật (`streamlit run`), KHÔNG xuất hiện trong 175 test tự động | `@st.cache_data` dùng `pickle` để lưu giá trị TRẢ VỀ (không chỉ hash tham số đầu vào); file-watcher dev-mode của Streamlit reload lại module giữa các lần rerun, tạo 2 class cùng tên nhưng khác identity — `pickle` từ chối | Bug này KHÔNG THỂ phát hiện bằng pytest (môi trường test không có file-watcher/rerun) — khẳng định lại giá trị của việc luôn test qua UI thật trước khi đóng 1 bước có đụng cache/`.env`, không chỉ tin vào test suite xanh. Cách sửa đúng: hàm `@st.cache_data` chỉ trả về kiểu builtin thuần, convert sang/từ dataclass thật ở bên ngoài |
| Hit giới hạn sử dụng (usage limit) ngay giữa lúc CLI đang sửa bug cache, phải chờ ~4 tiếng mới reset | Giới hạn gói dịch vụ đang dùng, không phải lỗi kỹ thuật | Vì cửa sổ terminal CLI vẫn mở nguyên trong lúc chờ, sau khi giới hạn reset chỉ cần gõ tiếp trong đúng cửa sổ đó — CLI tự nhớ toàn bộ ngữ cảnh phiên, KHÔNG cần chạy lại prompt từ đầu. Nếu lỡ đóng terminal, việc đầu tiên khi mở phiên mới nên là `git status`/`git diff` để biết chính xác đã làm tới đâu, tránh làm trùng hoặc bỏ sót |

## Kết quả

Bước 7.1 hoàn thành với 175/175 test pass (88% coverage), 2 lỗ hổng bảo mật đã biết được xử lý dứt điểm (cookie key hardcode công khai trên GitHub, tài khoản MySQL `root` dùng chung cho app + migration), 1 bug phụ phát sinh được phát hiện và sửa ngay trong lúc kiểm thử qua UI thật, và 1 vòng review độc lập bởi `qa-reviewer-agent` đạt 9/9 Pass trên 32 file — đủ điều kiện tiến hành triển khai thật lên Windows Server (bước 7.2).
