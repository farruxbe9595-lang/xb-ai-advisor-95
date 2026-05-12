from datetime import datetime, timezone, date
from math import prod

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
            getattr(settings, "ai_enabled", True) and getattr(settings, "enable_ai_validator", True),
        )
        self.explainer = Explainer(settings.openai_api_key, settings.openai_model)

    def _enabled_markets(self):
        return {
            x.strip()
            for x in str(getattr(settings, "enabled_markets", settings.odds_markets)).split(",")
            if x.strip()
        }

    def market_enabled(self, key):
        return key in self._enabled_markets()

    def passes(self, a):
        return (
            a.confidence >= settings.min_confidence
            and a.value_edge >= settings.min_value_edge
            and a.anomaly_score <= settings.max_anomaly_score
            and str(a.ai_validator_verdict).upper() != "REJECT"
            and a.ai_validator_score >= settings.min_ai_validator_score
            and settings.min_odds <= a.odds <= settings.max_odds
            and a.stake_amount > 0
        )

    def passes_express(self, a):
        if not self.passes(a):
            return False

        return (
            a.confidence >= settings.express_min_confidence
            and a.ai_validator_score >= settings.express_min_ai_score
            and a.value_edge >= settings.express_min_value_edge
            and a.anomaly_score <= settings.express_max_anomaly_score
            and settings.express_min_odds <= a.odds <= settings.express_max_odds
            and str(a.ai_validator_verdict).upper() not in {"REJECT", "CAUTION_REJECT"}
            and "Yuqori" not in str(a.risk_level)
        )

    def event_day_rank(self, commence_time):
        now = datetime.now(timezone.utc)
        event_date = commence_time.date()
        today = now.date()

        if event_date == today:
            return 0
        if event_date == date.fromordinal(today.toordinal() + 1):
            return 1
        return 2

    async def enrich(self, event):
        if event.sport_key.startswith("basketball"):
            data = await self.api_sports.enrich_basketball(event.home_team, event.away_team, event.commence_time)
        elif event.sport_key.startswith("tennis"):
            data = await self.api_sports.enrich_tennis(event.home_team, event.away_team, event.commence_time)
        elif event.sport_key.startswith("soccer"):
            data = await self.api_sports.enrich_soccer(event.home_team, event.away_team, event.commence_time)
        else:
            data = {"data_quality": "odds_only"}

        if data.get("api_sports_event_id"):
            await self.repo.save_event_link(event.event_id, event.sport_key, data["api_sports_event_id"])

        return data

    async def best_analysis_for_event(self, event):
        if getattr(settings, "enable_synthetic_half_totals", False):
            add_synthetic_half(event)

        enrich_data = await self.enrich(event)
        analyses = []

        for market in event.markets:
            if not self.market_enabled(market.key):
                continue

            adj, note = await self.backtest.market_adjustment(event.sport_key, market.key)

            for outcome in market.outcomes:
                prev = await self.repo.get_previous_odds(event.event_id, market.key, outcome.name, outcome.point)

                analysis = await self.scorer.analyze(event, market, outcome, prev, enrich_data, adj, note)

                score, verdict, notes = await self.validator.validate(analysis)
                analysis.ai_validator_score = score
                analysis.ai_validator_verdict = verdict
                analysis.warnings.extend(notes)

                stake, pct, risk_note = await self.risk.suggest(
                    analysis.confidence,
                    analysis.value_edge,
                    analysis.anomaly_score,
                )
                analysis.stake_amount = stake
                analysis.stake_percent = pct
                analysis.reasons.append("Risk engine: " + risk_note)

                if self.passes(analysis):
                    analyses.append(analysis)

        await self.repo.save_odds_snapshot(event)

        if not analyses:
            return None

        analyses.sort(
            key=lambda x: (
                x.confidence,
                x.ai_validator_score,
                x.value_edge,
                -x.anomaly_score,
                -abs(float(x.odds) - 1.60),
            ),
            reverse=True,
        )

        return analyses[0]

    def build_express_coupon(self, candidates):
        filtered = [x for x in candidates if self.passes_express(x)]

        filtered.sort(
            key=lambda x: (
                x.confidence * 0.45
                + x.ai_validator_score * 0.30
                + x.value_edge * 1.20
                - x.anomaly_score * 0.65
                - abs(float(x.odds) - 1.60) * 4.0
            ),
            reverse=True,
        )

        legs = []
        used_events = set()
        used_sports = set()
        total_odds = 1.0

        max_legs = max(1, int(settings.express_max_legs))
        min_legs = max(1, int(settings.express_min_legs))

        for a in filtered:
            if a.event_id in used_events:
                continue

            if not settings.express_allow_same_sport and a.sport_key in used_sports:
                continue

            next_total = total_odds * float(a.odds)
            if next_total > settings.express_max_total_odds:
                continue

            legs.append(a)
            used_events.add(a.event_id)
            used_sports.add(a.sport_key)
            total_odds = next_total

            if len(legs) >= max_legs:
                break

        if len(legs) < min_legs:
            return []

        total_odds = prod(float(x.odds) for x in legs)
        if total_odds < settings.express_min_total_odds or total_odds > settings.express_max_total_odds:
            return []

        return legs

    async def _fetch_events(self):
        all_events = []
        sport_list = [s.strip() for s in settings.sport_keys.split(",") if s.strip()]

        print(f"[SIGNAL] sports={sport_list}")
        print(f"[SIGNAL] enabled_markets={sorted(self._enabled_markets())}")
        print(f"[SIGNAL] express_mode={settings.express_mode}")

        for sport_key in sport_list:
            try:
                print(f"[FETCH] {sport_key} started")
                events = await self.odds.fetch_events_for_sport(sport_key)
                print(f"[FETCH] {sport_key} events={len(events)}")
            except Exception as error:
                print("[FETCH ERROR]", sport_key, repr(error))
                continue

            accepted = 0
            for event in events:
                hours = (event.commence_time - datetime.now(timezone.utc)).total_seconds() / 3600
                if not (-1 <= hours <= settings.max_hours_before_match):
                    continue
                all_events.append(event)
                accepted += 1

            print(f"[FILTER] {sport_key} accepted_by_time={accepted}")

        all_events.sort(key=lambda e: (self.event_day_rank(e.commence_time), e.commence_time))
        print(f"[ANALYZE] total_events={len(all_events)}")
        return all_events

    async def run_once(self):
        all_events = await self._fetch_events()

        if settings.express_mode:
            await self.run_express_once(all_events)
        else:
            await self.run_single_once(all_events)

    async def run_single_once(self, all_events):
        sent = 0
        today_count = await self.repo.daily_signal_count() if hasattr(self.repo, "daily_signal_count") else 0

        if today_count >= settings.max_signals_per_day:
            print(f"[LIMIT] daily max_signals_per_day reached: {today_count}/{settings.max_signals_per_day}")
            return

        for event in all_events:
            if sent >= settings.max_signals_per_scan:
                print(f"[LIMIT] scan max_signals_per_scan reached: {sent}/{settings.max_signals_per_scan}")
                break

            if today_count + sent >= settings.max_signals_per_day:
                print(f"[LIMIT] daily max_signals_per_day reached: {today_count + sent}/{settings.max_signals_per_day}")
                break

            best = await self.best_analysis_for_event(event)

            if best is None:
                print(f"[NO SIGNAL] {event.sport_key} | {event.home_team} vs {event.away_team}")
                continue

            if await self.repo.save_signal(best):
                sent += 1
                print(f"[SIGNAL SENT] {event.sport_key} | {event.home_team} vs {event.away_team} | {best.market_key} | {best.pick}")
                await self.notifier.send_signal(best, await self.explainer.explain(best))
            else:
                print(f"[DUPLICATE] {event.sport_key} | {event.home_team} vs {event.away_team}")

        print(f"[SIGNAL] finished sent={sent}")

    async def run_express_once(self, all_events):
        candidates = []
        today_count = await self.repo.daily_signal_count() if hasattr(self.repo, "daily_signal_count") else 0

        if today_count >= settings.max_signals_per_day:
            print(f"[EXPRESS LIMIT] daily max_signals_per_day reached: {today_count}/{settings.max_signals_per_day}")
            return

        for event in all_events:
            best = await self.best_analysis_for_event(event)
            if best is None:
                print(f"[EXPRESS NO LEG] {event.sport_key} | {event.home_team} vs {event.away_team}")
                continue

            if not self.passes_express(best):
                print(
                    f"[EXPRESS FILTERED] {best.sport_key} | {best.match_name} | "
                    f"conf={best.confidence} ai={best.ai_validator_score} edge={best.value_edge} "
                    f"anom={best.anomaly_score} odds={best.odds}"
                )
                continue

            if await self.repo.signal_exists(best):
                print(f"[EXPRESS DUPLICATE LEG] {best.sport_key} | {best.match_name} | {best.pick}")
                continue

            candidates.append(best)

        coupon = self.build_express_coupon(candidates)

        if not coupon:
            print(f"[EXPRESS] no coupon. candidates={len(candidates)}")
            return

        if today_count + len(coupon) > settings.max_signals_per_day:
            print(
                f"[EXPRESS LIMIT] daily limit would be exceeded: "
                f"{today_count}+{len(coupon)}>{settings.max_signals_per_day}"
            )
            return

        saved_legs = []
        for leg in coupon:
            if await self.repo.save_signal(leg):
                saved_legs.append(leg)

        if len(saved_legs) < settings.express_min_legs:
            print(f"[EXPRESS] not enough saved legs: {len(saved_legs)}/{settings.express_min_legs}")
            return

        print(
            f"[EXPRESS SENT] legs={len(saved_legs)} total_odds="
            f"{prod(float(x.odds) for x in saved_legs):.2f}"
        )
        await self.notifier.send_express(saved_legs)


class ResultTracker:
    def __init__(self, repo, notifier, api_sports):
        self.repo = repo
        self.notifier = notifier
        self.api_sports = api_sports

    async def run_once(self):
        for signal in await self.repo.pending_signals():
            api_id = await self.repo.get_event_link(signal["event_id"])
            payload = None
            sport_key = str(signal["sport_key"])

            if api_id and sport_key.startswith("basketball"):
                payload = await self.api_sports.basketball_result(api_id)
            elif api_id and sport_key.startswith("tennis"):
                payload = await self.api_sports.tennis_result(api_id)
            elif api_id and sport_key.startswith("soccer"):
                payload = await self.api_sports.soccer_result(api_id)

            status, text = evaluate_signal(signal, payload)

            if status in {"won", "lost", "void"}:
                signal_code = signal.get("signal_code") or f"SIG-{signal['id']:04d}"

                await self.repo.mark_signal(signal["id"], status, text)

                await self.notifier.send_result(
                    ("✅" if status == "won" else "❌" if status == "lost" else "↩️")
                    + f" NATIJA\n"
                    f"ID: {signal_code}\n"
                    f"Match: {signal['match_name']}\n"
                    f"Market: {signal['market_label']}\n"
                    f"Pick: {signal['pick']}\n"
                    f"{text}"
                )


class ReportService:
    def __init__(self, repo, notifier):
        self.repo = repo
        self.notifier = notifier

    async def run_once(self):
        return


class LiveService:
    def __init__(self, notifier):
        self.notifier = notifier

    async def run_once(self):
        return
