import re
from openai import AsyncOpenAI
class AIValidator:
    def __init__(self,api_key,model,enabled=True): self.enabled=bool(api_key and enabled); self.client=AsyncOpenAI(api_key=api_key) if self.enabled else None; self.model=model
    async def validate(self,a):
        if not self.enabled or self.client is None: return 100,'APPROVE',[]
        prompt=(f"Return exactly:\nSCORE: 0-100\nVERDICT: APPROVE or REJECT\nREASON: Uzbek Latin short\n"
                f"Match:{a.match_name}\nMarket:{a.market_label}\nPick:{a.pick}\nOdds:{a.odds}\nConfidence:{a.confidence}\nEdge:{a.value_edge}\nAnomaly:{a.anomaly_score}\nSynthetic:{a.synthetic}")
        try:
            res=await self.client.chat.completions.create(model=self.model,messages=[{'role':'system','content':'Be conservative. Never guarantee profit.'},{'role':'user','content':prompt}],temperature=0.1,max_tokens=120)
            txt=res.choices[0].message.content.strip(); sm=re.search(r'SCORE:\s*(\d+)',txt,re.I); vm=re.search(r'VERDICT:\s*(APPROVE|REJECT)',txt,re.I); rm=re.search(r'REASON:\s*(.+)',txt,re.I|re.S)
            return int(sm.group(1)) if sm else 70, vm.group(1).upper() if vm else 'APPROVE', [f"AI validator: {rm.group(1).strip() if rm else txt}"]
        except Exception: return 75,'APPROVE',['AI validator ishlamadi, asosiy risk filtri ishladi.']
class Explainer:
    def __init__(self,api_key,model): self.enabled=bool(api_key); self.client=AsyncOpenAI(api_key=api_key) if api_key else None; self.model=model
    async def explain(self,a):
        reasons='\n'.join('- '+r for r in a.reasons); warnings='\n'.join('- '+w for w in a.warnings) if a.warnings else '- Katta anomaliya yo‘q'
        if not self.enabled or self.client is None: return reasons
        prompt=f"Uzbek Latin scriptda professional izoh yoz, kafolat bermagin.\nMatch:{a.match_name}\nMarket:{a.market_label}\nPick:{a.pick}\nOdds:{a.odds}\nConfidence:{a.confidence}\nAI validator:{a.ai_validator_score}/{a.ai_validator_verdict}\nStake:{a.stake_amount}\nReasons:\n{reasons}\nWarnings:\n{warnings}"
        try:
            res=await self.client.chat.completions.create(model=self.model,messages=[{'role':'system','content':'Conservative sports analytics assistant.'},{'role':'user','content':prompt}],temperature=0.2,max_tokens=250)
            return res.choices[0].message.content.strip()
        except Exception: return reasons
