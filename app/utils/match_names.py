from rapidfuzz import fuzz
def norm_name(name:str)->str: return name.lower().replace('fc','').replace('bc','').replace('.','').replace('-',' ').replace('_',' ').strip()
def similarity(a:str,b:str)->int: return int(fuzz.token_set_ratio(norm_name(a), norm_name(b)))
def pair_score(ha,aa,hb,ab)->int: return max((similarity(ha,hb)+similarity(aa,ab))//2,(similarity(ha,ab)+similarity(aa,hb))//2)
