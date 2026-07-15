"""Example extraction schema (Pydantic). Usage:

    docs-reader extract invoice.pdf --schema schemas/invoice.py

The loader picks the model named ``Schema`` (or the single BaseModel in the file).
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(description="Product or service description")
    quantity: Optional[float] = Field(default=None, description="Quantity / count")
    unit_price: Optional[float] = Field(default=None, description="Price per unit")
    amount: Optional[float] = Field(default=None, description="Line total")


class Invoice(BaseModel):
    invoice_number: Optional[str] = Field(default=None, description="Invoice / document number")
    issue_date: Optional[date] = Field(default=None, description="Date the invoice was issued")
    due_date: Optional[date] = Field(default=None, description="Payment due date")
    supplier_name: Optional[str] = Field(default=None, description="Seller / supplier name")
    buyer_name: Optional[str] = Field(default=None, description="Buyer / customer name")
    currency: Optional[str] = Field(default=None, description="ISO currency code, e.g. KRW, USD")
    subtotal: Optional[float] = Field(default=None, description="Amount before tax")
    tax: Optional[float] = Field(default=None, description="Tax amount (VAT)")
    total: Optional[float] = Field(default=None, description="Grand total to be paid")
    line_items: list[LineItem] = Field(default_factory=list, description="Itemized lines")


# Explicit designation so the loader is unambiguous even if helper models exist.
Schema = Invoice
