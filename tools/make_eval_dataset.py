"""Generate a small labeled evaluation dataset under eval/dataset/.

Each sample: a document + `<name>.gold.json` (field labels) and, for OCR samples,
`<name>.gold.txt` (transcript). Values match the rendered content exactly so field
and OCR accuracy are meaningful.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / "eval" / "dataset"
OUT.mkdir(parents=True, exist_ok=True)


def _write_gold(stem: str, fields: dict, text: str | None = None) -> None:
    (OUT / f"{stem}.gold.json").write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
    if text is not None:
        (OUT / f"{stem}.gold.txt").write_text(text, encoding="utf-8")


def en_invoice() -> None:
    lines = [
        "TAX INVOICE",
        "Invoice No: INV-2024-0091",
        "Date: 2024-03-05    Due: 2024-04-04",
        "From: Acme Supplies Ltd",
        "Bill To: Globex Corp",
        "Description        Qty   Unit    Amount",
        "Widget A            10   5.00     50.00",
        "Widget B             2  20.00     40.00",
        "Subtotal: 90.00   VAT(10%): 9.00   Total: 99.00 USD",
    ]
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for ln in lines:
        page.insert_text((72, y), ln, fontsize=12)
        y += 20
    doc.save(str(OUT / "en_invoice.pdf"))
    doc.close()
    _write_gold("en_invoice", {
        "invoice_number": "INV-2024-0091",
        "issue_date": "2024-03-05", "due_date": "2024-04-04",
        "supplier_name": "Acme Supplies Ltd", "buyer_name": "Globex Corp",
        "currency": "USD", "subtotal": 90.0, "tax": 9.0, "total": 99.0,
        "line_items": [
            {"description": "Widget A", "quantity": 10, "unit_price": 5.0, "amount": 50.0},
            {"description": "Widget B", "quantity": 2, "unit_price": 20.0, "amount": 40.0},
        ],
    })


def table_invoice() -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 30), "TAX INVOICE   INV-TBL-2024", fontsize=13)
    cols = [50, 200, 300, 400]
    rows = [60, 100, 140, 180]
    for x in cols:
        page.draw_line((x, rows[0]), (x, rows[-1]))
    for yy in rows:
        page.draw_line((cols[0], yy), (cols[-1], yy))
    cells = [["Description", "Qty", "Amount"], ["Widget A", "10", "50.00"], ["Widget B", "2", "40.00"]]
    for r, ry in enumerate(rows[:-1]):
        for c, cx in enumerate(cols[:-1]):
            page.insert_text((cx + 5, ry + 25), cells[r][c], fontsize=10)
    page.insert_text((50, 210), "Total: 90.00 USD", fontsize=11)
    doc.save(str(OUT / "table_invoice.pdf"))
    doc.close()
    _write_gold("table_invoice", {
        "invoice_number": "INV-TBL-2024",
        "currency": "USD", "total": 90.0,
        "line_items": [
            {"description": "Widget A", "quantity": 10, "amount": 50.0},
            {"description": "Widget B", "quantity": 2, "amount": 40.0},
        ],
    })


def korean_scan() -> None:
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    font_path = next((c for c in candidates if Path(c).exists()), None)
    if not font_path:
        print("skip korean_scan (no Korean font)")
        return
    lines = [
        "세금계산서",
        "공급자: (주)아크메  등록번호 123-45-67890",
        "공급받는자: 글로벡스 주식회사",
        "공급가액 90,000원   세액 9,000원",
        "합계금액 99,000원",
    ]
    font = ImageFont.truetype(font_path, 30)
    img = Image.new("RGB", (820, 260), "white")
    d = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        d.text((25, 20 + i * 45), line, font=font, fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    doc = fitz.open()
    page = doc.new_page(width=820, height=260)
    page.insert_image(fitz.Rect(0, 0, 820, 260), stream=buf.getvalue())
    doc.save(str(OUT / "korean_scan.pdf"))
    doc.close()
    _write_gold(
        "korean_scan",
        {
            "supplier_name": "(주)아크메", "buyer_name": "글로벡스 주식회사",
            "currency": "KRW", "subtotal": 90000, "tax": 9000, "total": 99000,
        },
        text="\n".join(lines),
    )


if __name__ == "__main__":
    en_invoice()
    table_invoice()
    korean_scan()
    print("wrote eval dataset to", OUT)
    for p in sorted(OUT.iterdir()):
        print("  ", p.name)
