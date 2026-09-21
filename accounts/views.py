# NOTA TEMPORAL PARA APRENDIZAJE:
# El cambio rápido autentica realmente al mesero elegido, sin PIN: sólo puede
# recibirse hacia un mesero que ya inició sesión con su contraseña hoy en esta
# tablet (accounts/quick_switch.py). Conserva la URL de trabajo. Borra esta nota.

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import EmployeeLoginForm, QuickSwitchForm
from .quick_switch import LOCK_KEY, logged_in_today_ids, restore_daily_logins, snapshot_daily_logins
from .roles import ADMIN, WAITER, user_has_any_role


def login_view(request):
    if request.user.is_authenticated:
        return redirect("internal_portal:dashboard")

    form = EmployeeLoginForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if _can_quick_switch(user):
            _complete_quick_switch(request, user)
        else:
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect(_safe_next(request) if request.POST.get("next") else "internal_portal:dashboard")

    role_presentations = {
        "Administrador": ("Administrador", "Acceso completo al sistema", "🛡"),
        "Telefonista": ("Telefonista", "Captura y gestión de pedidos", "☎"),
        "Mesero": ("Mesero", "Atención y operación de mesas", "🍽"),
        "Repartidor": ("Repartidor", "Consulta y entrega de pedidos", "🛵"),
    }
    profiles = []
    users = get_user_model().objects.filter(is_active=True).select_related("profile").prefetch_related("groups").order_by("first_name", "username")
    for user in users:
        role_name = "Administrador" if user.is_superuser else next((group.name for group in user.groups.all() if group.name in role_presentations), "Empleado")
        role, description, icon = role_presentations.get(role_name, (role_name, "Acceso al sistema", "●"))
        initials = "".join(part[:1] for part in (user.first_name, user.last_name) if part).upper() or user.username[:2].upper()
        profiles.append({"user": user, "profile": getattr(user, "profile", None), "role": role, "description": description, "icon": icon, "initials": initials})
    return render(request, "registration/login.html", {"form": form, "login_profiles": profiles, "selected_user_id": request.POST.get("user", ""), "next": request.GET.get("next", "")})


def _can_quick_switch(user):
    """El cambio rápido pertenece a meseros, nunca a cuentas administrativas."""
    return user_has_any_role(user, (WAITER,)) and not user_has_any_role(user, (ADMIN,))


def _safe_next(request):
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("tables:table_map")
    return next_url if url_has_allowed_host_and_scheme(next_url, {request.get_host()}) else reverse("tables:table_map")


def _complete_quick_switch(request, waiter):
    snapshot = snapshot_daily_logins(request.session)
    login(request, waiter, backend="django.contrib.auth.backends.ModelBackend")
    restore_daily_logins(request.session, snapshot, user_id=waiter.pk)


@login_required
def quick_switch(request):
    # NOTA TEMPORAL PARA APRENDIZAJE: cambiar hacia un mesero que ya inició sesión
    # hoy en esta tablet es instantáneo, sin pedir nada. Cambiar hacia uno que
    # todavía no lo ha hecho pide su contraseña real (nunca un PIN) como su único
    # inicio de sesión del día; a partir de ahí también queda "sin PIN" el resto
    # del día. Esta misma pantalla aparece sola cuando la tablet se bloquea por
    # inactividad. Borra esta nota después de leerla.
    if not _can_quick_switch(request.user):
        messages.error(request, "El cambio rápido está disponible solamente para meseros.")
        return redirect("internal_portal:dashboard")
    today_ids = logged_in_today_ids(request.session)
    waiters = get_user_model().objects.filter(
        is_active=True, groups__name=WAITER,
    ).order_by("first_name", "username")
    form = QuickSwitchForm(request.POST or None)
    next_url = _safe_next(request)
    inline_request = request.POST.get("inline") == "1"
    if request.method == "POST" and form.is_valid():
        waiter = waiters.filter(pk=form.cleaned_data["waiter_id"]).first()
        if not waiter:
            form.add_error(None, "El mesero seleccionado ya no está disponible.")
        elif waiter.pk in today_ids:
            _complete_quick_switch(request, waiter)
            return redirect(next_url)
        else:
            password = form.cleaned_data.get("password")
            if not password:
                form.add_error("password", "Escribe tu contraseña; es tu primer inicio de sesión de hoy en esta tablet.")
            elif authenticate(request, username=waiter.username, password=password) is None:
                form.add_error("password", "La contraseña no es correcta.")
            else:
                _complete_quick_switch(request, waiter)
                return redirect(next_url)
    if request.method == "POST" and inline_request:
        errors = [
            error["message"]
            for field_errors in form.errors.get_json_data().values()
            for error in field_errors
        ]
        messages.error(request, " ".join(errors) or "No fue posible cambiar de mesero.")
        return redirect(next_url)
    return render(request, "accounts/quick_switch.html", {
        "form": form, "waiters": waiters, "next": next_url, "today_ids": today_ids,
    })


@require_POST
@login_required
def quick_lock(request):
    if not _can_quick_switch(request.user):
        messages.error(request, "El bloqueo de tablet está disponible solamente para meseros.")
        return redirect("internal_portal:dashboard")
    request.session[LOCK_KEY] = True
    request.session.modified = True
    return redirect(f"{reverse('accounts:quick_switch')}?{urlencode({'next': _safe_next(request)})}")
