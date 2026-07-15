"""Generate small demo documents under samples/ (text PDF + image-only PDF)."""

from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "samples"
OUT.mkdir(exist_ok=True)


def make_text_pdf() -> Path:
    doc = fitz.open()
    page = doc.new_page()
    lines = [
        "TAX INVOICE",
        "Invoice No: INV-2024-0091",
        "Date: 2024-03-05    Due: 2024-04-04",
        "From: Acme Supplies Ltd",
        "Bill To: Globex Corp",
        "",
        "Description        Qty   Unit    Amount",
        "Widget A            10   5.00     50.00",
        "Widget B             2  20.00     40.00",
        "",
        "Subtotal: 90.00   VAT(10%): 9.00   Total: 99.00 USD",
    ]
    y = 72
    for ln in lines:
        page.insert_text((72, y), ln, fontsize=12)
        y += 18
    path = OUT / "invoice.pdf"
    doc.save(str(path))
    doc.close()
    return path


def make_scanned_pdf() -> Path:
    img = Image.new("RGB", (800, 300), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 20), "SCANNED INVOICE  INV-SCAN-7  Total: 123.00 USD", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=800, height=300)
    page.insert_image(fitz.Rect(0, 0, 800, 300), stream=buf.getvalue())
    path = OUT / "scan.pdf"
    doc.save(str(path))
    doc.close()
    return path


def make_table_image_pdf() -> Path:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 30), "TAX INVOICE   INV-TBL-2024", fontsize=13)
    cols = [50, 200, 300, 400]
    rows = [60, 100, 140, 180]
    for x in cols:
        page.draw_line((x, rows[0]), (x, rows[-1]))
    for y in rows:
        page.draw_line((cols[0], y), (cols[-1], y))
    cells = [["Description", "Qty", "Amount"], ["Widget A", "10", "50.00"], ["Widget B", "2", "40.00"]]
    for r, ry in enumerate(rows[:-1]):
        for c, cx in enumerate(cols[:-1]):
            page.insert_text((cx + 5, ry + 25), cells[r][c], fontsize=10)
    page.insert_text((50, 210), "Total: 90.00 USD", fontsize=11)
    # embedded logo image
    logo = Image.new("RGB", (120, 60), "navy")
    d = ImageDraw.Draw(logo)
    d.text((10, 20), "ACME", fill="white")
    buf = io.BytesIO()
    logo.save(buf, format="PNG")
    page.insert_image(fitz.Rect(430, 40, 550, 100), stream=buf.getvalue())
    path = OUT / "table_image.pdf"
    doc.save(str(path))
    doc.close()
    return path


def make_korean_scan_pdf() -> Path | None:
    """A Korean scanned invoice (image-only) — needs a Korean TTF; skipped if absent."""
    from PIL import ImageFont

    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    font_path = next((c for c in candidates if Path(c).exists()), None)
    if not font_path:
        print("skip korean_scan.pdf (no Korean font found)")
        return None
    font = ImageFont.truetype(font_path, 30)
    img = Image.new("RGB", (820, 260), "white")
    d = ImageDraw.Draw(img)
    lines = [
        "세금계산서",
        "공급자: (주)아크메  등록번호 123-45-67890",
        "공급받는자: 글로벡스 주식회사",
        "공급가액 90,000원   세액 9,000원",
        "합계금액 99,000원",
    ]
    for i, line in enumerate(lines):
        d.text((25, 20 + i * 45), line, font=font, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=820, height=260)
    page.insert_image(fitz.Rect(0, 0, 820, 260), stream=buf.getvalue())
    path = OUT / "korean_scan.pdf"
    doc.save(str(path))
    doc.close()
    return path


if __name__ == "__main__":
    print("wrote", make_text_pdf())
    print("wrote", make_scanned_pdf())
    print("wrote", make_table_image_pdf())
    kr = make_korean_scan_pdf()
    if kr:
        print("wrote", kr)
