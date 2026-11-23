import io
from datetime import date, datetime
from decimal import Decimal
from fastapi import Response
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HEAD_FILL = PatternFill("solid", fgColor="2457D6")
HEAD_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14)
SECTION_FONT = Font(bold=True)
SECTION_FILL = PatternFill("solid", fgColor="EEF3FF")
THIN = Side(style="thin", color="D5DAE1")
MONEY = '#,##0.00'
DATE = 'DD.MM.YYYY'

class Money(Decimal):
    pass

def _width(value):
    if value is None:
        return 0
    if isinstance(value, (date, datetime)):
        return 10
    if isinstance(value, (int, float, Decimal)):
        return len(f"{value:,.2f}") if isinstance(value, Decimal) else len(str(value))
    return max(len(line) for line in str(value).split("\n"))

def _write(ws, row_idx, values, header=False):
    for col, value in enumerate(values, 1):
        cell = ws.cell(row=row_idx, column=col, value=value)
        if header:
            cell.font, cell.fill = HEAD_FONT, HEAD_FILL
            cell.alignment = Alignment(vertical="center", wrap_text=True)
        else:
            cell.border = Border(bottom=THIN)
            if isinstance(value, Decimal):
                cell.number_format = MONEY
            elif isinstance(value, (date, datetime)):
                cell.number_format = DATE
            elif isinstance(value, str):
                cell.number_format = "@"
        if isinstance(value, str) and value.startswith("="):
            cell.data_type = "s"

def table_sheet(wb, title, header, rows, widths=None):
    ws = wb.create_sheet(title[:31])
    _write(ws, 1, header, header=True)
    for i, row in enumerate(rows, 2):
        _write(ws, i, row)
    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(header))}{len(rows) + 1}"
    ws.row_dimensions[1].height = 30
    for col in range(1, len(header) + 1):
        longest = max([_width(header[col - 1])] + [_width(r[col - 1]) for r in rows if len(r) >= col])
        ws.column_dimensions[get_column_letter(col)].width = min(max(longest + 3, 9), (widths or {}).get(col, 45))
    return ws

def report_sheet(wb, title, heading, sections):
    ws = wb.create_sheet(title[:31])
    ws.cell(row=1, column=1, value=heading).font = TITLE_FONT
    row, widths = 3, {}
    for name, header, rows in sections:
        cell = ws.cell(row=row, column=1, value=name)
        cell.font, cell.fill = SECTION_FONT, SECTION_FILL
        for col in range(2, len(header) + 1):
            ws.cell(row=row, column=col).fill = SECTION_FILL
        row += 1
        _write(ws, row, header, header=True)
        for item in rows:
            row += 1
            _write(ws, row, item)
        for col, label in enumerate(header, 1):
            widths[col] = max([widths.get(col, 0), _width(label)] + [_width(r[col - 1]) for r in rows])
        row += 2
    for col, w in widths.items():
        ws.column_dimensions[get_column_letter(col)].width = min(max(w + 3, 12), 48)
    return ws

def xlsx_response(build, filename):
    wb = Workbook()
    wb.remove(wb.active)
    build(wb)
    stream = io.BytesIO()
    wb.save(stream)
    return Response(stream.getvalue(),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})
