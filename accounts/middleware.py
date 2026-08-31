from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

from .quick_switch import LOCK_KEY, TRUST_KEY, enable_quick_switch, quick_switch_is_trusted
from .roles import WAITER


class QuickSwitchLockMiddleware:
    """Impide operar rutas internas cuando la tablet fue bloqueada por inactividad."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # NOTA TEMPORAL PARA APRENDIZAJE:
        # El PIN pertenece al perfil y permanece en la base de datos. Tras un inicio de sesión
        # normal habilitamos la sesión nueva sin pedir que el mesero vuelva a crearlo. Borra esta nota.
        if (
            request.user.is_authenticated
            and TRUST_KEY not in request.session
            and request.user.groups.filter(name=WAITER).exists()
            and hasattr(request.user, "profile")
            and request.user.profile.has_quick_pin
        ):
            enable_quick_switch(request.session)
        exempt_prefix = "/app/perfil/cambio-rapido/"
        if (
            request.path.startswith("/app/")
            and not request.path.startswith(exempt_prefix)
            and request.user.is_authenticated
            and quick_switch_is_trusted(request.session)
            and request.session.get(LOCK_KEY)
        ):
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('accounts:quick_switch')}?{query}")
        return self.get_response(request)
