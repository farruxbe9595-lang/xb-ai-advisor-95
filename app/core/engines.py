from app.config.settings import settings
from app.utils.math_utils import decimal_to_implied_probability, clamp, market_label
from app.models.domain import Analysis, Market, Outcome


class Anomaly:
    @staticmethod
    def score(current, previous, model):
        warnings = []
        score = 0

        if previous and previous > 1:
            ch = abs(current - previous) / previous * 100

            if ch >= 18:
                score += 45
                warnings.append(f'Koeffitsient juda keskin o‘zgargan: {previous:.2f} → {current:.2f}')
            elif ch >= 10:
                score += 25
                warnings.append(f'Koeffitsient sezilarli o‘zgargan: {previous:.2f} → {current:.2f}')
            elif ch >= 6:
                score += 12
                warnings.append(f'Koeffitsient o‘zgarishi kuzatildi: {previous:.2f} → {current:.2f}')

        if model < 58:
            score += 20
            warnings.append('Model ehtimoli past.')

        return int(clamp(score, 0, 100)), warnings


class BacktestEngine:
    def __init__(self, repo):
        self.repo = repo

    async def market_adjustment(self, sport, market):
        for r in await self.repo.performance_by_market():
            if r['sport_key'] == sport and r['market_key'] == market:
                total = r['total'] or 0
                won = r['won'] or 0

                if total < 10:
                    return 0, 'Backtest sample hali kam.'

                hit = won / total * 100

                if hit >= 65:
                    return 3, f'Backtest ijobiy: {hit:.1f}%.'
                if hit <= 48:
                    return -5, f'Backtest salbiy: {hit:.1f}%.'

                return 0, f'Backtest neytral: {hit:.1f}%.'

        return 0, 'Backtest ma’lumoti hali yo‘q.'


class RiskEngine:
    def __init__(self, repo):
        self.repo = repo

    async def suggest(self, conf, edge, anom):
        pl = await self.repo.daily_pl()
        losses = await self.repo.consecutive_losses()
        max_loss = settings.bankroll * settings.daily_loss_limit_percent / 100

        if pl <= -max_loss:
            return 0, 0, f'Kunlik zarar limiti oshdi: {pl}'

        if losses >= settings.max_consecutive_losses:
            return 0, 0, f'Ketma-ket {losses} zarar. Pauza.'

        pct = settings.base_stake_percent
        if conf >= 88:
            pct += 0.25
        if edge >= 10:
            pct += 0.20
        if anom >= 25:
            pct -= 0.40

        pct = clamp(pct, 0.2, settings.max_stake_percent)
        return round(settings.bankroll * pct / 100, 2), round(pct, 2), 'Risk limiti normal.'


class Scorer:
    def __init__(self):
        self.min = settings.min_odds
        self.max = settings.max_odds

    async def analyze(self, event, market, outcome, previous, enrich, adj, note):
        implied = decimal_to_implied_probability(outcome.price)
        model = implied
        reasons = []

        if self.min <= outcome.price <= self.max:
            model += 4
            reasons.append('Koeffitsient konservativ diapazonda.')

        if enrich.get('data_quality') == 'odds_plus_api_sports':
            model += 4
            reasons.append('API-Sports mapping topildi.')
        else:
            reasons.append('API-Sports mapping topilmadi.')

        if market.synthetic:
            model -= 8
            reasons.append('Synthetic market xavfli, ball pasaytirildi.')

        if market.key == 'h2h':
            model += 5 if event.sport_key.startswith('tennis') else 3

        if market.key == 'totals':
            if event.sport_key.startswith('basketball'):
                model += 2
                reasons.append('Basketbol total marketi ehtiyotkor baholandi.')
            else:
                model += 3

        if market.key == 'first_half_totals':
            model += 1

        if market.key == 'spreads':
            model += 3

        if outcome.point is not None:
            reasons.append(f'Line: {outcome.point:g}')

            if market.key == 'totals' and event.sport_key.startswith('basketball'):
                if outcome.name.lower() == 'under' and float(outcome.point) < 215:
                    model -= 6
                    reasons.append('NBA Under line past: xavf oshirildi.')

        if adj:
            model += adj

        reasons.append(note)

        model = clamp(model, 1, 90)
        edge = model - implied
        anom, warn = Anomaly.score(outcome.price, previous, model)

        conf = int(clamp(
            48 + (model - 50) * 1.05 + edge * 1.10 - anom * 0.35,
            1,
            92
        ))

        risk = 'Past/o‘rtacha' if conf >= 84 and anom < 30 else 'O‘rtacha' if conf >= 78 else 'Yuqori'

        return Analysis(
            event.event_id,
            event.sport_key,
            event.sport_title,
            f'{event.home_team} vs {event.away_team}',
            event.commence_time,
            market.key,
            market_label(market.key),
            outcome.name,
            outcome.price,
            outcome.point,
            round(implied, 2),
            round(model, 2),
            round(edge, 2),
            conf,
            anom,
            risk,
            reasons,
            warn,
            market.bookmaker,
            enrich.get('data_quality', 'odds_only'),
            market.synthetic
        )


def add_synthetic_half(event):
    if not event.sport_key.startswith('basketball') or any(m.key == 'first_half_totals' for m in event.markets):
        return

    for m in event.markets:
        if m.key == 'totals':
            for o in m.outcomes:
                if o.point is not None and o.name.lower() in {'over', 'under'}:
                    event.markets.append(
                        Market(
                            'first_half_totals',
                            f'{m.bookmaker} / synthetic',
                            [Outcome(o.name, o.price, round(float(o.point) * 0.505, 1))],
                            m.last_update,
                            True
                        )
                    )
                    return


def evaluate_signal(signal, payload):
    if not payload:
        return 'pending', 'Natija hali topilmadi.'

    market = signal['market_key']
    pick = str(signal['pick'])
    hs = payload.get('home_score')
    aw = payload.get('away_score')

    if market == 'h2h':
        winner = payload.get('winner')
        status = 'won' if winner and (
            pick.lower() in str(winner).lower()
            or str(winner).lower() in pick.lower()
        ) else 'lost'
        return status, f"Winner: {winner}. Final: {hs}-{aw}."

    if market in {'totals', 'first_half_totals'}:
        if market == 'first_half_totals':
            hs = payload.get('first_half_home')
            aw = payload.get('first_half_away')

        if hs is None or aw is None:
            return 'pending', 'Score yetishmayapti.'

        total = int(hs) + int(aw)
        line = float(signal['line'])
        p = pick.lower()

        won = (total > line) if 'over' in p else (total < line)
        return ('won' if won else 'lost'), f"Total: {total}. Line: {line}. Final: {hs}-{aw}."

    if market == 'spreads':
        return 'void', f"Spread natija qo‘lda tekshiriladi. Final: {hs}-{aw}."

    return 'pending', 'Market noma’lum.'
