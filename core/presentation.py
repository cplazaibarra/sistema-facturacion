"""Presentation of historical documents without altering persisted snapshots."""
import re
from decimal import Decimal, InvalidOperation


def line_quantity(line):
    value = line.get('quantity', 0) if isinstance(line, dict) else (re.search(r'\(([\d.,]+)\)\s*$', str(line)) or [None, 0])[1]
    try:
        quantity = Decimal(str(value or 0).replace(',', '.'))
        return float(quantity) if quantity.is_finite() else 0.0
    except (InvalidOperation, ValueError):
        return 0.0


def product_label(line):
    if isinstance(line, dict):
        return line.get('product_name') or line.get('name') or line.get('sku') or 'Producto sin identificación'
    return str(line or 'Producto sin identificación')


def money_cl(value):
    try:
        amount = Decimal(str(value or 0))
        if not amount.is_finite():
            return '—'
        return '$' + format(amount, ',.2f').translate(str.maketrans({',': '.', '.': ','}))
    except (InvalidOperation, ValueError):
        return '—'
