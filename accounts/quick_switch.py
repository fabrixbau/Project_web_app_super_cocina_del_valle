from datetime import datetime, timedelta

from django.utils import timezone


TRUST_HOURS = 12
IDLE_SECONDS = 180
TRUST_KEY = "quick_switch_trusted_until"
LOCK_KEY = "quick_switch_locked"


def enable_quick_switch(session):
    session[TRUST_KEY] = (timezone.now() + timedelta(hours=TRUST_HOURS)).isoformat()
    session[LOCK_KEY] = False
    session.modified = True


def quick_switch_is_trusted(session):
    raw_value = session.get(TRUST_KEY)
    if not raw_value:
        return False
    try:
        trusted_until = datetime.fromisoformat(raw_value)
        if timezone.is_naive(trusted_until):
            trusted_until = timezone.make_aware(trusted_until)
        return trusted_until > timezone.now()
    except (TypeError, ValueError):
        return False
