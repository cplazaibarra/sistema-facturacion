"""Net commercial prices based on ledger PPP, including manufactured goods."""
from decimal import Decimal, ROUND_HALF_UP
from services.money import number


def net_price(cost, markup):
    cost, markup = number(cost, 'Costo neto'), number(markup, 'Recargo')
    if cost < 0 or markup < 0:
        raise ValueError('El costo y el recargo no pueden ser negativos.')
    return float((cost * (1 + markup / 100)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
