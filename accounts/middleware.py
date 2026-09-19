from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

from .quick_switch import LOCK_KEY
from .roles import ADMIN, WAITER


class QuickSwitchLockMiddleware:
    """Impide operar rutas internas cuando la tablet fue bloqueada por inactividad."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # NOTA TEMPORAL PARA APRENDIZAJE:
        # El registro de "quién inició sesión hoy" ya se hace en accounts.views.login_view
        # y accounts.views.quick_switch justo después de login(); este middleware ya no
        # necesita habilitar nada por su cuenta, sólo aplicar el bloqueo por inactividad
        # a cualquier mesero (nunca a Administrador). Borra esta nota después de leerla.
        exempt_prefix = "/app/perfil/cambio-rapido/"
        if (
            request.path.startswith("/app/")
            and not request.path.startswith(exempt_prefix)
            and request.user.is_authenticated
            and request.user.groups.filter(name=WAITER).exists()
            and not request.user.is_superuser
            and not request.user.groups.filter(name=ADMIN).exists()
            and request.session.get(LOCK_KEY)
        ):
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('accounts:quick_switch')}?{query}")
        return self.get_response(request)
