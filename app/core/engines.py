from app.config.settings import settings
from app.utils.math_utils import decimal_to_implied_probability, clamp, market_label
from app.models.domain import Analysis, Market, Outcome


def _as_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


class Anomaly:
    @staticmethod
    def score(current, previous, model):
        warnings = []
        score = 0

        current = _as_float(current)
        previous = _as_float(previous)

        if current and previous and previous > 1:
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

        if model < 52:
            score += 15
            warnings.append('Model ustunligi juda kichik.')

        return int(clamp(score, 0, 100)), warnings


class BacktestEngine:
    def __init__(self, repo):
        self.repo = repo

    async def market_adjustment(self, sport, market):
        try:
            rows = await self.repo.performance_by_market()
        except Exception as exc:
            return 0, f'Backtest o‘qishda xato: {repr(exc)}'

        for r in rows:
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
        bankroll = float(getattr(settings, 'bankroll', 1000.0) or 1000.0)
        base_pct = float(
            getattr(settings, 'base_stake_percent', None)
            or getattr(settings, 'stake_percent', 1.0)
            or 1.0
        )
        min_pct = float(getattr(settings, 'min_stake_percent', 0.2) or 0.2)
        max_pct = float(getattr(settings, 'max_stake_percent', 2.0) or 2.0)

        pl = await self.repo.daily_pl()
        losses = await self.repo.consecutive_losses()
        max_loss = bankroll * float(settings.daily_loss_limit_percent) / 100

        if pl <= -max_loss:
            return 0, 0, f'Kunlik zarar limiti oshdi: {pl}'

        if losses >= settings.max_consecutive_losses:
            return 0, 0, f'Ketma-ket {losses} zarar. Pauza.'

        pct = base_pct

        if conf >= 88:
            pct += 0.25
        elif conf < 78:
            pct -= 0.20

        if edge >= 10:
            pct += 0.20
        elif edge < 2:
            pct -= 0.15

        if anom >= 25:
            pct -= 0.40
        if anom >= 35:
            pct -= 0.35

        pct = clamp(pct, min_pct, max_pct)
        return round(bankroll * pct / 100, 2), round(pct, 2), 'Risk limiti normal.'


class Scorer:
    def __init__(self):
        self.min = settings.min_odds
        self.max = settings.max_odds

    async def analyze(self, event, market, outcome, previous, enrich, adj, note):
        implied = decimal_to_implied_probability(outcome.price)
        model = implied
        reasons = []
        warnings = []

        if self.min <= outcome.price <= self.max:
            model += 4
            reasons.append('Koeffitsient konservativ diapazonda.')
        else:
            model -= 6
            warnings.append('Koeffitsient tavsiya diapazonidan tashqarida.')

        data_quality = str(enrich.get('data_quality', 'odds_only'))
        if data_quality.startswith('api_sports_'):
            model += 4
            reasons.append('API-Sports mapping topildi.')
        else:
            model -= 2
            warnings.append(enrich.get('warning') or 'API-Sports mapping topilmadi.')

        if market.synthetic:
            model -= 10
            warnings.append('Synthetic market xavfli, ball pasaytirildi.')

        if market.key == 'h2h':
            if event.sport_key.startswith('tennis'):
                model += 5
            elif event.sport_key.startswith('basketball'):
                model += 3
            else:
                model += 2

        if market.key == 'spreads':
            model += 2
            reasons.append('Spread market qo‘shimcha xavf bilan baholandi.')

        if market.key == 'totals':
            if event.sport_key.startswith('basketball'):
                model += 1
                reasons.append('Basketbol total marketi ehtiyotkor baholandi.')
            else:
                model += 2

        if market.key == 'first_half_totals':
            model -= 2
            warnings.append('1-yarm total faqat qo‘shimcha/synthetic taxmin sifatida baholandi.')

        point = _as_float(outcome.point)
        if point is not None:
            reasons.append(f'Line: {point:g}')

            if market.key == 'totals' and event.sport_key.startswith('basketball'):
                pick = str(outcome.name).lower()
                if 'under' in pick and point < 215:
                    model -= 6
                    warnings.append('Basketbol Under line past: xavf oshirildi.')
                if 'over' in pick and point > 245:
                    model -= 5
                    warnings.append('Basketbol Over line juda yuqori: xavf oshirildi.')

        if adj:
            model += adj

        if note:
            reasons.append(note)

        model = clamp(model, 1, 90)
        edge = model - implied
        anom, anom_warnings = Anomaly.score(outcome.price, previous, model)
        warnings.extend(anom_warnings)

        conf = int(clamp(
            48 + (model - 50) * 1.05 + edge * 1.10 - anom * 0.35,
            1,
            92,
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
            warnings,
            market.bookmaker,
            data_quality,
            market.synthetic,
        )


def add_synthetic_half(event):
    if not event.sport_key.startswith('basketball') or any(m.key == 'first_half_totals' for m in event.markets):
        return

    for m in event.markets:
        if m.key == 'totals':
            for o in m.outcomes:
                point = _as_float(o.point)
                if point is not None and str(o.name).lower() in {'over', 'under'}:
                    event.markets.append(
                        Market(
                            'first_half_totals',
                            f'{m.bookmaker} / synthetic',
                            [Outcome(o.name, o.price, round(point * 0.505, 1))],
                            m.last_update,
                            True,
                        )
                    )
                    return


def evaluate_signal(signal, payload):
    if not payload:
        return 'pending', 'Natija hali topilmadi.'

    if payload.get('error'):
        return 'pending', f"Natija API xatosi: {payload.get('error')}"

    if payload.get('finished') is False:
        return 'pending', f"O‘yin hali tugamagan yoki natija tasdiqlanmagan. Status: {payload.get('status', 'unknown')}"

    market = signal['market_key']
    pick = str(signal['pick'])
    hs = payload.get('home_score')
    aw = payload.get('away_score')

    if market == 'h2h':
        winner = payload.get('winner')
        if not winner:
            return 'pending', f"Winner aniqlanmadi. Final: {hs}-{aw}."

        status = 'won' if _same_side(pick, winner) else 'lost'
        return status, f"Winner: {winner}. Final: {hs}-{aw}."

    if market in {'totals', 'first_half_totals'}:
        if market == 'first_half_totals':
            hs = payload.get('first_half_home')
            aw = payload.get('first_half_away')

        if hs is None or aw is None:
            return 'pending', 'Score yetishmayapti.'

        if signal.get('line') is None:
            return 'pending', 'Line topilmadi.'

        total = float(hs) + float(aw)
        line = float(signal['line'])
        p = pick.lower()

        if abs(total - line) < 0.0001:
            return 'void', f"Push/Void. Total: {total:g}. Line: {line:g}. Final: {hs}-{aw}."

        won = (total > line) if 'over' in p else (total < line)
        return ('won' if won else 'lost'), f"Total: {total:g}. Line: {line:g}. Final: {hs}-{aw}."

    if market == 'spreads':
        return _evaluate_spread(signal, payload)

    return 'pending', 'Market noma’lum.'


def _evaluate_spread(signal, payload):
    if signal.get('line') is None:
        return 'pending', 'Spread line topilmadi.'

    hs = payload.get('home_score')
    aw = payload.get('away_score')
    if hs is None or aw is None:
        return 'pending', 'Spread uchun final score yetishmayapti.'

    pick = str(signal['pick'])
    line = float(signal['line'])
    home = str(payload.get('home_team') or '')
    away = str(payload.get('away_team') or '')

    pick_is_home = _same_side(pick, home)
    pick_is_away = _same_side(pick, away)

    if not pick_is_home and not pick_is_away:
        match_name = str(signal.get('match_name') or '')
        if ' vs ' in match_name:
            mh, ma = match_name.split(' vs ', 1)
            pick_is_home = _same_side(pick, mh)
            pick_is_away = _same_side(pick, ma)

    if not pick_is_home and not pick_is_away:
        return 'void', f"Spread pick jamoa bilan moslanmadi. Pick: {pick}. Final: {hs}-{aw}."

    picked_score = float(hs if pick_is_home else aw)
    opp_score = float(aw if pick_is_home else hs)
    adjusted = picked_score + line

    if abs(adjusted - opp_score) < 0.0001:
        return 'void', f"Spread push. Adjusted: {adjusted:g}. Line: {line:g}. Final: {hs}-{aw}."

    won = adjusted > opp_score
    return ('won' if won else 'lost'), f"Spread adjusted: {adjusted:g} vs {opp_score:g}. Line: {line:g}. Final: {hs}-{aw}."


def _same_side(a, b):
    a = _clean_name(a)
    b = _clean_name(b)

    if not a or not b:
        return False

    return a == b or a in b or b in a or len(set(a.split()).intersection(set(b.split()))) >= 2


def _clean_name(x):
    cleaned = (
        str(x)
        .lower()
        .replace('.', ' ')
        .replace('-', ' ')
        .replace('_', ' ')
        .replace('  ', ' ')
        .strip()
    )
    drop = {'fc', 'cf', 'afc', 'bc', 'club'}
    return ' '.join(w for w in cleaned.split() if w not in drop)
