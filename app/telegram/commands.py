from telegram.ext import Application, CommandHandler
from app.config.settings import settings
class CommandBot:
    def __init__(self,repo): self.repo=repo
    async def stats(self,u,c):
        s=await self.repo.stats_summary(); await u.message.reply_text(f"📊 Pending:{s.get('pending',0)} Won:{s.get('won',0)} Lost:{s.get('lost',0)}")
    async def performance(self,u,c):
        rows=await self.repo.performance_by_market(); lines=['📈 Performance']
        for r in rows[:10]:
            total=r['total'] or 0; won=r['won'] or 0; hit=won/total*100 if total else 0; lines.append(f"{r['sport_key']} / {r['market_key']}: {hit:.1f}% ({won}/{total})")
        await u.message.reply_text('\n'.join(lines) if len(lines)>1 else 'Hali statistika yo‘q.')
    async def risk(self,u,c): await u.message.reply_text(f"Daily P/L: {await self.repo.daily_pl()}\nConsecutive losses: {await self.repo.consecutive_losses()}")
    async def help(self,u,c): await u.message.reply_text('/stats\n/performance\n/risk\n/help')
    async def run(self):
        if not settings.bot_token: return
        app=Application.builder().token(settings.bot_token).build()
        app.add_handler(CommandHandler('stats',self.stats)); app.add_handler(CommandHandler('performance',self.performance)); app.add_handler(CommandHandler('risk',self.risk)); app.add_handler(CommandHandler('help',self.help))
        await app.initialize(); await app.start(); await app.updater.start_polling()
