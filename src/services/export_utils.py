"""Xuất báo cáo Excel/PDF dùng chung cho 6 trang báo cáo (Tuần 6, bước 6.1).

Theo CLAUDE.md mục 2 (tách lớp): module này KHÔNG mở kết nối DB và KHÔNG
nhận `scope` — chỉ nhận `pd.DataFrame` / `plotly.graph_objects.Figure` ĐÃ
TÍNH SẴN (RBAC đã áp dụng ở service/trang gọi trước đó). Đây là lớp tiện ích
thuần (pure utility), không thuộc lớp Business Logic hay Data.

PDF dùng ReportLab với font TTF hỗ trợ dấu tiếng Việt đăng ký thủ công (xem
`_register_vietnamese_font`) — Helvetica mặc định của ReportLab KHÔNG có dấu
tiếng Việt. Ảnh chart nhúng vào PDF qua `fig.to_image(engine="kaleido")`,
bọc timeout thủ công (`_KALEIDO_TIMEOUT_SECONDS`) vì kaleido có thể treo vô
thời hạn khi môi trường thiếu Chrome khả dụng — đã gặp thật khi test module
này (xem báo cáo bước 6.1), không để 1 lần xuất PDF lỗi làm treo cả app.
Timeout dùng `threading.Thread(daemon=True)` thủ công thay vì
`ThreadPoolExecutor` — đã kiểm chứng thật: `ThreadPoolExecutor` đăng ký
`atexit` join TẤT CẢ thread con (không daemon) khi tiến trình Python thoát,
nên nếu kaleido treo, `shutdown(wait=False)` vẫn không cứu được, cả tiến
trình Streamlit sẽ treo theo khi restart/stop. Thread daemon không có vấn đề
này (bị bỏ qua khi tiến trình thoát), đánh đổi: tiến trình `kaleido.exe` con
có thể vẫn còn sống ngầm sau khi timeout — cần theo dõi ở môi trường thật.
"""

from __future__ import annotations

import threading
from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_MAX_PDF_ROWS = 200
_KALEIDO_TIMEOUT_SECONDS = 20

# Đường dẫn font TTF hỗ trợ dấu tiếng Việt, thử lần lượt tới khi tìm được 1
# cặp (regular, bold) tồn tại. DejaVuSans (Linux) đứng đầu theo yêu cầu gốc;
# Arial Windows là fallback dùng khi code chạy trên máy dev Windows hiện tại
# — Arial cũng là lựa chọn hợp lý cho đích deploy Windows Server ở bước 7.2
# (font hệ thống lõi, có sẵn trên mọi bản Windows Server có GUI, không cần
# cài thêm). Nếu deploy lên Windows Server bản Core/Nano (không có GUI đầy
# đủ) thì Arial có thể KHÔNG có sẵn — cần cài DejaVuSans thủ công lúc đó.
_FONT_CANDIDATES: list[tuple[str, str]] = [
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
]
_FONT_NAME = "LaccoPdfFont"
_FONT_NAME_BOLD = "LaccoPdfFont-Bold"
_font_registered = False


def _register_vietnamese_font() -> None:
    """Đăng ký font TTF hỗ trợ dấu tiếng Việt vào ReportLab (chỉ 1 lần).

    Raises:
        RuntimeError: nếu không tìm thấy cặp font (regular, bold) nào trong
            `_FONT_CANDIDATES` — dừng hẳn thay vì âm thầm dùng Helvetica
            (sẽ vỡ chữ/lỗi khi PDF chứa tiếng Việt có dấu).
    """
    global _font_registered
    if _font_registered:
        return

    for regular_path, bold_path in _FONT_CANDIDATES:
        if Path(regular_path).is_file() and Path(bold_path).is_file():
            pdfmetrics.registerFont(TTFont(_FONT_NAME, regular_path))
            pdfmetrics.registerFont(TTFont(_FONT_NAME_BOLD, bold_path))
            logger.info(
                "export_utils: đã đăng ký font PDF tiếng Việt từ '{}' / '{}'",
                regular_path,
                bold_path,
            )
            _font_registered = True
            return

    tried_paths = [c[0] for c in _FONT_CANDIDATES]
    raise RuntimeError(
        "Không tìm thấy font TTF hỗ trợ dấu tiếng Việt trên máy này (đã thử: "
        f"{tried_paths}). Không thể xuất PDF đúng dấu — cần cài 1 trong các "
        "font trên (ví dụ DejaVuSans) trước khi dùng tính năng Xuất PDF."
    )


def _excel_cell_value(value: Any) -> Any:
    """Chuyển giá trị 1 ô DataFrame sang kiểu openpyxl ghi được — NaN/NaT
    thành ô trống, kiểu numpy scalar (int64/float64...) về kiểu Python gốc
    qua `.item()` (openpyxl không nhận trực tiếp 1 số kiểu numpy)."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def dataframe_to_excel_bytes(
    df: pd.DataFrame, *, sheet_name: str = "Data", title: str | None = None
) -> bytes:
    """Ghi `df` ra nội dung file Excel (.xlsx) dạng bytes bằng openpyxl.

    Args:
        df: DataFrame đã tính sẵn (đã qua RBAC ở service gọi trước đó).
        sheet_name: tên sheet Excel — nên đặt ASCII ngắn gọn (giới hạn 31
            ký tự của Excel, hàm tự cắt nếu dài hơn).
        title: tiêu đề hiển thị ở dòng 1 (được phép tiếng Việt có dấu), bỏ
            qua dòng tiêu đề nếu `None`.

    Returns:
        Nội dung file .xlsx dạng bytes — dùng trực tiếp làm `data=` cho
        `st.download_button`.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name[:31]

    header_row = 1
    if title:
        title_cell = sheet.cell(row=1, column=1, value=title)
        title_cell.font = Font(bold=True, size=13)
        header_row = 2

    for col_idx, col_name in enumerate(df.columns, start=1):
        cell = sheet.cell(row=header_row, column=col_idx, value=str(col_name))
        cell.font = Font(bold=True)

    for row_offset, row in enumerate(df.itertuples(index=False), start=1):
        for col_idx, value in enumerate(row, start=1):
            sheet.cell(
                row=header_row + row_offset,
                column=col_idx,
                value=_excel_cell_value(value),
            )

    for col_idx, col_name in enumerate(df.columns, start=1):
        content_lengths = df.iloc[:, col_idx - 1].astype(str).map(len)
        max_len = max(len(str(col_name)), content_lengths.max() if len(df) else 0)
        sheet.column_dimensions[get_column_letter(col_idx)].width = min(max_len + 2, 60)

    buffer = BytesIO()
    workbook.save(buffer)
    logger.info(
        "export_utils.dataframe_to_excel_bytes: sheet='{}' rows={} cols={}",
        sheet_name,
        len(df),
        len(df.columns),
    )
    return buffer.getvalue()


def _render_figure_to_png_bytes(fig: Any) -> bytes:
    """Render `fig` Plotly sang PNG bytes qua kaleido, giới hạn thời gian
    chờ `_KALEIDO_TIMEOUT_SECONDS` giây bằng `threading.Thread(daemon=True)`
    thủ công (xem lý do KHÔNG dùng `ThreadPoolExecutor` ở docstring đầu
    file — treo tiến trình chính khi thoát nếu kaleido treo).

    Raises:
        TimeoutError: nếu kaleido không trả kết quả trong
            `_KALEIDO_TIMEOUT_SECONDS` giây.
        Exception: lỗi gốc từ `fig.to_image()` nếu kaleido trả lỗi (không
            phải treo) — ném lại nguyên bản qua thread chính.
    """
    result: dict[str, Any] = {}

    def _target() -> None:
        try:
            result["value"] = fig.to_image(format="png", scale=2, engine="kaleido")
        except Exception as exc:  # noqa: BLE001 - chuyển lỗi sang thread chính qua `result`
            result["error"] = exc

    worker = threading.Thread(target=_target, daemon=True)
    worker.start()
    worker.join(timeout=_KALEIDO_TIMEOUT_SECONDS)
    if worker.is_alive():
        raise TimeoutError(
            f"kaleido quá thời gian chờ ({_KALEIDO_TIMEOUT_SECONDS}s) khi render chart."
        )
    if "error" in result:
        raise result["error"]
    return result["value"]


def _format_cell_text(value: Any) -> str:
    """Định dạng 1 giá trị ô sang chuỗi hiển thị trong bảng PDF — không suy
    diễn định dạng nghiệp vụ riêng (tiền tệ/%...), chỉ làm gọn số thập phân
    và ô rỗng cho NaN/None."""
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def build_pdf_report_bytes(
    df: pd.DataFrame,
    fig: Any | None,
    *,
    title: str,
    subtitle: str | None = None,
) -> bytes:
    """Build nội dung PDF báo cáo (tiêu đề + ảnh chart Plotly + bảng dữ liệu)
    dạng bytes bằng ReportLab.

    Args:
        df: DataFrame đã tính sẵn (đã qua RBAC ở service gọi trước đó). Nếu
            có hơn `_MAX_PDF_ROWS` (200) dòng, chỉ đưa 200 dòng đầu vào PDF
            kèm ghi chú — PDF dài quá sẽ vỡ layout/chậm.
        fig: `plotly.graph_objects.Figure` đã vẽ sẵn, hoặc `None` nếu báo
            cáo không có chart tương ứng (không render ảnh trong trường hợp
            này, không phải lỗi).
        title: tiêu đề báo cáo (tiếng Việt có dấu OK).
        subtitle: mô tả phụ (ví dụ bộ lọc ngày đang áp dụng), bỏ qua nếu
            `None`.

    Returns:
        Nội dung file .pdf dạng bytes — dùng trực tiếp làm `data=` cho
        `st.download_button`. LUÔN trả về được PDF hợp lệ kể cả khi kaleido
        lỗi/treo khi render `fig` — trường hợp đó PDF vẫn có đủ tiêu đề +
        bảng số liệu, chỉ thay ảnh chart bằng 1 dòng chú thích (xem VIỆC 7,
        báo cáo bước 6.1 — kaleido không ổn định trên môi trường Windows
        hiện tại, không được để người dùng nhận lỗi trắng ở tính năng dùng
        hàng ngày này).

    Raises:
        RuntimeError: nếu không tìm được font tiếng Việt (xem
            `_register_vietnamese_font`) — đây là lỗi cấu hình môi trường
            thật sự chặn toàn bộ PDF (kể cả bảng số liệu), khác với lỗi
            render chart (chỉ mất ảnh, không chặn PDF).
    """
    _register_vietnamese_font()

    buffer = BytesIO()
    page_size = landscape(A4)
    left_margin = right_margin = top_margin = bottom_margin = 1.5 * cm
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=left_margin,
        rightMargin=right_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )

    title_style = ParagraphStyle(
        "LaccoTitle", fontName=_FONT_NAME_BOLD, fontSize=16, leading=20
    )
    subtitle_style = ParagraphStyle(
        "LaccoSubtitle", fontName=_FONT_NAME, fontSize=10, textColor=colors.grey
    )
    note_style = ParagraphStyle(
        "LaccoNote", fontName=_FONT_NAME, fontSize=9, textColor=colors.red
    )
    header_cell_style = ParagraphStyle(
        "LaccoHeaderCell",
        fontName=_FONT_NAME_BOLD,
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    body_cell_style = ParagraphStyle(
        "LaccoBodyCell", fontName=_FONT_NAME, fontSize=8, leading=10
    )

    elements: list[Any] = [Paragraph(title, title_style)]
    if subtitle:
        elements.append(Paragraph(subtitle, subtitle_style))
    elements.append(Spacer(1, 0.4 * cm))

    if fig is not None:
        image_bytes: bytes | None = None
        try:
            image_bytes = _render_figure_to_png_bytes(fig)
        except TimeoutError:
            logger.warning(
                "export_utils.build_pdf_report_bytes: kaleido quá thời gian "
                "chờ ({}s) khi render chart '{}' — PDF vẫn được tạo, KHÔNG "
                "có ảnh chart (xem VIỆC 6/7, báo cáo bước 6.1).",
                _KALEIDO_TIMEOUT_SECONDS,
                title,
            )
        except Exception as exc:  # noqa: BLE001 - mọi lỗi render chart đều không được chặn PDF
            logger.warning(
                "export_utils.build_pdf_report_bytes: lỗi render chart '{}' "
                "sang ảnh: {} — PDF vẫn được tạo, KHÔNG có ảnh chart.",
                title,
                exc,
            )

        if image_bytes is not None:
            available_width = page_size[0] - left_margin - right_margin
            elements.append(
                Image(
                    BytesIO(image_bytes),
                    width=available_width,
                    height=11 * cm,
                    kind="proportional",
                )
            )
            elements.append(Spacer(1, 0.4 * cm))
        else:
            elements.append(
                Paragraph(
                    "Không thể tạo biểu đồ cho bản PDF này (lỗi kỹ thuật tạm "
                    "thời) — xem biểu đồ trực tiếp trên Dashboard. Bảng số "
                    "liệu đầy đủ vẫn có bên dưới.",
                    note_style,
                )
            )
            elements.append(Spacer(1, 0.4 * cm))

    total_rows = len(df)
    truncated = total_rows > _MAX_PDF_ROWS
    display_df = df.head(_MAX_PDF_ROWS) if truncated else df
    if truncated:
        elements.append(
            Paragraph(
                f"Chỉ hiển thị {_MAX_PDF_ROWS}/{total_rows} dòng đầu — xem "
                "đầy đủ ở file Excel.",
                note_style,
            )
        )
        elements.append(Spacer(1, 0.2 * cm))

    table_data = [
        [Paragraph(str(col), header_cell_style) for col in display_df.columns]
    ]
    for row in display_df.itertuples(index=False):
        table_data.append(
            [Paragraph(_format_cell_text(value), body_cell_style) for value in row]
        )

    available_width = page_size[0] - left_margin - right_margin
    col_width = available_width / max(len(display_df.columns), 1)
    table = Table(
        table_data, colWidths=[col_width] * len(display_df.columns), repeatRows=1
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F2F2F2")],
                ),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    logger.info(
        "export_utils.build_pdf_report_bytes: title='{}' rows={} truncated={} "
        "has_chart={}",
        title,
        total_rows,
        truncated,
        fig is not None,
    )
    return buffer.getvalue()
