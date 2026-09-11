from django.contrib.auth import get_user_model

from .quick_switch import quick_switch_is_trusted
from .roles import ADMIN, WAITER, user_has_any_role


def quick_switch_context(request):
    is_admin = bool(request.user.is_authenticated and user_has_any_role(request.user, (ADMIN,)))
    is_waiter = bool(
        request.user.is_authenticated
        and user_has_any_role(request.user, (WAITER,))
        and not is_admin
    )
    available = bool(
        is_waiter
        and quick_switch_is_trusted(request.session)
    )
    has_pin = bool(
        request.user.is_authenticated
        and hasattr(request.user, "profile")
        and request.user.profile.has_quick_pin
    )
    quick_waiters = []
    single_target = None
    if available:
        quick_waiters = list(get_user_model().objects.filter(
            is_active=True, groups__name=WAITER, profile__quick_pin_hash__gt="",
        ).exclude(pk=request.user.pk).distinct().order_by("first_name", "username"))
        if len(quick_waiters) == 1:
            single_target = quick_waiters[0]
    return {
        "quick_switch_available": available,
        "current_user_has_quick_pin": has_pin,
        "current_user_is_waiter": is_waiter,
        "quick_switch_waiters": quick_waiters,
        "quick_switch_single_target": single_target,
    }
