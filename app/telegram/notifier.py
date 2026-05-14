from datetime import datetime, timedelta
from math import prod

from telegram import Bot

from app.config.settings import settings
from app.utils.html import esc


class TelegramNotifier:
    def __init__(self, token, group_id):
        token = token or settings.telegram_bot_token
        group_id = group_id or settings.telegram_chat_id
        self.enabled = bool(settings.bot_enabled and token and group_id)
        self.group_id = group_id
        self.bot = Bot(token=token) if token else None

    async def send_signal(self, a, explanation):
        if not self.enabled or self.bot is None:
            print('SIGNAL', a)
            print(explanation)
            return

        line = f"\n📏 <b>Line:</b> {esc(a.line)}" if a.line is not None else ''
        warnings = (
            '\n'.join('⚠️ ' + esc(w) for w in a.warnings)
            if a.warnings
            else '✅ Katta shubhali anomaliya topilmadi'
        )
        signal_code = getattr(a, 'signal_code', '') or 'NEW'
        uz_time = a.commence_time + timedelta(hours=settings.timezone_offset_hours)

        ai_validator_text = f'{a.ai_validator_score}/100 — {esc(a.ai_validator_verdict)}'
        if str(a.ai_validator_verdict).upper() in {'DISABLED', 'OFF'}:
            ai_validator_text = 'O‘chirilgan'

        title = '🛡 <b>AI SAFE SIGNAL</b>' if getattr(settings, 'safe_mode', False) else '🎯 <b>AI SPORTS ADVISOR SIGNAL</b>'

        text = f"""{title}

🆔 <b>Signal ID:</b> {esc(signal_code)}

🏟 <b>Sport:</b> {esc(a.sport_title)}
🆚 <b>Match:</b> {esc(a.match_name)}
⏰ <b>Start (UZT):</b> {esc(uz_time.strftime('%Y-%m-%d %H:%M'))}

📌 <b>Market:</b> {esc(a.market_label)}
✅ <b>Pick:</b> {esc(a.pick)}{line}
💰 <b>Odds:</b> {a.odds:.2f}

🤖 <b>AI ehtimoli:</b> {a.model_probability:.1f}%
📊 <b>Implied probability:</b> {a.implied_probability:.1f}%
📈 <b>Value edge:</b> {a.value_edge:.1f}%
🔐 <b>Confidence:</b> {a.confidence}%
🧠 <b>AI validator:</b> {ai_validator_text}
🚨 <b>Anomaly:</b> {a.anomaly_score}/100
🧪 <b>Data:</b> {esc(a.data_quality)}
💵 <b>Stake suggestion:</b> {a.stake_amount:.2f} ({a.stake_percent:.2f}% bankroll)

<b>AI izohi:</b>
{esc(explanation)}

<b>Risk filtri:</b>
{warnings}

<i>Avtomatik pul tikish emas. Yakuniy qaror operatorniki.</i>"""

        await self.bot.send_message(
            chat_id=self.group_id,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )

    async def send_express(self, legs):
        if not legs:
            return

        total_odds = prod(float(x.odds) for x in legs)
        avg_conf = sum(int(x.confidence) for x in legs) / len(legs)
        avg_ai = sum(int(x.ai_validator_score) for x in legs) / len(legs)
        max_anomaly = max(int(x.anomaly_score) for x in legs)
        stake_amount = settings.bankroll * settings.express_stake_percent / 100
        uz_now = datetime.utcnow() + timedelta(hours=settings.timezone_offset_hours)
        coupon_id = f"SAFE-{uz_now.strftime('%Y%m%d-%H%M')}" if getattr(settings, 'safe_mode', False) else f"EXP-{uz_now.strftime('%Y%m%d-%H%M')}"

        rows = []
        for i, a in enumerate(legs, start=1):
            uz_time = a.commence_time + timedelta(hours=settings.timezone_offset_hours)
            line = f" | Line: {a.line:g}" if a.line is not None else ""
            code = getattr(a, 'signal_code', '') or 'pending'
            rows.append(
                f"""<b>{i}) {esc(a.sport_title)}</b>
🆔 Leg ID: {esc(code)}
🆚 {esc(a.match_name)}
⏰ {esc(uz_time.strftime('%Y-%m-%d %H:%M'))}
📌 {esc(a.market_label)} | ✅ {esc(a.pick)}{esc(line)}
💰 Odds: <b>{a.odds:.2f}</b> | 🔐 Conf: {a.confidence}% | 🧠 AI: {a.ai_validator_score}/100 | 🚨 Anomaly: {a.anomaly_score}/100"""
            )

        title = "🛡 <b>AI SAFE EXPRESS</b>" if getattr(settings, 'safe_mode', False) else "🎯 <b>AI EXPRESS COUPON</b>"
        strategy = "Maqsad: katta koeffitsient emas, maksimal yutish ehtimoli." if getattr(settings, 'safe_mode', False) else "Maqsad: saralangan 2-leg express."

        text = f"""{title}

🧾 <b>Coupon ID:</b> {esc(coupon_id)}
🔢 <b>Legs:</b> {len(legs)}
💰 <b>Total odds:</b> {total_odds:.2f}
🔐 <b>Avg confidence:</b> {avg_conf:.1f}%
🧠 <b>Avg AI score:</b> {avg_ai:.1f}/100
🚨 <b>Max anomaly:</b> {max_anomaly}/100
💵 <b>Stake suggestion:</b> {stake_amount:.2f} ({settings.express_stake_percent:.2f}% bankroll)
🧭 <b>Strategy:</b> {esc(strategy)}

""" + "\n\n".join(rows) + """

<b>SAFE EXPRESS qoidasi:</b>
✅ Faqat konservativ market
✅ Kichik odds = yuqori ehtimol
✅ Past anomaly
✅ 2 ta o‘yin maksimum
✅ Totals marketdan qochiladi

<i>Bu avtomatik pul tikish emas. Yakuniy qaror operatorniki.</i>"""

        if not self.enabled or self.bot is None:
            print(text)
            return

        await self.bot.send_message(
            chat_id=self.group_id,
            text=text,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )

    async def send_result(self, text):
        if not self.enabled or self.bot is None:
            print(text)
            return

        await self.bot.send_message(
            chat_id=self.group_id,
            text=esc(text),
            parse_mode='HTML',
            disable_web_page_preview=True,
        )

    async def send_plain(self, text):
        await self.send_result(text)
