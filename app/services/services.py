from datetime import datetime, timezone, date
from app.config.settings import settings
from app.data.odds_api import OddsApiClient
from app.core.engines import Scorer,BacktestEngine,RiskEngine,add_synthetic_half,evaluate_signal
from app.services.openai_services import AIValidator,Explainer
class SignalService:
    def __init__(self,repo,notifier,api_sports):
        self.repo=repo; self.notifier=notifier; self.api_sports=api_sports; self.odds=OddsApiClient(settings.odds_api_key,settings.odds_regions,settings.odds_markets); self.scorer=Scorer(); self.backtest=BacktestEngine(repo); self.risk=RiskEngine(repo); self.validator=AIValidator(settings.openai_api_key,settings.openai_model,settings.enable_ai_validator); self.explainer=Explainer(settings.openai_api_key,settings.openai_model)
    def market_enabled(self,k): return {'h2h':settings.enable_winner_market,'totals':settings.enable_totals_market,'spreads':settings.enable_spreads_market,'first_half_totals':settings.enable_synthetic_half_totals}.get(k,False)
    def passes(self,a): return a.confidence>=settings.min_confidence and a.value_edge>=settings.min_value_edge and a.anomaly_score<=settings.max_anomaly_score and a.ai_validator_verdict!='REJECT' and a.ai_validator_score>=settings.min_ai_validator_score and settings.min_odds<=a.odds<=settings.max_odds and a.stake_amount>0
    async def enrich(self,e):
        if e.sport_key.startswith('basketball'): x=await self.api_sports.enrich_basketball(e.home_team,e.away_team,e.commence_time)
        elif e.sport_key.startswith('tennis'): x=await self.api_sports.enrich_tennis(e.home_team,e.away_team,e.commence_time)
        else: x={'data_quality':'odds_only'}
        if x.get('api_sports_event_id'): await self.repo.save_event_link(e.event_id,e.sport_key,x['api_sports_event_id'])
        return x
    async def run_once(self):
        for sk in [s.strip() for s in settings.sport_keys.split(',') if s.strip()]:
            try: events=await self.odds.fetch_events_for_sport(sk)
            except Exception as er: print('Fetch error',sk,er); continue
            for e in events:
                hrs=(e.commence_time-datetime.now(timezone.utc)).total_seconds()/3600
                if not (-1<=hrs<=settings.max_hours_before_match): continue
                if settings.enable_synthetic_half_totals: add_synthetic_half(e)
                enrich=await self.enrich(e); analyses=[]
                for m in e.markets:
                    if not self.market_enabled(m.key): continue
                    adj,note=await self.backtest.market_adjustment(e.sport_key,m.key)
                    for o in m.outcomes:
                        prev=await self.repo.get_previous_odds(e.event_id,m.key,o.name,o.point)
                        a=await self.scorer.analyze(e,m,o,prev,enrich,adj,note)
                        score,verdict,notes=await self.validator.validate(a); a.ai_validator_score=score; a.ai_validator_verdict=verdict; a.warnings.extend(notes)
                        stake,pct,rnote=await self.risk.suggest(a.confidence,a.value_edge,a.anomaly_score); a.stake_amount=stake; a.stake_percent=pct; a.reasons.append('Risk engine: '+rnote)
                        if self.passes(a): analyses.append(a)
                await self.repo.save_odds_snapshot(e)
                analyses.sort(key=lambda x:(x.confidence,x.ai_validator_score,x.value_edge),reverse=True)
                for a in analyses[:settings.max_signals_per_event]:
                    if await self.repo.save_signal(a): await self.notifier.send_signal(a, await self.explainer.explain(a))
class ResultTracker:
    def __init__(self, repo, notifier, api_sports):
        self.repo = repo
        self.notifier = notifier
        self.api_sports = api_sports

    async def run_once(self):
        for s in await self.repo.pending_signals():
            api_id = await self.repo.get_event_link(s["event_id"])
            payload = None

            if api_id and str(s["sport_key"]).startswith("basketball"):
                payload = await self.api_sports.basketball_result(api_id)
            elif api_id and str(s["sport_key"]).startswith("tennis"):
                payload = await self.api_sports.tennis_result(api_id)

            status, text = evaluate_signal(s, payload)

            if status in {"won", "lost", "void"}:
                signal_code = s.get("signal_code") or f"SIG-{s['id']:04d}"

                await self.repo.mark_signal(s["id"], status, text)

                await self.notifier.send_result(
                    ("✅" if status == "won" else "❌") +
                    f" NATIJA\n"
                    f"ID: {signal_code}\n"
                    f"Match: {s['match_name']}\n"
                    f"Market: {s['market_label']}\n"
                    f"Pick: {s['pick']}\n"
                    f"{text}"
                )
class ReportService:
    def __init__(self,repo,notifier): self.repo=repo; self.notifier=notifier
    async def run_once(self):
        if datetime.now().hour!=settings.daily_report_hour: return
        today=date.today().isoformat()
        if await self.repo.daily_report_sent(today): return
        stats=await self.repo.stats_summary(); perf=await self.repo.performance_by_market(); lines=[f'📊 DAILY REPORT {today}',f"P/L: {await self.repo.daily_pl()}",f"Pending:{stats.get('pending',0)} Won:{stats.get('won',0)} Lost:{stats.get('lost',0)}"]
        for r in perf[:5]:
            total=r['total'] or 0; won=r['won'] or 0; lines.append(f"{r['sport_key']}/{r['market_key']}: {won}/{total}")
        await self.notifier.send_plain('\n'.join(lines)); await self.repo.mark_daily_report_sent(today)
class LiveService:
    def __init__(self,notifier): self.notifier=notifier
    async def run_once(self): return
