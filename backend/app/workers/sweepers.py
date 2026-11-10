"""Sweepers runner — stuck-event + retention loops; hooks for connectivity/escalation."""

from __future__ import annotations

import logging
import time

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sweepers")


def _try_connectivity() -> int:
    """ConnectivitySweeper.run (commits its own work)."""
    try:
        from app.iot.connectivity_sweeper import ConnectivitySweeper
        from app.persistence.pg.session import SessionLocal

        db = SessionLocal()
        try:
            return int(ConnectivitySweeper(db).run())
        finally:
            db.close()
    except Exception as exc:
        log.debug("connectivity_sweeper_unavailable: %s", exc)
        return 0


def _try_escalation() -> int:
    """Vritika plugs EscalationTimer.run here."""
    try:
        from app.alerts.escalation_timer import EscalationTimer  # type: ignore
        from app.persistence.pg.session import SessionLocal

        db = SessionLocal()
        try:
            return int(EscalationTimer(db).run())
        finally:
            db.close()
    except Exception as exc:
        log.debug("escalation_timer_unavailable: %s", exc)
        return 0


def _run_stuck() -> dict[str, int]:
    from app.persistence.jobs.stuck_event_sweeper import StuckEventSweeper
    from app.persistence.pg.session import SessionLocal

    db = SessionLocal()
    try:
        result = StuckEventSweeper(db).run()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_retention() -> dict:
    from app.persistence.jobs.retention_job import RetentionJob
    from app.persistence.pg.session import SessionLocal

    db = SessionLocal()
    try:
        result = RetentionJob(db).run()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main(
    *,
    sleep_sec: float = 60.0,
    retention_every: int = 1440,
    stop_after: int | None = None,
) -> None:
    """Run forever (or stop_after iterations for tests)."""
    log.info("sweepers started")
    ticks = 0
    while True:
        try:
            conn = _try_connectivity()
            esc = _try_escalation()
            stuck = _run_stuck()
            log.info("tick connectivity=%s escalation=%s stuck=%s", conn, esc, stuck)
            if ticks % retention_every == 0:
                ret = _run_retention()
                log.info("retention=%s", ret)
        except Exception:
            log.exception("sweeper_tick_failed")
        ticks += 1
        if stop_after is not None and ticks >= stop_after:
            break
        time.sleep(sleep_sec)


if __name__ == "__main__":
    main()
