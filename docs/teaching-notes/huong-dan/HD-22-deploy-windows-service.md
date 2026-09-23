# HD-22: Deploy Streamlit trên Windows Server (chạy như Windows Service)

**Tuần:** 7 — Kiểm thử & triển khai | **Đối tượng phù hợp:** IT/BA | **Ngày thực hiện:** 23/09/2026

## Mục tiêu

Đưa LACCO Dashboard từ "chạy tay trên máy dev" sang chạy thật như một dịch vụ nền cho người dùng trong mạng nội bộ. Cụ thể, app phải: tự khởi động khi bật máy mà không cần ai đăng nhập Windows, tự phục hồi khi bị crash hoặc bị kill, và truy cập được từ các máy khác trong LAN qua một địa chỉ cố định. Bước này cũng là lần đầu kiểm tra các rủi ro môi trường đã ghi nhận từ trước (kaleido/Chrome headless ở HD-18, ngưỡng hiệu năng ở HD-19) trên chính máy chạy production.

## Giải thích khái niệm

- **Windows Service (dịch vụ nền):** chương trình do Windows tự chạy lúc khởi động, dưới một tài khoản hệ thống, không phụ thuộc việc có người đăng nhập hay không. Streamlit không tự đăng ký được thành Windows Service, nên cần một công cụ "bọc" bên ngoài. Hai lựa chọn phổ biến là **NSSM** (công cụ ngoài, phải tải về) và **Task Scheduler** (có sẵn trong Windows, cấu hình để chạy lúc khởi động máy dưới tài khoản `SYSTEM`).
- **Static IP và dải DHCP:** router tự cấp IP cho các máy trong mạng từ một dải (DHCP range). Máy chủ cần IP cố định để người dùng luôn gõ đúng một địa chỉ. Nếu đặt IP cố định nằm *trong* dải DHCP, router có thể cấp trùng IP đó cho máy khác, gây xung đột mạng. Vì vậy IP cố định phải nằm *ngoài* dải DHCP.
- **Bind `0.0.0.0`:** Streamlit lắng nghe trên mọi card mạng của máy, không gắn với một IP cụ thể. Nhờ vậy khi đổi IP máy, app không cần sửa code hay khởi động lại.

## Cách tiếp cận / Quy trình đã dùng

**Quyết định của COO trước khi làm (qua `AskUserQuestion`):**

- Máy đích: dùng chính máy Windows 11 hiện tại (kết nối Wi-Fi) làm máy chủ, thay vì chờ một Windows Server riêng. Máy này vì vậy vừa là máy dev vừa là máy production, dùng chung MySQL local. Việc chuyển sang máy khác để sau.
- Cách cố định IP: đặt static IP trực tiếp trên máy Windows (không đặt DHCP reservation trên router).

**Một prompt CLI thực hiện tuần tự:**

| Hạng mục | Cách làm |
|---|---|
| Static IP | Kiểm tra IP thật bằng `ipconfig` trước, tắt DHCP trên card Wi-Fi, gán IP cố định bằng PowerShell `New-NetIPAddress` + `Set-DnsClientServerAddress` (DNS 192.168.1.1, 8.8.8.8) |
| Firewall | `New-NetFirewallRule` mở cổng TCP 8501 chiều vào, theo cổng, không giới hạn IP |
| Chống ngủ | `powercfg /change standby-timeout-ac 0` và `hibernate-timeout-ac 0` |
| `.env` production | `APP_ENVIRONMENT=production`, `AUTH_COOKIE_KEY` sinh mới bằng `secrets.token_hex(32)`, app dùng tài khoản `lacco_app` (không dùng root). CLI tự sinh secret, không in ra báo cáo |
| Chạy nền | Chọn **Task Scheduler** thay vì NSSM để không thêm công cụ ngoài không có trong repo. `scripts/deploy/install_service.ps1` đăng ký task "LACCO Dashboard": trigger *At startup* trễ 1 phút (chờ MySQL và mạng lên), tài khoản `SYSTEM`, `MultipleInstances IgnoreNew`. Script chạy lại nhiều lần vẫn an toàn |
| Tự phục hồi | `scripts/deploy/run_app.cmd` chạy Streamlit trong vòng lặp: Streamlit thoát thì ghi log, chờ 10 giây rồi chạy lại. Log ghi ra `logs\streamlit.log` (không commit) |
| MySQL | `Set-Service MySQL80 -StartupType Automatic` (trước đó đang ở chế độ Manual) |
| Kiểm tra | Kill-test, reboot test thật, xuất PDF có chart, load test lặp lại kịch bản HD-19 |

## Bảng lỗi và tình huống thật đã gặp

| # | Tình huống | Nguyên nhân | Cách phát hiện / xử lý |
|---|---|---|---|
| 1 | COO báo IP máy là `192.168.1.177`, thực tế là `.117` | Nhớ nhầm số, IP do DHCP cấp | CLI kiểm tra `ipconfig` trước khi cấu hình. Luôn đọc thông số thật từ máy, không cấu hình theo số người dùng nhớ |
| 2 | "Restart on failure" của Task Scheduler không chạy lại app khi process bị kill | Task Scheduler chỉ coi task "thất bại" trong một số trường hợp; process bị kill thì task chỉ về trạng thái Ready, không tự chạy lại dù đã đặt `RestartCount 999` | Phát hiện bằng kill-test thật. Sửa ở tầng kiến trúc: đưa vòng lặp tự restart vào ngay `run_app.cmd`. Kill-test lần 2: app tự lên lại sau khoảng 25 giây |
| 3 | Reboot test báo FAIL theo `schtasks`: Last Result `0x800710E0`, Last Run Time không phải lúc boot, dù app thật ra đã chạy đúng | Task còn sót một trigger lặp 5 phút (ban đầu thêm làm "watchdog" dự phòng). Mỗi lần trigger này kích hoạt trong lúc app đang chạy, Windows từ chối chạy thêm bản thứ hai (`IgnoreNew`) và **ghi đè** Last Result/Last Run Time | Chứng minh app chạy đúng bằng 3 nguồn độc lập: cây tiến trình (cha là Task Scheduler, user `SYSTEM`), mốc thời gian trong `logs\streamlit.log` (74 giây sau khi máy lên, khớp độ trễ 1 phút), và health check. COO đồng ý xoá trigger lặp, chỉ giữ *At startup* (commit `7b024c5`) |
| 4 | Xuất PDF có chart bị treo trên máy thật, sinh 3 tiến trình kaleido mồ côi | Đúng rủi ro đã ghi nhận ở HD-18: kaleido không khởi động được Chrome headless ổn định trên máy này | Graceful fallback hoạt động đúng thiết kế: sau 20 giây timeout vẫn tạo PDF hợp lệ (77 KB, có bảng, không có chart). COO quyết định chấp nhận fallback, hoãn việc nâng kaleido 1.x. Các tiến trình mồ côi tự mất sau reboot |
| 5 | MySQL80 không tự chạy sau khi khởi động lại máy | Service MySQL80 đang ở chế độ Manual | Đổi sang Automatic ngay trong `install_service.ps1`, xác nhận bằng `sc qc MySQL80` |
| 6 | Lần commit đầu của bản sửa trigger thất bại, không có gì được commit | PowerShell 5.1 tách message commit tại dấu ngoặc kép trong nội dung | CLI ghi message ra file rồi commit bằng `git commit -F <file>`. Với commit message dài, có dấu tiếng Việt hoặc dấu ngoặc, nên dùng cách này ngay từ đầu trên Windows PowerShell |
| 7 | Đổi IP `.117` → `.248`: `New-NetIPAddress -DefaultGateway` báo lỗi "DefaultGateway already exists" | `Remove-NetIPAddress` chỉ gỡ IP, không gỡ route default gateway đi kèm. Prompt do Cowork soạn thiếu bước này | CLI tự phát hiện, gỡ gateway cũ trước rồi mới gán IP mới, có sẵn bước khôi phục về `.117` nếu lỗi, và báo lại rõ chỗ làm khác đề bài. Ping `.248` trước khi đổi để chắc IP đang trống |
| 8 | `.env` production không tạo mới hoàn toàn như đề bài | Máy vừa dev vừa prod, CLI không có mật khẩu `lacco_app`/`lacco_migrate` để tạo lại | CLI giữ phần MySQL và Sentry của `.env` cũ, chỉ sinh mới `AUTH_COOKIE_KEY` và đặt `APP_ENVIRONMENT=production`, báo lại rõ độ lệch. Hệ quả: Sentry dùng chung DSN cho dev và prod, event chỉ phân biệt được qua tag `environment` (chưa kiểm tra trên sentry.io) |

## Kết quả thu được

- **Địa chỉ truy cập:** `http://192.168.1.248:8501`. IP ban đầu là `.117`; COO chủ động đổi sang `.248` sau khi kiểm tra dải DHCP trên router. IP cũ đã ngừng phản hồi. Rà soát toàn repo không có file nào hardcode IP, nên việc đổi IP không cần commit.
- **Chạy nền:** commit `da9f7ca` (thêm `scripts/deploy/run_app.cmd`, `scripts/deploy/install_service.ps1`, mục "Deploy" trong `README.md`), commit `7b024c5` (bỏ trigger lặp 5 phút). CI xanh cả hai commit.
- **Kill-test:** app tự phục hồi sau khoảng 25 giây.
- **Reboot test:** máy lên lúc 22:15:40, Streamlit khởi động lúc 22:16:54 dưới tài khoản `SYSTEM`, health check trả `ok`.
- **Load test** (dữ liệu mẫu nhỏ, cùng kịch bản HD-19): 485 lượt gọi/60 giây, 0 lỗi, p95 tối đa 12 ms, đạt ngưỡng p95 < 3 giây. Kết quả tương đương bước 6.2 (481–488 lượt).
- **Firewall:** rule TCP 8501 áp dụng mọi profile mạng, không giới hạn IP. **Chống ngủ:** đã tắt standby/hibernate khi cắm điện.
- **Hoãn theo quyết định của COO (không chặn go-live):**
  - PDF có chart: tạm chấp nhận PDF không chart.
  - Load test với khối lượng dữ liệu lớn hơn: chờ COO có ước tính số đơn hàng và khách hàng sau 1–2 năm. Script `generate_synthetic_sample_data.py` cũng cần thêm tham số số lượng.

## Ghi chú khi chuyển sang máy chủ khác sau này

Code không cần sửa vì app bind `0.0.0.0` và không có IP hardcode. Việc cần làm lại trên máy mới:

1. Clone repo, tạo `.venv`, `pip install -r requirements.txt`.
2. Tạo `.env` production mới.
3. Chạy `install_service.ps1` bằng quyền Administrator.
4. Mở firewall cổng 8501.
5. Đặt static IP ngoài dải DHCP.

Điểm cần lưu ý nhất là MySQL. Hai tài khoản `lacco_app`/`lacco_migrate` hiện chỉ cho phép kết nối từ `@localhost`.

- Nếu MySQL chuyển cùng app sang máy mới: tạo lại hai tài khoản trên máy mới và backup/restore dữ liệu (xem bước 7.3).
- Nếu tách app và DB ra hai máy: phải tạo tài khoản với host là IP của máy app thay vì `@localhost`, và chỉ mở cổng 3306 cho đúng IP đó.

## Bài học rút ra

- **"Có sẵn tính năng" không có nghĩa là "tính năng hoạt động".** Task Scheduler có cài đặt "restart on failure" nhưng thực tế không chạy lại process bị kill. Cách duy nhất để biết là cố ý làm hỏng (kill process) rồi quan sát. Mọi cơ chế tự phục hồi đều phải được kiểm tra bằng cách phá thật trước go-live.
- **Công cụ chẩn đoán cũng có thể báo sai. Cần ít nhất 2 nguồn bằng chứng độc lập trước khi kết luận.** `schtasks` báo FAIL trong khi app chạy hoàn toàn đúng. Log ứng dụng, cây tiến trình và health check cùng chỉ về một kết luận thì mới đáng tin.
- **"Lưới an toàn" thêm vào khi không cần có thể gây hại.** Trigger watchdog 5 phút không bổ sung khả năng phục hồi nào (vòng lặp trong `run_app.cmd` đã làm việc đó), nhưng lại làm hỏng khả năng chẩn đoán. Thiết kế vận hành nên tối giản: mỗi cơ chế giải quyết đúng một việc.
- **Rủi ro ghi nhận sớm và có fallback thì không chặn go-live khi thành sự thật.** Lỗi kaleido đã được cảnh báo từ HD-18 và đã có sẵn fallback, nên khi xảy ra trên máy thật chỉ còn là một quyết định nghiệp vụ (chấp nhận PDF không chart) do COO đưa ra, không phải sự cố kỹ thuật.
- **Prompt do Cowork soạn có thể sai chi tiết lệnh hệ điều hành.** Lỗi gateway (#7) và lỗi dấu ngoặc của PowerShell (#6) đều do CLI chạy thật trên máy phát hiện. Phân vai hợp lý là: Cowork soạn ý đồ và tiêu chí kiểm tra; CLI được quyền tự điều chỉnh lệnh cho đúng môi trường, nhưng bắt buộc báo lại mọi chỗ làm khác đề bài.
- **Máy vừa dev vừa prod là một rủi ro vận hành cần nhớ.** App production chạy trực tiếp từ thư mục repo. Code đang sửa dở trong working copy, hoặc một lần `git checkout` sang nhánh khác, có thể được Streamlit nạp vào phiên production ở lần tương tác kế tiếp. Đây cũng chính là cơ chế reload module gây lỗi pickle ở HD-21. Khi có máy chủ riêng nên tách dev và prod.

## Kết quả

Bước 7.2 hoàn thành ngày 23/09/2026. LACCO Dashboard chạy như dịch vụ nền tại `http://192.168.1.248:8501`: tự khởi động khi bật máy dưới tài khoản `SYSTEM`, tự phục hồi sau khoảng 25 giây khi bị kill, MySQL tự khởi động, và load test đạt ngưỡng. Quá trình làm phát hiện và xử lý 2 lỗi vận hành thật của Task Scheduler (restart on failure không hoạt động; trigger lặp ghi đè kết quả chẩn đoán). Hai hạng mục được COO quyết định hoãn, không chặn go-live: PDF có chart và load test với khối lượng dữ liệu lớn.
