# HD-11: Thiết kế RBAC 3 cấp với Claude Code

**Tuần:** 3 — Auth, RBAC & bảo mật | **Đối tượng phù hợp:** Cả hai | **Ngày thực hiện:** 25/08/2026

## Mục tiêu

Xây module đăng nhập (bcrypt qua `streamlit-authenticator`) và middleware tính phạm vi dữ liệu theo RBAC 3 cấp (Admin/Manager/User) kết hợp phân cấp Khối/Phòng và phân loại khách hàng A/B/C — đúng theo CLAUDE.md mục 6, xác minh bằng đăng nhập thật (cả đường thành công lẫn thất bại) trên database "lacco".

## Quy trình đã dùng

1. Kiểm tra trạng thái mật khẩu MySQL trước khi bắt đầu — vì bước này chạm trực tiếp vào bcrypt/session, cần môi trường DB sạch. Phát hiện quan trọng: xem bên dưới.
2. Giao việc cho agent general-purpose mang persona `auth-rbac-agent.md` (đúng quy ước "general-purpose + dán nguyên văn persona" đã chốt từ HD-07, nay đã ghi thẳng vào CLAUDE.md mục 2).
3. Tạo `requirements.txt` bằng `pip freeze` từ môi trường thật đang chạy (việc tồn đọng từ bước 2.3, làm luôn ở đây vì sắp thêm dependency mới `streamlit-authenticator`).
4. Xây 3 file trong `src/auth/` (`hashing.py`, `authentication.py`, `scope.py`) + `admin_actions.py`, cộng `src/services/auth_service.py` (truy vấn DB) và `src/app/main.py` (trang Streamlit demo tối thiểu) — tuân thủ tách lớp CLAUDE.md mục 2.
5. Tạo 3 tài khoản test (Admin/Manager/User) bằng cách đặt lại mật khẩu bcrypt thật cho 3 dòng trong 21 user synthetic đã có từ bước 2.4, thay vì tạo mới — không commit mật khẩu test vào git, chỉ báo cáo lại trong kết quả trả về (khác với mật khẩu MySQL thật, đây là tài khoản demo trong DB dev/test, không phải secret production).
6. Tự (Claude Code, không qua agent con) đăng nhập thử cả 3 tài khoản — 1 lần đúng, 1 lần cố ý sai mật khẩu — và query trực tiếp `login_history` để xác nhận, thay vì chỉ tin log của agent.

## Phát hiện bảo mật quan trọng — mật khẩu MySQL chưa từng được đổi

Khi kiểm tra trước khi bắt đầu (bước A.2), phát hiện `password_last_changed` của `root@localhost` là **21/05/2025** — cũ hơn cả thời điểm bị lộ trong chat ở bước 2.3 (tháng 8/2026). Nghĩa là khuyến nghị đổi mật khẩu đưa ra từ HD-09 chưa từng được thực hiện. Đồng thời `.env` vẫn dùng thẳng tài khoản `root` (chưa tạo user least-privilege riêng, một việc tồn đọng khác từ Tuần 1).

**Cách phát hiện đáng chú ý:** không chỉ hỏi "đã đổi chưa", mà tự truy vấn `password_last_changed` trong `mysql.user` để có bằng chứng thời gian cụ thể — đúng nguyên tắc "xác minh bằng hành động thật" đã áp dụng xuyên suốt dự án, áp dụng cả cho câu hỏi có vẻ chỉ cần trả lời có/không.

Sau khi báo cáo, COO đã đổi mật khẩu root ngay trong phiên. Cập nhật `.env` + cấu hình MCP theo mật khẩu mới, xác minh lại bằng kết nối thật qua `src/services/db_connection.py` (query `SELECT` thành công) — không chỉ tin trạng thái "Connected". Lưu ý: không xác minh được qua chính công cụ MCP trong cùng phiên CLI vì tool MCP chưa được nạp vào bộ công cụ của phiên đó — đây là giới hạn kỹ thuật của phiên, không phải lỗi cấu hình; đường xác minh qua `db_connection.py` vẫn là bằng chứng độc lập đủ tin cậy.

## Quyết định kiến trúc & lý do

- **Phạm vi Admin — quyết định nghiệp vụ cần COO xác nhận, không tự đoán:** agent code ban đầu cho Admin có gắn `employee_id` vẫn bị giới hạn xem theo Khối (giống Giám đốc Khối), Admin không gắn `employee_id` mới xem toàn bộ. Đây là suy luận hợp lý về mặt kỹ thuật nhưng mâu thuẫn với định nghĩa gốc ở CLAUDE.md mục 6 (Admin = "quản trị hệ thống", một vai trò tách biệt khỏi phân cấp Khối/Phòng nghiệp vụ mà Manager mới đại diện). Agent đã liệt kê đúng thành mục "cần xác nhận" thay vì tự quyết. **COO xác nhận (25/08/2026): Admin luôn xem toàn bộ dữ liệu, không giới hạn theo Khối/Phòng dù có gắn `employee_id` hay không.** Đã sửa `src/auth/scope.py` theo đúng quyết định này, xác minh lại bằng `compute_data_scope()` chạy thật (Admin: 3 → 30 khách hàng, tức toàn bộ hệ thống).
- **Phạm vi Manager/User suy luận từ UNION nhiều bảng** (`sales_order`, `debt`, `price_request`) vì `customer` không có cột chủ sở hữu trực tiếp — quyết định kỹ thuật hợp lý, chấp nhận, nhưng agent tự nêu rủi ro: nếu 1 khách hàng có đơn hàng và công nợ gắn 2 nhân viên khác nhau, KH đó sẽ lọt vào phạm vi của cả hai. Chưa cần xử lý ngay (chưa có báo cáo thật dùng đến), ghi nhận làm rủi ro cần theo dõi khi xây module báo cáo.
- **`streamlit-authenticator` đảm nhiệm cả hash bcrypt lẫn form đăng nhập** — đúng theo CLAUDE.md mục 3 đã chốt, không tự viết lại logic hash.
- **`@st.cache_data` cho hàm tính phạm vi dữ liệu bắt buộc nhận `user_id` + `role_value` làm tham số** — đúng quy tắc bảo mật nghiêm trọng nhất dự án (CLAUDE.md mục 6), đã tự kiểm tra lại code xác nhận không có biến global chứa dữ liệu nghiệp vụ.
- **`requirements.txt` sinh từ `pip freeze` môi trường thật** thay vì tự đoán version — tránh lặp lại lỗi "tin thông tin tra cứu chưa kiểm chứng" đã từng gặp ở HD-06 (sai tên biến môi trường MCP).

## Kết quả thu được

Commit `10b2a01` (requirements.txt), `510f72b` (module Auth & RBAC, 7 file mới — 943 dòng: `hashing.py` 49, `authentication.py` 213, `scope.py` 202, `admin_actions.py` 71, `auth_service.py` 259, `main.py` 121, cộng `.claude/agents/auth-rbac-agent.md`), `662892a` (sửa phạm vi Admin theo quyết định COO).

Xác minh thật (tự Claude Code chạy, không chỉ tin agent):

| Kiểm tra | Kết quả |
|---|---|
| Đăng nhập đúng mật khẩu (cả 3 role) | `success=True`, đúng role từng tài khoản |
| Đăng nhập sai mật khẩu (Admin) | `success=False`, `reason='wrong_password'` |
| `login_history` | Ghi đủ cả lượt thành công lẫn thất bại, có IP, timestamp |
| `compute_data_scope()` — trước khi sửa Admin | Admin: giới hạn theo Khối (n=3) — sai theo định nghĩa gốc |
| `compute_data_scope()` — sau khi sửa Admin | Admin: `unrestricted=True`, n=30 (toàn bộ); Manager/User không đổi |
| `audit_log` (đặt lại mật khẩu test) | Chỉ ghi "password_hash_updated", không lộ hash/plaintext |
| Kết nối MySQL với mật khẩu mới | Query `SELECT` thật qua `db_connection.py` thành công |
| Mật khẩu/secret lọt vào git | Không — đã grep toàn bộ diff của cả 3 commit |

## Bài học rút ra

- **Câu hỏi tưởng chỉ cần trả lời có/không ("đã đổi mật khẩu chưa") vẫn nên xác minh bằng dữ liệu thật** (`password_last_changed`) thay vì chỉ hỏi — phát hiện ra khuyến nghị từ HD-09 đã bị bỏ sót suốt 3 ngày, nếu không xác minh sẽ tiếp tục code trên nền DB có rủi ro bảo mật thật.
- **Để agent tự liệt kê "cần xác nhận" thay vì tự quyết tiếp tục chứng minh giá trị** — trường hợp phạm vi Admin là ví dụ rõ nhất: agent đưa ra 2 lựa chọn hợp lý về mặt kỹ thuật, nhưng chỉ COO mới biết lựa chọn nào đúng ý nghĩa "Admin" mà CLAUDE.md đã định nghĩa.
- **Giới hạn môi trường có thể thay đổi giữa các phiên** — công cụ MCP không nạp được trong phiên CLI lần này dù đã hoạt động ở Tuần 1/2; luôn có đường xác minh dự phòng (ở đây là kết nối trực tiếp qua `db_connection.py`) thay vì phụ thuộc vào 1 kênh duy nhất.
- **Tài khoản test/demo trong DB dev không cần xử lý nghiêm ngặt như secret production** — mật khẩu 3 tài khoản test được báo cáo thẳng trong chat là chấp nhận được (khác hẳn sự cố mật khẩu MySQL thật ở bước 2.3), miễn là không commit vào git và không phải dữ liệu/quyền truy cập thật.

## Kết quả

Module Auth & RBAC hoạt động thật trên database "lacco": đăng nhập bcrypt qua `streamlit-authenticator`, phạm vi dữ liệu đúng theo role (Admin toàn bộ, Manager theo Phòng, User theo cá nhân phụ trách), `login_history`/`audit_log` ghi đầy đủ. Mật khẩu MySQL root đã được đổi trong tuần này (sau khi phát hiện chưa từng đổi từ sự cố Tuần 2). Còn 1 việc tồn đọng từ Tuần 1 chưa xử lý: tạo user MySQL least-privilege thay cho `root`.
