from datetime import datetime, timezone, date, timedelta

from app.config.settings import settings
from app.data.odds_api import OddsApiClient
from app.core.engines import (
    Scorer,
    BacktestEngine,
    RiskEngine,
    add_synthetic_half,
    evaluate_signal,
)
from app.services.openai_services import AIValidator, Explainer


class SignalService:
    def __init__(self, repo, notifier, api_sports):
        self.repo = repo
        self.notifier = notifier
        self.api_sports = api_sports
        self.odds = OddsApiClient(
            settings.odds_api_key,
            settings.odds_regions,
            settings.odds_markets,
        )
        self.scorer = Scorer()
        self.backtest = BacktestEngine(repo)
        self.risk = RiskEngine(repo)
        self.validator = AIValidator(
            settings.openai_api_key,
            settings.openai_model,
            settings.enable_ai_validator,
        )
        self.explainer = Explainer(
            settings.openai_api_key,
            settings.openai_model,
        )

    def market_enabled(self, k):
        return {
            'h2h': settings.enable_winner_market,
            'totals': settings.enable_totals_market,
            'spreads': settings.enable_spreads_market,
            'first_half_totals': settings.enable_synthetic_half_totals,
        }.get(k, False)

    def passes(self, a):
        base_ok = (
            a.confidence >= settings.min_confidence
            and a.value_edge >= settings.min_value_edge
            and a.anomaly_score <= settings.max_anomaly_score
            and settings.min_odds <= a.odds <= settings.max_odds
            and a.stake_amount > 0
        )
        if not base_ok:
            return False

        if settings.enable_ai_validator:
            return (
                a.ai_validator_verdict != 'REJECT'
                and a.ai_validator_score >= settings.min_ai_validator_score
            )

        # AI validator o'chirilsa signalni AI score bilan bloklamaymiz.
        return True

    def event_day_rank(self, commence_time):
        event_date = (commence_time + timedelta(hours=settings.timezone_offset_hours)).date()
        today = (datetime.now(timezone.utc) + timedelta(hours=settings.timezone_offset_hours)).date()

        if event_date == today:
            return 0
        if event_date == date.fromordinal(today.toordinal() + 1):
            return 1
        return 2

    async def enrich(self, e):
        if e.sport_key.startswith('basketball'):
            x = await self.api_sports.enrich_basketball(e.home_team, e.away_team, e.commence_time)
        elif e.sport_key.startswith('tennis'):
            x = await self.api_sports.enrich_tennis(e.home_team, e.away_team, e.commence_time)
        elif e.sport_key.startswith('soccer') or e.sport_key.startswith('football'):
            x = await self.api_sports.enrich_soccer(e.home_team, e.away_team, e.commence_time)
        else:
            x = {'data_quality': 'odds_only'}

        if x.get('api_sports_event_id'):
            await self.repo.save_event_link(e.event_id, e.sport_key, x['api_sports_event_id'])

        return x

    async def best_analysis_for_event(self, e):
        if settings.enable_synthetic_half_totals:
            add_synthetic_half(e)

        enrich = await self.enrich(e)
        analyses = []

        for m in e.markets:
            if not self.market_enabled(m.key):
                continue

            adj, note = await self.backtest.market_adjustment(e.sport_key, m.key)

            for o in m.outcomes:
                prev = await self.repo.get_previous_odds(e.event_id, m.key, o.name, o.point)

                a = await self.scorer.analyze(e, m, o, prev, enrich, adj, note)

                if settings.enable_ai_validator:
                    score, verdict, notes = await self.validator.validate(a)
                else:
                    score, verdict, notes = 100, 'DISABLED', ['AI validator o‘chirilgan.']

                a.ai_validator_score = score
                a.ai_validator_verdict = verdict
                a.warnings.extend(notes)

                stake, pct, rnote = await self.risk.suggest(
                    a.confidence,
                    a.value_edge,
                    a.anomaly_score,
                )
                a.stake_amount = stake
                a.stake_percent = pct
                a.reasons.append('Risk engine: ' + rnote)

                if self.passes(a):
                    analyses.append(a)

        await self.repo.save_odds_snapshot(e)

        if not analyses:
            return None

        analyses.sort(
            key=lambda x: (
                x.confidence,
                x.ai_validator_score,
                x.value_edge,
                -x.anomaly_score,
            ),
            reverse=True,
        )

        # Har bir eventdan eng kuchli bitta signal qaytadi.
        return analyses[0]

    async def run_once(self):
        all_events = []
        sport_list = [s.strip() for s in settings.sport_keys.split(',') if s.strip()]

        print(f'[SIGNAL] sports={sport_list}')

        for sk in sport_list:
            try:
                print(f'[FETCH] {sk} started')
                events = await self.odds.fetch_events_for_sport(sk)
                print(f'[FETCH] {sk} events={len(events)}')
            except Exception as er:
                print('[FETCH ERROR]', sk, repr(er))
                continue

            accepted = 0
            now_utc = datetime.now(timezone.utc)

            for e in events:
                hrs = (e.commence_time - now_utc).total_seconds() / 3600

                if not (-1 <= hrs <= settings.max_hours_before_match):
                    continue

                all_events.append(e)
                accepted += 1

            print(f'[FILTER] {sk} accepted_by_time={accepted}')

        all_events.sort(
            key=lambda e: (
                self.event_day_rank(e.commence_time),
                e.commence_time,
            )
        )

        print(f'[ANALYZE] total_events={len(all_events)}')

        sent = 0

        for e in all_events:
            best = await self.best_analysis_for_event(e)

            if best is None:
                print(f'[NO SIGNAL] {e.sport_key} | {e.home_team} vs {e.away_team}')
                continue

            if await self.repo.save_signal(best):
                sent += 1
                print(
                    f'[SIGNAL SENT] {e.sport_key} | '
                    f'{e.home_team} vs {e.away_team} | '
                    f'{best.market_key} | {best.pick}'
                )

                explanation = await self._safe_explain(best)
                await self.notifier.send_signal(best, explanation)
            else:
                print(f'[DUPLICATE] {e.sport_key} | {e.home_team} vs {e.away_team}')

        print(f'[SIGNAL] finished sent={sent}')

    async def _safe_explain(self, best):
        try:
            if not settings.openai_api_key:
                return 'OpenAI API kalit yo‘q. Signal ichki model va risk filtr orqali saralandi.'
            return await self.explainer.explain(best)
        except Exception as e:
            return f'AI izoh xatosi: {repr(e)}. Signal ichki model va risk filtr orqali saralandi.'


class ResultTracker:
    def __init__(self, repo, notifier, api_sports):
        self.repo = repo
        self.notifier = notifier
        self.api_sports = api_sports

    async def run_once(self):
        for s in await self.repo.pending_signals():
            api_id = await self.repo.get_event_link(s['event_id'])
            payload = None
            sport_key = str(s['sport_key'])

            if api_id and sport_key.startswith('basketball'):
                payload = await self.api_sports.basketball_result(api_id)
            elif api_id and sport_key.startswith('tennis'):
                payload = await self.api_sports.tennis_result(api_id)
            elif api_id and (sport_key.startswith('soccer') or sport_key.startswith('football')):
                payload = await self.api_sports.soccer_result(api_id)

            status, text = evaluate_signal(s, payload)

            if status in {'won', 'lost', 'void'}:
                signal_code = s.get('signal_code') or f"SIG-{s['id']:04d}"
                await self.repo.mark_signal(s['id'], status, text)

                icon = {'won': '✅', 'lost': '❌', 'void': '➖'}.get(status, 'ℹ️')
                title = {'won': 'YUTDI', 'lost': 'YUTQAZDI', 'void': 'VOID/PUSH'}.get(status, status.upper())

                await self.notifier.send_result(
                    f"{icon} NATIJA — {title}\n"
                    f"ID: {signal_code}\n"
                    f"Match: {s['match_name']}\n"
                    f"Market: {s['market_label']}\n"
                    f"Pick: {s['pick']}\n"
                    f"{text}"
                )
            else:
                signal_code = s.get('signal_code') or f"SIG-{s['id']:04d}"
                print(f"[RESULT PENDING] {signal_code}: {text}")


class ReportService:
    def __init__(self, repo, notifier):
        self.repo = repo
        self.notifier = notifier

    async def run_once(self):
        # Hozircha placeholder. Keyingi bosqichda kunlik reportni shu yerga qo'shamiz.
        return


class LiveService:
    def __init__(self, notifier):
        self.notifier = notifier

    async def run_once(self):
        # Hozircha placeholder.
        return
