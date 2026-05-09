def decimal_to_implied_probability(odds:float)->float: return 100.0/odds if odds>1 else 0.0
def clamp(value:float, minimum:float, maximum:float)->float: return max(minimum, min(maximum, value))
def market_label(key:str)->str: return {'h2h':'Match winner','totals':'Total over/under','spreads':'Handicap/spread','first_half_totals':'1-half total over/under'}.get(key,key)
