# Nhật ký Tuần 7 — Kiểm thử & triển khai

**Thời gian dự kiến:** 07/09 – 13/09/2026 | **Thời gian hoàn thành thực tế:** 22/09 – 20/10/2026 | **Trạng thái:** 4/4 bước hoàn thành

## 1. Tổng quan

Tuần 7 gồm 4 bước: test suite toàn diện + rà soát bảo mật lần cuối (7.1, HD-21), deploy thật lên Windows Server (7.2, HD-22), backup/restore MySQL định kỳ (7.3, HD-23), và nhật ký tuần này (7.4). Cả 4 bước đã hoàn thành, nhưng kéo dài hơn lịch dự kiến đáng kể (gần 6 tuần thay vì 1 tuần) — chủ yếu do khoảng cách xa giữa các lượt làm việc (phiên làm việc trải dài nhiều tuần lịch thật, có lúc hit giới hạn sử dụng phải chờ reset) chứ không phải do vướng mắc kỹ thuật kéo dài liên tục. Đúng tinh thần đã ghi nhận từ các tuần trước: "ngày là mốc linh hoạt, không phải deadline cứng".

Đây là tuần có khối lượng và mật độ phát hiện thật cao nhất tính đến nay: mở rộng test suite từ 13 lên 175 test (0% → 88% coverage toàn `src/`), xử lý dứt điểm 2 lỗ hổng bảo mật đã biết từ trước (cookie key hardcode công khai, tài khoản MySQL `root` dùng chung cho app và migration), lần đầu deploy thật lên máy sản xuất với Windows Service tự phục hồi, và lần đầu có vòng backup/restore MySQL hoàn chỉnh đã kiểm chứng. Tuần này cũng là tuần đầu tiên gặp liên tiếp nhiều sự cố **ngoài tầm kiểm soát trực tiếp của dự án** — Task Scheduler "restart on failure" không hoạt động như tài liệu Windows mô tả, một trigger thừa làm sai lệch kết quả chẩn đoán, và một sự cố hạ tầng thật của GitHub Actions — tất cả đều được xử lý đúng bằng cách xác minh bằng bằng chứng cụ thể trước khi hành động, không phỏng đoán.

Tiến độ tổng dự án sau tuần này: **33/38 bước (86,8%)** — theo sheet "3-Tien do tong quan" của tracker.

## 2. Đối chiếu tiêu chí nghiệm thu MVP Giai đoạn 1 (Kế hoạch triển khai mục 8)

7 tiêu chí nghiệm thu cuối Giai đoạn 1 (8 tuần), không phải tiêu chí phải đạt từng tuần — dưới đây chỉ liệt kê phần Tuần 7 đã đóng góp, không phải toàn bộ đã "xong":

| # | Tiêu chí (nguyên văn Kế hoạch triển khai) | Tuần 7 đóng góp gì |
|---|---|---|
| 1 | Tất cả 6 nhóm báo cáo hoạt động | Không thuộc phạm vi Tuần 7 (đã xong ở Tuần 4/5) |
| 2 | RBAC 3 cấp hoạt động đúng | Không thuộc phạm vi trực tiếp, nhưng bước 7.1 (Fix B) củng cố thêm lớp bảo mật quyền truy cập dữ liệu ở tầng hạ tầng (tách quyền MySQL) |
| 3 | Audit log và login history ghi nhận đầy đủ | Không thuộc phạm vi Tuần 7 (đã xong ở Tuần 3) |
| 4 | Xuất được Excel/PDF cho mọi báo cáo | Không phải việc mới, nhưng **lần đầu xác nhận thật trên máy production ở bước 7.2**: rủi ro `kaleido` đã cảnh báo từ Tuần 6 xảy ra thật (treo, timeout), graceful fallback hoạt động đúng như thiết kế — PDF vẫn xuất được, chỉ thiếu chart |
| 5 | Chịu tải 20 người dùng đồng thời không lỗi | Không phải việc mới, nhưng **đo lại trên máy production ở bước 7.2**: 485 lượt gọi/60 giây, 0 lỗi, p95 tối đa 12 ms — đạt ngưỡng, tương đương kết quả Tuần 6. Đo trên dữ liệu mẫu quy mô nhỏ, khối lượng lớn hơn còn hoãn (chờ COO cung cấp ước tính thật) |
| 6 | **Có backup/restore đã test thử** | **Đạt ở bước 7.3** — `mysqldump` qua tài khoản least-privilege, lưu 2 nơi, test restore thật khớp tuyệt đối 19/19 bảng |
| 7 | Có bộ tài liệu case study sẵn sàng làm bài giảng mẫu | Tuần 7 đóng góp 3 file HD (HD-21/22/23) + nhật ký này — đều có bảng lỗi thật với số lượng tình huống nhiều nhất từ trước đến nay |

Ngoài 7 tiêu chí trên, bước 7.1 còn đạt một mốc không có trong danh sách gốc nhưng quan trọng cho go-live: **test suite tự động mở rộng từ 13 lên 175 test, 0% → 88% coverage toàn `src/`**, cùng 1 vòng review bảo mật độc lập (`qa-reviewer-agent`, 9/9 Pass trên 32 file).

## 3. Bảng chi tiết các bước trong tuần

| Bước | Tên bước | Trạng thái | Ngày hoàn thành | Mã HD |
|---|---|---|---|---|
| 7.1 | Test suite & security review cuối | Hoàn thành | 22/09/2026 | HD-21 |
| 7.2 | Deploy Windows Server | Hoàn thành | 23/09/2026 | HD-22 |
| 7.3 | Backup/restore | Hoàn thành | 20/10/2026 | HD-23 |
| 7.4 | Review & nhật ký Tuần 7 | Hoàn thành | 20/10/2026 | (nhật ký này) |

## 4. Quyết định kiến trúc & lý do

**Quyết định của COO (nghiệp vụ/hạ tầng, qua `AskUserQuestion`):**
- **Áp dụng Fix B ngay** (tách quyền MySQL least-privilege) thay vì hoãn, và **giữ bước 7.1 "Đang làm"** cho đến khi Fix B xong — không đóng bước non dù phần test suite đã đạt.
- **Sửa bug cache (pickle) ngay trong 1 prompt riêng**, tách khỏi commit Fix B — giữ lịch sử commit rõ ràng theo từng mục đích.
- **Deploy trên chính máy Windows 11 hiện tại** (máy vừa dev vừa production) thay vì chờ có máy chủ riêng — chấp nhận đánh đổi để không trễ tiến độ, việc tách máy để sau.
- **Đặt static IP trực tiếp trên máy Windows** (không dùng DHCP reservation trên router) cho bước 7.2.
- **Chấp nhận fallback PDF không chart**, hoãn nâng cấp `kaleido` 1.x — vì fallback đã hoạt động đúng, không chặn go-live.
- **Làm reboot test ngay** thay vì để sau, và **hoãn load test khối lượng lớn** vì chưa có ước tính đơn hàng/khách hàng thật.
- **Xoá trigger watchdog 5 phút thừa** sau khi hiểu rõ nó đang làm sai lệch chẩn đoán `schtasks` mà không tăng thêm khả năng phục hồi thật (vòng lặp trong `run_app.cmd` đã đảm nhận việc đó).
- **Đổi IP `.117` → `.248`** để chắc chắn nằm ngoài dải DHCP router, sau khi tự kiểm tra router.
- **Backup lưu ở OneDrive, tần suất hằng tuần** (không phải hằng ngày) cho bước 7.3.
- **Sửa ngay 2 cảnh báo deprecation của CI** (action cũ, `ubuntu-latest` sắp đổi) thay vì để dồn thành nợ kỹ thuật.

**Quyết định kỹ thuật thuần (Claude/CLI tự quyết theo convention có sẵn, không cần hỏi COO):**
- Tài khoản MySQL `lacco_backup` dùng đúng mẫu least-privilege đã thiết lập ở Fix B (bước 7.1) — chỉ `SELECT, LOCK TABLES, SHOW VIEW, EVENT, TRIGGER`.
- Task Scheduler thay vì NSSM để chạy Streamlit như dịch vụ nền — tránh thêm phụ thuộc công cụ ngoài không có trong `requirements.txt`.
- Tự viết vòng lặp restart trong `run_app.cmd` thay vì dựa vào "restart on failure" của Task Scheduler — sau khi kill-test thật chứng minh tính năng đó không hoạt động.
- Dùng `mysqldump --result-file` thay vì redirect `>` của PowerShell (tránh lỗi mã hoá UTF-16), và `--no-tablespaces` (tránh yêu cầu quyền `PROCESS` không cần thiết cho tài khoản least-privilege).
- Test restore vào database tạm `lacco_restore_test`, không đụng database `lacco` thật.
- Sửa `ci.yml` từ `--cov=src/auth` sang `--cov=src` — phát hiện đây là lỗi tồn đọng từ trước, CLAUDE.md từng sửa ở tài liệu tham khảo (v12) nhưng quên sửa file cấu hình thật.

## 5. Vấn đề gặp phải & cách Claude hỗ trợ giải quyết

| # | Bước | Vấn đề | Cách xử lý |
|---|---|---|---|
| 1 | 7.1 | SQLite (môi trường test) không chạy được `func.date_format()` — hàm chỉ MySQL hỗ trợ | Đăng ký hàm SQL tương đương ngay trong từng test qua `sqlite3.Connection.create_function`, không sửa code nghiệp vụ viết cho MySQL thật |
| 2 | 7.1 | `@st.cache_data` không pickle được khi trả về `DataScope` — chỉ xuất hiện khi test qua UI thật, không xuất hiện trong 175 test tự động | Phát hiện: file-watcher dev-mode của Streamlit reload module giữa chừng, tạo 2 class trùng tên khác identity. Sửa: hàm cache chỉ trả về kiểu builtin thuần, convert sang/từ dataclass ở ngoài |
| 3 | 7.1 | CLAUDE.md v12 bị chèn sai vị trí trong changelog (trước v11 thay vì sau) — lặp lại đúng lỗi đã từng mắc ở v9/v10 | CLI tự phát hiện khi review diff trước khi commit, báo lại thay vì tự sửa hay commit luôn — Cowork sửa lại đúng thứ tự |
| 4 | 7.2 | Nhầm IP máy là `.177`, thực tế là `.117` | CLI kiểm tra `ipconfig` thật trước khi cấu hình, không tin theo trí nhớ |
| 5 | 7.2 | Task Scheduler "restart on failure" không thực sự chạy lại app khi process bị kill, dù đã cấu hình `RestartCount 999` | Phát hiện bằng kill-test thật (không chỉ đọc tài liệu Windows). Xử lý: vòng lặp tự restart ngay trong `run_app.cmd` |
| 6 | 7.2 | Trigger lặp 5 phút làm `schtasks` báo "FAIL" (Last Result `0x800710E0`) dù app đã khởi động đúng lúc boot | Xác minh bằng 3 nguồn độc lập (log `streamlit.log`, cây tiến trình, health check) trước khi kết luận app chạy đúng; xoá trigger gây nhiễu |
| 7 | 7.2 | Đổi IP `.117→.248`: lệnh PowerShell thiếu bước gỡ default gateway cũ, gây lỗi | CLI tự phát hiện và sửa, có sẵn bước khôi phục nếu lỗi, báo lại rõ chỗ làm khác đề bài |
| 8 | 7.3 | Tạo tài khoản `lacco_backup` báo `Access denied` cho root | CLI đúng đắn **từ chối tự đọc mật khẩu root** từ cấu hình MCP — yêu cầu COO tự nhập. Khi vẫn lỗi, reset mật khẩu root theo đúng quy trình chuẩn, không in mật khẩu ra report |
| 9 | 7.3 | Vài tuần sau, tưởng root "lại hỏng" vì vẫn báo lỗi tương tự | Kiểm tra log trước khi reset lại — xác nhận lần reset trước vẫn còn hiệu lực, chỉ là dùng nhầm mật khẩu cũ. Tránh đổi mật khẩu một tài khoản đang hoạt động tốt |
| 10 | 7.3 | Sau khi push, CI kẹt `queued` hơn 10 phút | Loại trừ lần lượt: không hết quota (billing còn nguyên), không có run cũ bị treo, không có `concurrency` chặn — xác nhận đúng là sự cố `degraded_performance` thật của GitHub Actions qua githubstatus.com. Xử lý đúng: chờ, không huỷ/không push lại |
| 11 | 7.3 | Phát hiện phụ: `ci.yml` vẫn đo coverage `--cov=src/auth` dù CLAUDE.md đã sửa đúng ở tài liệu từ v12 — tồn đọng gần 1 tháng không ai biết | Sửa khớp lại `--cov=src`, đồng thời nâng cấp 2 action GitHub action lên bản mới |
| 12 | 7.4 | Khi viết xong entry changelog v14 (bước 7.3), còn sai 2 chi tiết nhỏ (đếm nhầm số thay đổi, diễn đạt dễ gây hiểu lầm thời điểm sự cố CI) | CLI đọc lại và phản biện trước khi commit tiếp — Cowork sửa ngay trong cùng ngày, không để sai sót nhỏ tồn đọng sang bước sau |

## 6. Prompt tiêu biểu đã dùng trong tuần

- **Prompt tự chứa hoàn toàn cho thao tác hệ điều hành thật** (static IP, Task Scheduler, reset mật khẩu root): luôn nhúng nguyên văn lệnh PowerShell cụ thể kèm bước xác minh rõ ràng ("test đăng nhập", "test health check"), không chỉ giao mục tiêu chung chung — vì CLI chạy trên máy Windows thật, không phải sandbox, mọi lệnh sai đều có hậu quả thật.
- **Yêu cầu loại trừ nguyên nhân bằng bằng chứng cụ thể trước khi hành động**, áp dụng nhất quán cho cả 3 lần chẩn đoán sự cố trong tuần (Task Scheduler, trigger thừa, GitHub Actions outage) — không đoán, không thử sửa ngẫu nhiên.
- **`AskUserQuestion` cho quyết định hạ tầng có đánh đổi rõ** (máy đích deploy, nơi lưu backup, tần suất backup, xử lý cảnh báo CI ngay hay để sau) — luôn kèm 1 phương án khuyến nghị và lý do, để COO quyết định nhanh mà vẫn hiểu đánh đổi.
- **Git commit message ghi ra file tạm, dùng `git commit -F <file>`** — áp dụng từ bước 7.2 sau khi phát hiện PowerShell 5.1 tách message tại dấu ngoặc kép, dùng lại nhất quán cho mọi commit sau đó trong tuần.

## 7. Ước tính thời gian tiết kiệm so với làm thủ công

Ước tính định tính (không phải số đo chính xác hay cam kết ROI chính thức): việc tự phát hiện Task Scheduler "restart on failure" không hoạt động thật — một hành vi khác với tài liệu Windows mô tả — bằng kill-test chủ động, thay vì phát hiện sau khi sự cố thật xảy ra ở production, là dạng rủi ro khó lượng hoá nhưng giá trị thực chất rất lớn. Tương tự, việc phân biệt đúng sự cố GitHub Actions ngoài tầm kiểm soát khỏi nghi ngờ "có thể do mình làm sai" giúp tránh nhiều giờ debug sai hướng (ví dụ thử sửa `ci.yml`, huỷ và tạo lại run nhiều lần) nếu không có quy trình loại trừ nguyên nhân rõ ràng.

## 8. Bài học rút ra cho tuần sau

- **Sửa một lỗi ở tài liệu không thay thế được việc rà lại cấu hình thật có cùng lỗi.** Lỗi `--cov=src/auth` trong `ci.yml` tồn tại thêm gần 1 tháng sau khi CLAUDE.md đã "sửa" nó ở tài liệu tham khảo — bài học lặp lại ở quy mô lớn hơn của việc đã từng gặp với file HD/tracker: một phát hiện chỉ thực sự được xử lý khi đã kiểm tra hết các nơi nó có thể còn tồn tại.
- **Trước khi lặp lại một thao tác có tính phá huỷ (đổi mật khẩu, xoá cấu hình, reset), luôn kiểm tra bằng chứng xem có thật sự cần làm lại không.** Việc tra log trước khi reset mật khẩu root lần 2 đã tránh được một thao tác không cần thiết, có thể làm hỏng các kết nối khác đang dùng đúng mật khẩu.
- **Khi gặp một sự cố có vẻ quen thuộc (ví dụ "chắc lại hết quota", "chắc lại gõ sai"), đừng dừng ở giả thuyết đầu tiên.** Cả 2 lần trong tuần (CI kẹt queued, root access denied lần 2) đều cần loại trừ bằng bằng chứng cụ thể trước khi tin, và cả 2 lần giả thuyết ban đầu "hiển nhiên" đều sai hoặc không đầy đủ.
- **Một phiên làm việc trải dài nhiều tuần lịch thật (ngắt quãng do hit giới hạn sử dụng, nghỉ giữa các lượt trao đổi) không làm mất ngữ cảnh** — nhưng mỗi lần quay lại sau một khoảng trống dài, nên chủ động xác minh lại trạng thái thật (`git log`, tracker) thay vì giả định mọi thứ còn y như lần cuối còn nhớ.

## 9. Việc cần làm tiếp

- **Tuần 8 (UAT & tổng kết case study):** chưa bắt đầu — 5 bước, chỉ tiến hành khi COO xác nhận.
- **Máy hiện tại vừa dev vừa production** — nên tách ra máy chủ riêng khi có điều kiện, trước khi UAT Tuần 8 có nhiều người dùng thật hơn truy cập.
- **2 hạng mục hoãn theo quyết định COO, chưa chặn go-live nhưng cần theo dõi:** nâng cấp `kaleido` để PDF có chart; load test khối lượng lớn (chờ COO cung cấp ước tính số đơn hàng/khách hàng thật để tham số hoá `generate_synthetic_sample_data.py`).
- **File lưu mật khẩu root mới** (`MySQL_root_moi_06102026.txt`, nằm ngoài repo) nên được COO chuyển vào trình quản lý mật khẩu rồi xoá — hiện vẫn ở dạng văn bản thuần.
- **Theo dõi lần chạy tự động đầu tiên của Scheduled Task backup** (Chủ Nhật tới) để xác nhận lịch hằng tuần hoạt động đúng trong điều kiện thật, không chỉ dựa vào lần chạy tay đã test.
