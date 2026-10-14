import logging
from datetime import datetime, timedelta

from apscheduler.jobstores.base import JobLookupError
from apscheduler.schedulers.background import BackgroundScheduler

from app import i18n
from app.core import auth
from app.core.database import user_session
from app.models.schemas import get_setting
from app.services.exchange_rates import sync_exchange_rates
from app.services.mail.sync import sync_mail_now
from app.services.recurrence import materialize_due

logger = logging.getLogger("scheduler")
scheduler = BackgroundScheduler()

MAIL_JOB = "mail_sync"  # one job per user: mail_sync:<user_id>
RATES_JOB = "exchange_rates_sync"
RATES_RETRY_JOB = "exchange_rates_retry"
RECURRING_JOB = "recurring_movements"
RATES_RETRY_DELAY = timedelta(hours=1)  # after a failed download, instead of waiting for the daily run
MIN_MAIL_INTERVAL = 5


def _mail_job_id(user_id: int) -> str:
    return f"{MAIL_JOB}:{user_id}"


def _active_user(user_id: int):
    user = auth.get_user(user_id)
    return user if user and user.is_active else None


def _user_language(db) -> str:
    """The language the user chose in Settings: what jobs save (e.g. the last sync result) is shown to them later."""
    return get_setting(db, "language")


def _mail_job(user_id: int):
    user = _active_user(user_id)
    if not user:
        return
    db = user_session(user_id)
    try:
        if get_setting(db, "mail_sync_enabled", "false").lower() == "true":
            with i18n.use(_user_language(db)):
                res = sync_mail_now(db)
            logger.info(f"Scheduled mail sync ({user.username}): {res.get('new_transactions', 0)} new, "
                        f"success={res.get('success')}")
    except Exception:
        logger.exception(f"Scheduled mail sync failed ({user.username})")
    finally:
        db.close()


def _rates_job():
    """Every active user's database gets the rates; each series is downloaded only once per run."""
    fetched = {}
    failed = False
    for user in auth.list_users():
        if not user.is_active:
            continue
        db = user_session(user.id)
        try:
            with i18n.use(_user_language(db)):
                failed |= not sync_exchange_rates(db, fetched)["success"]
        except Exception:
            failed = True
            logger.exception(f"Exchange rates sync failed ({user.username})")
        finally:
            db.close()
    if failed:
        # e.g. the NAS booted before the network was up, or mindicador was down
        scheduler.add_job(_rates_job, "date", run_date=datetime.now() + RATES_RETRY_DELAY,
                          id=RATES_RETRY_JOB, replace_existing=True)
        logger.info("Exchange rates: retrying in 1 hour")


def _recurring_job():
    """Creates the recurring movements due today (and any missed while the NAS was off) for every active user."""
    for user in auth.list_users():
        if not user.is_active:
            continue
        db = user_session(user.id)
        try:
            created = materialize_due(db)
            if created:
                logger.info(f"Recurring transactions ({user.username}): {created} created")
        except Exception:
            db.rollback()
            logger.exception(f"Creating recurring transactions failed ({user.username})")
        finally:
            db.close()


def sync_rates_for_user(user_id: int):
    """Background download for one user (after a CSV import that needs past years' rates)."""
    db = user_session(user_id)
    try:
        with i18n.use(_user_language(db)):
            sync_exchange_rates(db)
    except Exception:
        logger.exception(f"Exchange rates sync failed (user {user_id})")
    finally:
        db.close()


def next_rates_run():
    """Next automatic rates download (a pending retry comes before the daily run)."""
    if not scheduler.running:
        return None
    times = [job.next_run_time for job in (scheduler.get_job(RATES_RETRY_JOB), scheduler.get_job(RATES_JOB))
             if job and job.next_run_time]
    return min(times).strftime("%Y-%m-%d %H:%M") if times else None


def mail_interval_minutes(user_id: int) -> int:
    db = user_session(user_id)
    try:
        return max(int(get_setting(db, "mail_sync_interval_mins", "30") or 30), MIN_MAIL_INTERVAL)
    except ValueError:
        return 30
    finally:
        db.close()


def reschedule_mail(user_id: int):
    """Applies the interval stored in the user's settings (after they change it, or the user is created/reactivated)."""
    if not _active_user(user_id):
        remove_mail_job(user_id)
        return
    scheduler.add_job(_mail_job, "interval", args=[user_id], minutes=mail_interval_minutes(user_id),
                      id=_mail_job_id(user_id), replace_existing=True)


def remove_mail_job(user_id: int):
    try:
        scheduler.remove_job(_mail_job_id(user_id))
    except JobLookupError:
        pass


def next_mail_run(user_id: int):
    job = scheduler.get_job(_mail_job_id(user_id)) if scheduler.running else None
    return job.next_run_time.strftime("%Y-%m-%d %H:%M") if job and job.next_run_time else None


def start_scheduler():
    for user in auth.list_users():
        if user.is_active:
            reschedule_mail(user.id)
    scheduler.add_job(_rates_job, "interval", hours=24, id=RATES_JOB, replace_existing=True)
    scheduler.add_job(_rates_job, id="initial_exchange_rates_sync", replace_existing=True)  # once, at boot
    scheduler.add_job(_recurring_job, "cron", hour=0, minute=5, id=RECURRING_JOB, replace_existing=True)
    scheduler.add_job(_recurring_job, id="initial_recurring_movements", replace_existing=True)  # once, at boot
    if not scheduler.running:
        scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
