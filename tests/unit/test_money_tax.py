from decimal import Decimal
import pytest
from services.money import amounts_from_net, amounts_from_total, quotation_line, document_amounts
from services.pricing import net_price


def test_net_vat_gross_and_discount_are_not_double_taxed():
    line = quotation_line(3, '1000.50', 10)
    assert line['subtotal'] == 2701.35
    assert amounts_from_net(line['subtotal']) == {'net': 2701.0, 'vat': 513.0, 'total': 3214.0}
    assert document_amounts([line], 3214)['net'] == 2701


def test_half_peso_rounds_up_and_tax_is_based_on_document_net():
    assert amounts_from_net('102.50') == {'net': 103.0, 'vat': 20.0, 'total': 123.0}
    assert amounts_from_net('50') == {'net': 50.0, 'vat': 10.0, 'total': 60.0}


@pytest.mark.parametrize('qty,price,discount', [(0,1,0),(-1,1,0),('1.5',1,0),(1,0,0),(1,-1,0),(1,'NaN',0),(1,'Infinity',0),(1,1,-1),(1,1,101),(1,1,'NaN')])
def test_invalid_monetary_input_is_rejected(qty, price, discount):
    with pytest.raises(ValueError):
        quotation_line(qty,price,discount)


def test_full_discount_remains_zero_instead_of_reusing_undiscounted_price():
    line = quotation_line(1,1000,100)
    assert line['subtotal'] == 0
    assert document_amounts([line],0)['total'] == 0


def test_historical_total_and_payments_are_preserved_with_net_display_lines():
    original = [{'quantity':3,'price':10000,'discount':0,'subtotal':30000}]
    result = document_amounts(original,30000)
    assert result['historical_total_preserved']
    assert result['total'] == 30000
    assert result['net'] + result['vat'] == 30000
    assert sum(line['subtotal'] for line in result['lines']) == result['net']
    assert original[0]['price'] == 10000


def test_legacy_missing_lines_and_decimal_totals_preserve_contract():
    assert document_amounts(['legacy label'],11900)['total'] == 11900
    amounts = amounts_from_total('11900.50')
    assert Decimal(str(amounts['net'])) + Decimal(str(amounts['vat'])) == Decimal('11900.50')


def test_markup_is_explicit_net_price_and_uses_unrounded_cost():
    assert net_price('1016.6667',40) == 1423.33
    assert net_price(1000,40) == 1400
    with pytest.raises(ValueError):
        net_price(1000,'NaN')
