"""Test `src/services/db_connection.py` — dựng connection string MySQL và
cache SQLAlchemy Engine (CLAUDE.md mục 2: module này thuộc `src/services/`,
mục 4: raise lỗi rõ ràng thay vì nuốt lỗi âm thầm).

ĐẢM BẢO AN TOÀN (bắt buộc đọc trước khi sửa file này): các test dưới đây
KHÔNG BAO GIỜ mở kết nối MySQL thật. `create_engine()` của SQLAlchemy tạo
Engine "lazy" — chỉ thực sự mở connection khi có `.connect()`/thực thi
query; các test ở đây chỉ gọi `get_engine()`/`build_mysql_url()` rồi kiểm
tra thuộc tính của object trả về (`Engine.url`), không bao giờ gọi
`.connect()`, `session.execute(...)`, hay bất kỳ thao tác nào kích hoạt kết
nối thật tới host MySQL "lacco". Toàn bộ biến môi trường MySQL đều được
monkeypatch bằng giá trị giả (host `db-test.invalid`...), và `load_dotenv`
được patch thành no-op để không phụ thuộc `.env` thật trên máy chạy test.
"""

from __future__ import annotations

from urllib.parse import quote_plus

import pytest
from sqlalchemy import Engine

import src.services.db_connection as db_connection
from src.services.db_connection import build_mysql_url, get_engine

_REQUIRED_ENV_VARS = (
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_DATABASE",
)


@pytest.fixture(autouse=True)
def _no_real_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch `load_dotenv` thành no-op cho mọi test trong file này.

    `load_dotenv()` mặc định không ghi đè biến môi trường đã có sẵn
    (`override=False`), nên về lý thuyết `monkeypatch.setenv(...)` gọi
    trước `build_mysql_url()` đã đủ để thắng `.env` thật — nhưng để hoàn
    toàn độc lập với `.env` trên máy chạy test (kể cả trường hợp hành vi
    thư viện thay đổi ở bản sau), patch thẳng `load_dotenv` thành hàm
    không làm gì trong module `db_connection`.
    """
    monkeypatch.setattr(db_connection, "load_dotenv", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _reset_engine_cache() -> None:
    """Đảm bảo cache `_engine` cấp module sạch trước và sau mỗi test.

    `get_engine()` dùng biến global `_engine` để cache Engine giữa các lần
    gọi (không phải dữ liệu nghiệp vụ — không vi phạm CLAUDE.md mục 6).
    Vì toàn bộ test trong 1 lần chạy `pytest` chia sẻ chung 1 process, nếu
    không reset, cache tạo ở file test này có thể rò rỉ sang test khác
    (hoặc ngược lại) và làm sai lệch assertion "cùng object"/"khác object"
    dưới đây.
    """
    db_connection._engine = None
    yield
    db_connection._engine = None


def _set_valid_env(
    monkeypatch: pytest.MonkeyPatch, *, password: str = "matkhau"
) -> None:
    """Set đủ 5 biến môi trường MySQL bắt buộc với giá trị test giả lập."""
    monkeypatch.setenv("MYSQL_USER", "test_user")
    monkeypatch.setenv("MYSQL_PASSWORD", password)
    monkeypatch.setenv("MYSQL_HOST", "db-test.invalid")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_DATABASE", "lacco_test")


def test_build_mysql_url_raises_when_all_vars_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thiếu toàn bộ 5 biến môi trường bắt buộc -> RuntimeError liệt kê đủ
    tên biến còn thiếu trong thông báo lỗi."""
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(RuntimeError) as exc_info:
        build_mysql_url()

    message = str(exc_info.value)
    for var in _REQUIRED_ENV_VARS:
        assert var in message


def test_build_mysql_url_raises_when_one_var_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thiếu đúng 1 biến bắt buộc (MYSQL_PASSWORD) -> RuntimeError chỉ nêu
    đúng tên biến thiếu, không báo nhầm các biến đã có."""
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("MYSQL_USER", "test_user")
    monkeypatch.setenv("MYSQL_HOST", "db-test.invalid")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_DATABASE", "lacco_test")

    with pytest.raises(RuntimeError) as exc_info:
        build_mysql_url()

    message = str(exc_info.value)
    assert "MYSQL_PASSWORD" in message
    assert "MYSQL_USER" not in message
    assert "MYSQL_HOST" not in message
    assert "MYSQL_PORT" not in message
    assert "MYSQL_DATABASE" not in message


def test_build_mysql_url_escapes_special_characters_in_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mật khẩu chứa ký tự đặc biệt (`@`, `/`, `#`) phải được escape bằng
    `quote_plus` trong URL trả về — giống mật khẩu MySQL thật hiện tại có
    chứa `@` (xem docstring module `db_connection.py`)."""
    raw_password = "p@ss/word#1"
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    _set_valid_env(monkeypatch, password=raw_password)

    url = build_mysql_url()

    expected_user = quote_plus("test_user")
    expected_password = quote_plus(raw_password)
    expected_url = (
        f"mysql+mysqlconnector://{expected_user}:{expected_password}"
        "@db-test.invalid:3306/lacco_test"
    )
    assert url == expected_url


def test_build_mysql_url_not_affected_by_real_dotenv_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dù `load_dotenv` bị patch thành no-op (fixture `_no_real_dotenv`),
    giá trị trả về vẫn phải đúng theo `monkeypatch.setenv` — xác nhận test
    hoàn toàn độc lập với `.env` thật có thể tồn tại trên máy chạy test,
    không phụ thuộc việc `.env` có/không có hay chứa giá trị gì."""
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    _set_valid_env(monkeypatch)

    url = build_mysql_url()

    assert "db-test.invalid" in url
    assert "lacco_test" in url


def test_get_engine_force_new_returns_engine_with_expected_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`get_engine(force_new=True)` trả về `sqlalchemy.Engine` thật, với
    `url` phản ánh đúng host/database đã cấu hình qua biến môi trường —
    KHÔNG gọi `.connect()` nên không kích hoạt kết nối MySQL thật."""
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    _set_valid_env(monkeypatch)

    engine = get_engine(force_new=True)

    assert isinstance(engine, Engine)
    rendered = engine.url.render_as_string(hide_password=False)
    assert "db-test.invalid" in rendered
    assert "lacco_test" in rendered
    assert engine.url.host == "db-test.invalid"
    assert engine.url.database == "lacco_test"


def test_get_engine_caches_same_instance_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gọi `get_engine()` (mặc định `force_new=False`) 2 lần liên tiếp
    phải trả về đúng cùng 1 object (cache module-level `_engine`) — fixture
    `_reset_engine_cache` đảm bảo cache được dọn sạch trước/sau test này để
    không rò rỉ sang các test khác chạy cùng process."""
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    _set_valid_env(monkeypatch)

    engine_1 = get_engine()
    engine_2 = get_engine()

    assert engine_1 is engine_2


def test_get_engine_force_new_bypasses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gọi `get_engine(force_new=True)` 2 lần liên tiếp phải trả về 2 object
    KHÁC nhau (bỏ qua cache), dù cấu hình môi trường không đổi."""
    for var in _REQUIRED_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    _set_valid_env(monkeypatch)

    engine_1 = get_engine(force_new=True)
    engine_2 = get_engine(force_new=True)

    assert engine_1 is not engine_2
