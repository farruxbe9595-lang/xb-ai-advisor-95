from datetime import datetime
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
from app.models.domain import Event,Market,Outcome
class OddsApiClient:
    BASE='https://api.the-odds-api.com/v4/sports'
    def __init__(self,api_key,regions,markets): self.api_key=api_key; self.regions=regions; self.markets=markets
    @retry(stop=stop_after_attempt(3),wait=wait_exponential(multiplier=1,min=1,max=8))
    async def _get_json(self,url,params):
        async with aiohttp.ClientSession() as session:
            async with session.get(url,params=params,timeout=aiohttp.ClientTimeout(total=35)) as resp:
                text=await resp.text()
                if resp.status>=400: raise RuntimeError(f'Odds API HTTP {resp.status}: {text[:300]}')
                return await resp.json()
    async def fetch_events_for_sport(self,sport_key):
        if not self.api_key: raise RuntimeError('ODDS_API_KEY is empty')
        payload=await self._get_json(f'{self.BASE}/{sport_key}/odds',{'apiKey':self.api_key,'regions':self.regions,'markets':self.markets,'oddsFormat':'decimal','dateFormat':'iso'})
        events=[]
        if not isinstance(payload,list): return events
        for item in payload:
            markets=[]
            for bm in item.get('bookmakers',[]):
                bookmaker=bm.get('title') or bm.get('key') or 'bookmaker'
                for mk in bm.get('markets',[]):
                    outs=[Outcome(str(o.get('name','')),float(o['price']),float(o['point']) if o.get('point') is not None else None) for o in mk.get('outcomes',[]) if o.get('price') is not None]
                    if outs: markets.append(Market(str(mk.get('key','')),bookmaker,outs,mk.get('last_update')))
            if item.get('id') and item.get('commence_time'):
                events.append(Event(str(item['id']),str(item.get('sport_key',sport_key)),str(item.get('sport_title',sport_key)),datetime.fromisoformat(item['commence_time'].replace('Z','+00:00')),str(item.get('home_team','')),str(item.get('away_team','')),markets,item))
        return events
