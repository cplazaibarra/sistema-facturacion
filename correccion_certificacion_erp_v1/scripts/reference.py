"""Independent oracle: no imports from application monetary/cost modules."""
from decimal import Decimal,ROUND_HALF_UP
D=lambda n:Decimal(str(n))
def invoice(lines):
    discounted=[]
    for qty,price,discount in lines:
        value=D(qty)*D(price)*(D(100)-D(discount))/D(100)
        discounted.append(value.quantize(D('.01'),rounding=ROUND_HALF_UP))
    net=sum(discounted,D(0)).quantize(D(1),rounding=ROUND_HALF_UP)
    tax=(net*D(19)/D(100)).quantize(D(1),rounding=ROUND_HALF_UP)
    return {'net':net,'vat':tax,'total':net+tax,'lines':discounted}
def ppp(events,scale='0.0001'):
    units=D(0);value=D(0);average=D(0)
    for quantity,cost in events:
        q=D(quantity)
        if q>0:
            value+=q*D(cost);units+=q;average=value/units
        else:
            value-=abs(q)*average;units-=abs(q)
    return average.quantize(D(scale),rounding=ROUND_HALF_UP)
