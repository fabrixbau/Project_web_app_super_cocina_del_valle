# NOTA TEMPORAL PARA APRENDIZAJE:
# El cambio rápido autentica realmente al mesero elegido. La tablet debe estar habilitada con
# contraseña completa antes de aceptar PIN y conserva la URL de trabajo. Borra esta nota.

from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import EmployeeLoginForm, QuickPinSetupForm, QuickSwitchForm
from .models import Profile
from .quick_switch import LOCK_KEY, enable_quick_switch, quick_switch_is_trusted
from .roles import ADMIN, WAITER, user_has_any_role


def login_view(request):
    if request.user.is_authenticated:
        return redirect("internal_portal:dashboard")

    form = EmployeeLoginForm(request.POST or None, request=request)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user(), backend="django.contrib.auth.backends.ModelBackend")
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


def _can_use_waiter_pin(user):
    """El PIN rápido pertenece a meseros, nunca a cuentas administrativas."""
    return user_has_any_role(user, (WAITER,)) and not user_has_any_role(user, (ADMIN,))


def _safe_next(request):
    next_url = request.POST.get("next") or request.GET.get("next") or reverse("tables:table_map")
    return next_url if url_has_allowed_host_and_scheme(next_url, {request.get_host()}) else reverse("tables:table_map")


@login_required
def quick_pin_setup(request):
    if not _can_use_waiter_pin(request.user):
        messages.error(request, "El cambio rápido está disponible solamente para meseros.")
        return redirect("internal_portal:dashboard")
    form = QuickPinSetupForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        profile, _ = Profile.objects.get_or_create(user=request.user)
        if form.cleaned_data.get("pin"):
            profile.set_quick_pin(form.cleaned_data["pin"])
            profile.save(update_fields=("quick_pin_hash", "pin_failed_attempts", "pin_locked_until"))
        enable_quick_switch(request.session)
        messages.success(request, "Esta tablet tiene cambio rápido habilitado por 12 horas.")
        return redirect(_safe_next(request))
    return render(request, "accounts/quick_pin_setup.html", {"form": form, "next": _safe_next(request), "has_existing_pin": form.has_existing_pin})


@login_required
def quick_switch(request):
    if not _can_use_waiter_pin(request.user):
        messages.error(request, "El cambio rápido está disponible solamente para meseros.")
        return redirect("internal_portal:dashboard")
    if not quick_switch_is_trusted(request.session):
        messages.error(request, "Primero configura tu PIN para habilitar esta tablet.")
        return redirect("accounts:quick_pin_setup")
    waiters = get_user_model().objects.filter(is_active=True, groups__name=WAITER).select_related("profile").distinct().order_by("first_name", "username")
    form = QuickSwitchForm(request.POST or None)
    next_url = _safe_next(request)
    inline_request = request.POST.get("inline") == "1"
    if request.method == "POST" and form.is_valid():
        waiter = waiters.filter(pk=form.cleaned_data["waiter_id"]).first()
        if not waiter:
            form.add_error(None, "El mesero seleccionado ya no está disponible.")
        else:
            with transaction.atomic():
                profile, _ = Profile.objects.select_for_update().get_or_create(user=waiter)
                if not profile.has_quick_pin:
                    form.add_error("pin", "Este mesero todavía no ha configurado su PIN.")
                if profile.pin_is_locked:
                    form.add_error("pin", "Este perfil está bloqueado temporalmente por varios intentos.")
                elif not profile.check_quick_pin(form.cleaned_data["pin"]):
                    profile.pin_failed_attempts += 1
                    if profile.pin_failed_attempts >= 5:
                        profile.pin_locked_until = timezone.now() + timedelta(minutes=5)
                        profile.pin_failed_attempts = 0
                    profile.save(update_fields=("pin_failed_attempts", "pin_locked_until"))
                    form.add_error("pin", "PIN incorrecto.")
                else:
                    profile.pin_failed_attempts = 0
                    profile.pin_locked_until = None
                    profile.save(update_fields=("pin_failed_attempts", "pin_locked_until"))
                    login(request, waiter, backend="django.contrib.auth.backends.ModelBackend")
                    enable_quick_switch(request.session)
                    messages.success(request, f"Ahora está operando {waiter.get_full_name() or waiter.username}.")
                    return redirect(next_url)
    if request.method == "POST" and inline_request:
        errors = [
            error["message"]
            for field_errors in form.errors.get_json_data().values()
            for error in field_errors
        ]
        messages.error(request, " ".join(errors) or "No fue posible cambiar de mesero.")
        return redirect(next_url)
    return render(request, "accounts/quick_switch.html", {"form": form, "waiters": waiters, "next": next_url})


@require_POST
@login_required
def quick_lock(request):
    if not _can_use_waiter_pin(request.user):
        messages.error(request, "El bloqueo por PIN está disponible solamente para meseros.")
        return redirect("internal_portal:dashboard")
    if quick_switch_is_trusted(request.session):
        request.session[LOCK_KEY] = True
        request.session.modified = True
    return redirect(f"{reverse('accounts:quick_switch')}?{urlencode({'next': _safe_next(request)})}")
