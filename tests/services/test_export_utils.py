"""Test `src/services/export_utils.py` — lớp tiện ích thuần xuất
Excel/PDF (Tuần 6, bước 6.1), theo CLAUDE.md mục 2: module này KHÔNG mở
kết nối DB, chỉ nhận `pd.DataFrame`/`plotly.graph_objects.Figure` đã tính
sẵn, nên test ở đây KHÔNG cần `db_engine`/`seeded_scope_data` của
`tests/conftest.py`.

Nguyên tắc "graceful fallback" (CLAUDE.md mục 2, Tuần 6 bước 6.1): kaleido
(render ảnh chart cho PDF qua Chrome headless) có thể treo/lỗi khó lường
trên máy Windows dev hiện tại — thiết kế của `build_pdf_report_bytes` vì
vậy KHÔNG BAO GIỜ để việc render ảnh thất bại làm hỏng toàn bộ PDF. 2 test
dưới đây (`test_build_pdf_report_bytes_without_figure_skips_kaleido_entirely`
và `test_build_pdf_report_bytes_falls_back_when_chart_render_fails`) xác
minh trực tiếp nguyên tắc này ở 2 tình huống khác nhau:

1. `fig=None` — code không hề bước vào nhánh gọi kaleido (đọc
   `build_pdf_report_bytes` cho thấy toàn bộ khối `if fig is not None:`
   bị bỏ qua) — nên test này KHÔNG cần mock gì cả.
2. `fig` có `.to_image()` ném lỗi — mô phỏng kaleido lỗi thật mà KHÔNG
   gọi kaleido/Chrome thật (tránh phụ thuộc chậm/có thể treo trong CI —
   theo đúng yêu cầu của nhiệm vụ: "không cần test kaleido thật — mock
   hoặc bỏ qua phần render ảnh, ghi rõ lý do trong docstring test"), dùng
   1 fake object đơn giản thay cho `plotly.graph_objects.Figure` thật.

`_render_figure_to_png_bytes` (hàm gọi kaleido thật qua thread có timeout)
KHÔNG được test trực tiếp ở đây với 1 Plotly Figure thật, vì lý do tương
tự — xem docstring của 2 test PDF ở trên.
"""

from __future__ import annotations

from io import BytesIO

import numpy as np
import pandas as pd
from openpyxl import load_workbook

from src.services.export_utils import (
    _MAX_PDF_ROWS,
    _excel_cell_value,
    build_pdf_report_bytes,
    dataframe_to_excel_bytes,
)


def _sample_df() -> pd.DataFrame:
    """DataFrame nhỏ, nhiều kiểu dữ liệu (str, NaN, numpy int64/float64) —
    dùng chung cho các test Excel/PDF."""
    return pd.DataFrame(
        {
            "Khách hàng": ["Khách A", "Khách B", "Khách C"],
            "Doanh thu": pd.array([1000, 2000, np.nan], dtype="Int64"),
            "Tỷ lệ": np.array([1.5, np.nan, 3.25], dtype="float64"),
        }
    )


class TestExcelCellValue:
    """Test hàm thuần `_excel_cell_value()` — chuyển 1 giá trị ô sang kiểu
    openpyxl ghi được."""

    def test_nan_becomes_none(self) -> None:
        """Giá trị NaN (float `nan` từ pandas) phải chuyển thành `None` —
        openpyxl ghi `None` thành ô trống thay vì chuỗi "nan"."""
        assert _excel_cell_value(float("nan")) is None

    def test_numpy_scalar_becomes_python_scalar(self) -> None:
        """numpy scalar (int64/float64) phải chuyển về kiểu Python gốc qua
        `.item()` — openpyxl không nhận trực tiếp 1 số kiểu numpy."""
        value = _excel_cell_value(np.int64(42))
        assert value == 42
        assert type(value) is int

    def test_plain_value_passes_through(self) -> None:
        """Giá trị thường (str) không phải NaN/numpy phải được giữ nguyên
        không đổi."""
        assert _excel_cell_value("Khách A") == "Khách A"


class TestDataframeToExcelBytes:
    """Test `dataframe_to_excel_bytes()` — đọc ngược lại nội dung .xlsx đã
    tạo bằng `openpyxl.load_workbook()` để xác minh dữ liệu đúng."""

    def test_without_title_header_is_row_1(self) -> None:
        """Không truyền `title` — header phải nằm ở dòng 1, dữ liệu (kể cả
        NaN và numpy scalar) phải đọc lại đúng giá trị."""
        df = _sample_df()

        result = dataframe_to_excel_bytes(df, sheet_name="BaoCao")

        workbook = load_workbook(BytesIO(result))
        sheet = workbook.active
        assert sheet.title == "BaoCao"
        assert [cell.value for cell in sheet[1]] == [
            "Khách hàng",
            "Doanh thu",
            "Tỷ lệ",
        ]
        # Dòng 2 (NV đầu tiên): Doanh thu=1000 (numpy/pandas Int64 -> int)
        assert sheet.cell(row=2, column=1).value == "Khách A"
        assert sheet.cell(row=2, column=2).value == 1000
        assert sheet.cell(row=2, column=3).value == 1.5
        # Dòng 3: Tỷ lệ là NaN -> ô trống (None)
        assert sheet.cell(row=3, column=3).value is None
        # Dòng 4: Doanh thu là NaN -> ô trống (None)
        assert sheet.cell(row=4, column=2).value is None

    def test_with_title_shifts_header_to_row_2(self) -> None:
        """Truyền `title` — dòng 1 phải chứa tiêu đề (in đậm, cỡ 13), header
        cột phải dời xuống dòng 2, dữ liệu dời xuống dòng 3 trở đi."""
        df = _sample_df()

        result = dataframe_to_excel_bytes(
            df, sheet_name="BaoCao", title="Báo cáo doanh thu"
        )

        workbook = load_workbook(BytesIO(result))
        sheet = workbook.active
        title_cell = sheet.cell(row=1, column=1)
        assert title_cell.value == "Báo cáo doanh thu"
        assert title_cell.font.bold is True
        assert title_cell.font.size == 13
        assert [cell.value for cell in sheet[2]] == [
            "Khách hàng",
            "Doanh thu",
            "Tỷ lệ",
        ]
        assert sheet.cell(row=3, column=1).value == "Khách A"

    def test_sheet_name_longer_than_31_chars_is_truncated(self) -> None:
        """Excel giới hạn tên sheet tối đa 31 ký tự — hàm phải tự cắt bớt
        thay vì để `openpyxl` ném lỗi khi ghi."""
        long_name = "A" * 50
        df = _sample_df()

        result = dataframe_to_excel_bytes(df, sheet_name=long_name)

        workbook = load_workbook(BytesIO(result))
        assert workbook.active.title == "A" * 31

    def test_header_font_is_bold(self) -> None:
        """Ô header cột phải in đậm để phân biệt với dữ liệu."""
        df = _sample_df()

        result = dataframe_to_excel_bytes(df)

        workbook = load_workbook(BytesIO(result))
        sheet = workbook.active
        assert sheet.cell(row=1, column=1).font.bold is True


class TestBuildPdfReportBytes:
    """Test `build_pdf_report_bytes()` — xác minh nguyên tắc graceful
    fallback (CLAUDE.md mục 2) và cắt bớt dòng khi vượt `_MAX_PDF_ROWS`.

    Không parse nội dung text bên trong PDF (nhị phân, cần thêm thư viện
    ngoài — theo yêu cầu nhiệm vụ không thêm dependency mới cho việc này)
    — chỉ xác minh trả về bytes PDF hợp lệ (bắt đầu bằng magic header
    `%PDF`) và không ném lỗi.
    """

    def test_without_figure_skips_kaleido_entirely(self) -> None:
        """`fig=None` — đây CHÍNH LÀ trường hợp "graceful fallback khi
        không có ảnh chart" theo nhiệm vụ: đọc code `build_pdf_report_bytes`
        cho thấy khi `fig is None`, khối `if fig is not None:` (nơi gọi
        `_render_figure_to_png_bytes` -> kaleido) hoàn toàn không được thực
        thi. Do đó test này không cần mock kaleido dưới bất kỳ hình thức
        nào — đường code không hề chạm tới nó."""
        df = _sample_df()

        result = build_pdf_report_bytes(
            df, None, title="Báo cáo doanh thu", subtitle="Tháng 9/2026"
        )

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result.startswith(b"%PDF")

    def test_falls_back_when_chart_render_fails(self) -> None:
        """`fig` có `.to_image()` ném lỗi (mô phỏng kaleido lỗi thật) — PDF
        vẫn phải được tạo hợp lệ (title + bảng số liệu), chỉ thay ảnh chart
        bằng đoạn ghi chú, đúng thiết kế graceful fallback ở CLAUDE.md mục 2
        (Tuần 6, bước 6.1: kaleido có thể treo/lỗi trên máy dev Windows,
        không được để 1 lần lỗi render làm hỏng cả PDF).

        Mock `to_image` ở đây (thay vì dùng `plotly.graph_objects.Figure`
        thật) để KHÔNG gọi kaleido/Chrome headless thật trong test — theo
        đúng yêu cầu nhiệm vụ: kaleido thật chậm và có thể treo vô thời hạn
        trên môi trường này (xem docstring đầu `export_utils.py`), không
        phù hợp chạy trong bộ test tự động/CI.
        """

        class _FakeFigureThatFailsToRender:
            """Fake tối giản thay cho `plotly.graph_objects.Figure` — chỉ
            cần có `.to_image()` ném lỗi, không cần bất kỳ hành vi Plotly
            thật nào khác."""

            def to_image(self, **_kwargs: object) -> bytes:
                raise RuntimeError("simulated kaleido failure")

        df = _sample_df()

        result = build_pdf_report_bytes(
            df, _FakeFigureThatFailsToRender(), title="Báo cáo doanh thu"
        )

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result.startswith(b"%PDF")

    def test_rows_beyond_max_are_truncated_without_error(self) -> None:
        """DataFrame > `_MAX_PDF_ROWS` (200) dòng — hàm phải tự cắt còn 200
        dòng đầu kèm ghi chú, không ném lỗi, vẫn trả về PDF hợp lệ. Không
        kiểm tra text ghi chú bên trong PDF nhị phân (không thêm thư viện
        đọc PDF chỉ để phục vụ 1 assertion) — chỉ xác minh không lỗi và có
        magic header PDF hợp lệ."""
        long_df = pd.DataFrame(
            {
                "STT": range(_MAX_PDF_ROWS + 50),
                "Khách hàng": [f"Khách {i}" for i in range(_MAX_PDF_ROWS + 50)],
            }
        )

        result = build_pdf_report_bytes(long_df, None, title="Báo cáo dài")

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result.startswith(b"%PDF")

    def test_empty_dataframe_still_produces_valid_pdf(self) -> None:
        """DataFrame rỗng (0 dòng, có cột) — vẫn phải tạo được PDF hợp lệ
        (chỉ có header bảng, không có dòng dữ liệu), không ném lỗi."""
        empty_df = pd.DataFrame(columns=["Khách hàng", "Doanh thu"])

        result = build_pdf_report_bytes(empty_df, None, title="Báo cáo rỗng")

        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result.startswith(b"%PDF")


# Ghi chú: `_register_vietnamese_font()` nhánh lỗi (RuntimeError khi không
# tìm thấy font TTF nào trong `_FONT_CANDIDATES`) KHÔNG có test riêng ở
# đây — trên máy dev Windows hiện tại, font `C:\Windows\Fonts\arial.ttf`/
# `arialbd.ttf` tồn tại thật nên nhánh lỗi không thể kích hoạt tự nhiên.
# Cách duy nhất để ép nhánh này chạy là monkeypatch biến global module-level
# `_font_registered`/`_FONT_CANDIDATES` — rủi ro rò rỉ trạng thái sang các
# test PDF khác trong cùng file/tiến trình pytest (biến global dùng chung,
# không reset tự động giữa các test). Theo hướng dẫn nhiệm vụ, bỏ qua nhánh
# này thay vì ép 1 cách chông chênh; nếu cần test sau này, nên tách hàm
# thành nhận `font_candidates`/`font_registered` qua tham số thay vì global
# để test dễ cô lập hơn.


def test_module_sanity_max_pdf_rows_constant_is_int() -> None:
    """Sanity check nhỏ: `_MAX_PDF_ROWS` phải là số nguyên dương — nếu hằng
    số này đổi kiểu/giá trị âm ở tương lai, test truncation phía trên sẽ
    sai lệch âm thầm mà không báo lỗi rõ ràng."""
    assert isinstance(_MAX_PDF_ROWS, int)
    assert _MAX_PDF_ROWS > 0
