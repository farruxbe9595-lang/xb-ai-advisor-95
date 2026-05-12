import asyncio
import os
from dotenv import load_dotenv

# .env ni eng boshida yuklaymiz. Railway env variables baribir ustun turadi.
load_dotenv()

from app.config.settings import settings
from app.db.database import init_db
from app.db.repository import Repository
from app.telegram.notifier import TelegramNotifier
from app.telegram.commands import CommandBot
from app.data.api_sports import ApiSportsClient
from app.services.services import SignalService, ResultTracker, ReportService, LiveService


async def loop_forever(name, interval, fn):
    interval = max(int(interval or 60), 30)

    while True:
        try:
            print(f"[{name}] scan started")
            await fn()
            print(f"[{name}] scan finished. next in {interval}s")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[{name}] error: {repr(e)}")

        await asyncio.sleep(interval)


async def main():
    db_dir = os.path.dirname(settings.db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # MUHIM: bu yerda eski signals.db o'chirilmaydi.
    # Railway restart/deploy bo'lsa ham tarix, pending signal va backtest saqlanadi.
    await init_db(settings.db_path)

    repo = Repository(settings.db_path)
    notifier = TelegramNotifier(settings.bot_token, settings.group_id)

    api = ApiSportsClient(
        settings.api_sports_key,
        settings.api_sports_basketball_host,
        settings.api_sports_tennis_host,
        settings.api_sports_football_host,
    )

    tasks = [
        loop_forever(
            "signal_loop",
            settings.scan_interval_seconds,
            SignalService(repo, notifier, api).run_once,
        ),
        loop_forever(
            "result_loop",
            settings.result_interval_seconds,
            ResultTracker(repo, notifier, api).run_once,
        ),
        loop_forever(
            "report_loop",
            3600,
            ReportService(repo, notifier).run_once,
        ),
        CommandBot(repo).run(),
    ]

    if settings.enable_live_engine:
        tasks.append(
            loop_forever(
                "live_loop",
                settings.live_scan_interval_seconds,
                LiveService(notifier).run_once,
            )
        )

    print("XB AI Advisor 95 started.")
    print(f"DB_PATH={settings.db_path}")
    print(f"SPORT_KEYS={settings.sport_keys}")
    print(f"ODDS_MARKETS={settings.odds_markets}")
    print(f"ENABLE_AI_VALIDATOR={settings.enable_ai_validator}")
    print(f"ENABLE_SPREADS_MARKET={settings.enable_spreads_market}")

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
