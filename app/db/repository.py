async def save_signal(self, a):
    if await self.signal_exists(a):
        return False

    async with aiosqlite.connect(self.db_path) as db:
        cur = await db.execute(
            '''
            INSERT INTO signals(
                signal_code,
                event_id, sport_key, sport_title, match_name, commence_time,
                market_key, market_label, pick, odds, line,
                implied_probability, model_probability, value_edge,
                confidence, anomaly_score, risk_level, bookmaker,
                reasons, warnings, data_quality, synthetic,
                ai_validator_score, ai_validator_verdict,
                stake_amount, stake_percent, status, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''',
            (
                None,
                a.event_id, a.sport_key, a.sport_title, a.match_name,
                a.commence_time.isoformat(), a.market_key, a.market_label,
                a.pick, a.odds, a.line, a.implied_probability,
                a.model_probability, a.value_edge, a.confidence,
                a.anomaly_score, a.risk_level, a.bookmaker,
                json.dumps(a.reasons, ensure_ascii=False),
                json.dumps(a.warnings, ensure_ascii=False),
                a.data_quality, 1 if a.synthetic else 0,
                a.ai_validator_score, a.ai_validator_verdict,
                a.stake_amount, a.stake_percent,
                "pending", datetime.now(timezone.utc).isoformat()
            )
        )

        signal_id = cur.lastrowid

        prefix = (
            a.sport_key.upper()
            .replace("BASKETBALL_", "")
            .replace("TENNIS_", "")
        )
        date_code = datetime.now(timezone.utc).strftime("%Y%m%d")
        signal_code = f"{prefix}-{date_code}-{signal_id:04d}"

        await db.execute(
            "UPDATE signals SET signal_code=? WHERE id=?",
            (signal_code, signal_id)
        )

        await db.commit()

        a.signal_code = signal_code
        return True
