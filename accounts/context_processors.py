from django.contrib.auth import get_user_model

from .quick_switch import logged_in_today_ids
from .roles import ADMIN, WAITER, user_has_any_role


def quick_switch_context(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: el botón "Cambiar mesero" siempre está
    # disponible para cualquier mesero (nunca Administrador). Lista TODOS los
    # meseros activos, no sólo los que ya iniciaron sesión hoy: a un mesero que
    # aún no lo ha hecho, el mismo formulario le pide su contraseña real en vez
    # de un PIN (ver accounts/views.py:quick_switch). Borra esta nota.
    is_admin = bool(request.user.is_authenticated and user_has_any_role(request.user, (ADMIN,)))
    is_waiter = bool(
        request.user.is_authenticated
        and user_has_any_role(request.user, (WAITER,))
        and not is_admin
    )
    quick_waiters = []
    single_target = None
    today_ids = set()
    if is_waiter:
        today_ids = logged_in_today_ids(request.session)
        quick_waiters = list(get_user_model().objects.filter(
            is_active=True, groups__name=WAITER,
        ).exclude(pk=request.user.pk).distinct().order_by("first_name", "username"))
        if len(quick_waiters) == 1:
            single_target = quick_waiters[0]
    return {
        "quick_switch_available": is_waiter,
        "quick_switch_waiters": quick_waiters,
        "quick_switch_single_target": single_target,
        "quick_switch_today_ids": today_ids,
    }
