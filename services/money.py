"""CLP document amounts: unit prices are net; stored sale totals include VAT."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

VAT_RATE = Decimal('0.19')


def number(value, label='Valor'):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'{label} debe ser un número válido.') from None
    if not result.is_finite():
        raise ValueError(f'{label} debe ser finito.')
    return result


def pesos(value):
    return number(value).quantize(Decimal('1'), rounding=ROUND_HALF_UP)


def amounts_from_net(net):
    net = pesos(net)
    if net < 0:
        raise ValueError('El neto no puede ser negativo.')
    vat = pesos(net * VAT_RATE)
    return {'net': float(net), 'vat': float(vat), 'total': float(net + vat)}


def amounts_from_total(total):
    total = number(total)
    if total < 0:
        raise ValueError('El total no puede ser negativo.')
    # Historical totals may have cents. Preserve their contractual amount.
    net = pesos(total / (1 + VAT_RATE))
    return {'net': float(net), 'vat': float(total - net), 'total': float(total)}


def quotation_line(quantity, price, discount=0):
    quantity = number(quantity, 'Cantidad')
    price = number(price, 'Precio neto')
    discount = number(discount, 'Descuento')
    if quantity <= 0 or quantity != quantity.to_integral_value():
        raise ValueError('La cantidad debe ser un entero positivo.')
    if price <= 0:
        raise ValueError('El precio neto debe ser mayor que cero.')
    if not 0 <= discount <= 100:
        raise ValueError('El descuento debe estar entre 0 y 100%.')
    subtotal = (quantity * price * (1 - discount / 100)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return {'quantity': int(quantity), 'price': float(price), 'discount': float(discount), 'subtotal': float(subtotal)}


def line_subtotal(line):
    if line.get('subtotal') is not None:
        return number(line['subtotal'])
    quantity = number(line.get('quantity') or 0)
    price = number(line.get('price', line.get('unit_price')) or 0)
    discount = number(line.get('discount') or 0)
    return quantity * price * (1 - discount / 100)


def document_amounts(products, total):
    """Display historical gross lines as net without increasing existing receivables."""
    result = amounts_from_total(total)
    lines = [dict(p) for p in products if isinstance(p, dict)] if isinstance(products, list) else []
    line_total = sum((line_subtotal(p) for p in lines), Decimal(0))
    net_amounts = amounts_from_net(line_total)
    # Newly created documents have net lines and gross total. Old documents
    # often have gross lines equal to the stored total; never add VAT twice.
    net_lines = abs(number(net_amounts['total']) - number(total)) <= Decimal('.01')
    if net_lines:
        result = net_amounts
    elif line_total > 0:
        factor = number(result['net']) / line_total
        allocated = Decimal(0)
        for i, line in enumerate(lines):
            subtotal = line_subtotal(line)
            net_sub = (subtotal * factor).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
            if i == len(lines)-1:
                net_sub = number(result['net'])-allocated
            allocated += net_sub
            line['price'] = float(number(line.get('price', line.get('unit_price')) or 0)*factor)
            line['subtotal'] = float(net_sub)
    result['lines'] = lines
    result['historical_total_preserved'] = not net_lines
    return result
