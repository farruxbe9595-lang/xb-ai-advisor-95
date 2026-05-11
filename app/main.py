import os
import asyncio
from dotenv import load_dotenv

if os.path.exists("/app/storage/signals.db"):
    os.remove("/app/storage/signals.db")
    print("signals.db deleted")
from app.config.settings import settings
from app.db.database import init_db
from app.db.repository import Repository
from app.telegram.notifier import TelegramNotifier
from app.telegram.commands import CommandBot
from app.data.api_sports import ApiSportsClient
from app.services.services import SignalService, ResultTracker, ReportService, LiveService


async def loop_forever(name, interval, fn):
    while True:
        try:
            print(f"[{name}] scan started")
            await fn()
            print(f"[{name}] scan finished. next in {interval}s")
        except Exception as e:
            print(name, "error:", repr(e))

        await asyncio.sleep(interval)


async def main():
    load_dotenv()
    await init_db(settings.db_path)

    repo = Repository(settings.db_path)
    notifier = TelegramNotifier(settings.bot_token, settings.group_id)

    api = ApiSportsClient(
        settings.api_sports_key,
        settings.api_sports_basketball_host,
        settings.api_sports_tennis_host,
        settings.api_sports_football_host
    )

    tasks = [
        loop_forever(
            "signal_loop",
            settings.scan_interval_seconds,
            SignalService(repo, notifier, api).run_once
        ),
        loop_forever(
            "result_loop",
            settings.result_interval_seconds,
            ResultTracker(repo, notifier, api).run_once
        ),
        loop_forever(
            "report_loop",
            3600,
            ReportService(repo, notifier).run_once
        ),
        CommandBot(repo).run()
    ]

    if settings.enable_live_engine:
        tasks.append(
            loop_forever(
                "live_loop",
                settings.live_scan_interval_seconds,
                LiveService(notifier).run_once
            )
        )

    print("XB AI Advisor 95 started.")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
