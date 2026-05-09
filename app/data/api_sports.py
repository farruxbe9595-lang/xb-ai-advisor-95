from datetime import timezone
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
from app.utils.match_names import pair_score
class ApiSportsClient:
    def __init__(self,api_key,basketball_host,tennis_host): self.api_key=api_key; self.basketball_host=basketball_host; self.tennis_host=tennis_host
    @retry(stop=stop_after_attempt(2),wait=wait_exponential(multiplier=1,min=1,max=5))
    async def _get(self,host,path,params):
        if not self.api_key: return {}
        async with aiohttp.ClientSession(headers={'x-apisports-key':self.api_key}) as session:
            async with session.get(f'https://{host}{path}',params=params,timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status>=400: return {}
                return await resp.json()
    async def _find(self,host,path,home,away,commence,kind):
        payload=await self._get(host,path,{'date':commence.astimezone(timezone.utc).date().isoformat()}); items=payload.get('response',[]) if isinstance(payload,dict) else []
        best=None; best_score=0
        for it in items:
            if kind=='basketball': d=it.get('teams',{}); h=(d.get('home',{}) or {}).get('name',''); a=(d.get('away',{}) or {}).get('name','')
            else: d=it.get('players',{}); h=(d.get('home',{}) or {}).get('name',''); a=(d.get('away',{}) or {}).get('name','')
            sc=pair_score(home,away,h,a)
            if sc>best_score: best_score=sc; best=it
        return best if best and best_score>=(72 if kind=='basketball' else 68) else None
    async def enrich_basketball(self,home,away,commence):
        g=await self._find(self.basketball_host,'/games',home,away,commence,'basketball')
        if not g: return {'data_quality':'odds_only'}
        teams=g.get('teams',{}) or {}; return {'data_quality':'odds_plus_api_sports','api_sports_event_id':str(g.get('id','')),'api_home':(teams.get('home',{}) or {}).get('name'),'api_away':(teams.get('away',{}) or {}).get('name')}
    async def enrich_tennis(self,home,away,commence):
        f=await self._find(self.tennis_host,'/fixtures',home,away,commence,'tennis')
        if not f: return {'data_quality':'odds_only'}
        court=f.get('court',{}) or {}; players=f.get('players',{}) or {}; return {'data_quality':'odds_plus_api_sports','api_sports_event_id':str(f.get('id','')),'api_home':(players.get('home',{}) or {}).get('name'),'api_away':(players.get('away',{}) or {}).get('name'),'surface_note':court.get('surface')}
    async def basketball_result(self,game_id):
        payload=await self._get(self.basketball_host,'/games',{'id':game_id}); games=payload.get('response',[]) if isinstance(payload,dict) else []
        if not games: return None
        g=games[0]; status=str((g.get('status',{}) or {}).get('long','')).lower()
        if not any(x in status for x in ['finished','after','ended','full time','ft']): return None
        scores=g.get('scores',{}) or {}; h=scores.get('home',{}) or {}; a=scores.get('away',{}) or {}; ht=h.get('total'); at=a.get('total')
        if ht is None or at is None: return None
        fh=(int(h.get('quarter_1') or 0)+int(h.get('quarter_2') or 0)) if h.get('quarter_1') is not None and h.get('quarter_2') is not None else None
        fa=(int(a.get('quarter_1') or 0)+int(a.get('quarter_2') or 0)) if a.get('quarter_1') is not None and a.get('quarter_2') is not None else None
        teams=g.get('teams',{}) or {}; hn=(teams.get('home',{}) or {}).get('name'); an=(teams.get('away',{}) or {}).get('name')
        return {'home_score':int(ht),'away_score':int(at),'first_half_home':fh,'first_half_away':fa,'winner':hn if int(ht)>int(at) else an,'status':status}
    async def tennis_result(self,fixture_id):
        payload=await self._get(self.tennis_host,'/fixtures',{'id':fixture_id}); fixtures=payload.get('response',[]) if isinstance(payload,dict) else []
        if not fixtures: return None
        f=fixtures[0]; status=str((f.get('status',{}) or {}).get('long','')).lower()
        if not any(x in status for x in ['finished','ended','completed']): return None
        players=f.get('players',{}) or {}; hn=(players.get('home',{}) or {}).get('name',''); an=(players.get('away',{}) or {}).get('name','')
        scores=f.get('scores',{}) or {}; hs=(scores.get('home',{}) or {}).get('total') if isinstance(scores,dict) else None; aw=(scores.get('away',{}) or {}).get('total') if isinstance(scores,dict) else None
        winner=hn if hs is not None and aw is not None and int(hs)>int(aw) else an if hs is not None and aw is not None else None
        return {'home_score':int(hs) if hs is not None else None,'away_score':int(aw) if aw is not None else None,'winner':winner,'status':status}
