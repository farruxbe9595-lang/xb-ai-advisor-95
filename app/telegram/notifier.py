from telegram import Bot
from app.utils.html import esc

class TelegramNotifier:
    def __init__(self, token, group_id):
        self.enabled = bool(token and group_id)
        self.group_id = group_id
        self.bot = Bot(token=token) if token else None

    async def send_signal(self, a, explanation):
        if not self.enabled or self.bot is None:
            print("SIGNAL", a)
            return

        line = f"\n📏 <b>Line:</b> {esc(a.line)}" if a.line is not None else ""
        warnings = "\n".join("⚠️ " + esc(w) for w in a.warnings) if a.warnings else "✅ Katta shubhali anomaliya topilmadi"
        signal_code = getattr(a, "signal_code", "") or "NEW"

        text = f"""🎯 <b>AI SPORTS ADVISOR SIGNAL</b>

🆔 <b>Signal ID:</b> {esc(signal_code)}

🏟 <b>Sport:</b> {esc(a.sport_title)}
🆚 <b>Match:</b> {esc(a.match_name)}
⏰ <b>Start:</b> {esc(a.commence_time.strftime('%Y-%m-%d %H:%M UTC'))}

📌 <b>Market:</b> {esc(a.market_label)}
✅ <b>Pick:</b> {esc(a.pick)}{line}
💰 <b>Odds:</b> {a.odds:.2f}

🤖 <b>AI ehtimoli:</b> {a.model_probability:.1f}%
📊 <b>Implied probability:</b> {a.implied_probability:.1f}%
📈 <b>Value edge:</b> {a.value_edge:.1f}%
🔐 <b>Confidence:</b> {a.confidence}%
🧠 <b>AI validator:</b> {a.ai_validator_score}/100 — {esc(a.ai_validator_verdict)}
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
            parse_mode="HTML"
        )

    async def send_result(self, text):
        if not self.enabled or self.bot is None:
            print(text)
            return

        await self.bot.send_message(
            chat_id=self.group_id,
            text=esc(text),
            parse_mode="HTML"
        )

    async def send_plain(self, text):
        await self.send_result(text)
