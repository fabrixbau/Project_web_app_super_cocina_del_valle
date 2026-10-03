from django import template

from accounts.roles import ADMIN, user_has_any_role
from public_portal.preview import PREVIEW_SESSION_KEY, PREVIEW_TIMES

register = template.Library()


@register.inclusion_tag("public_portal/_preview_switch.html", takes_context=True)
def public_preview_switch(context):
    """VISTA DE PRUEBA: selector de horario, visible sólo para administradores."""
    request = context.get("request")
    allowed = bool(request) and user_has_any_role(request.user, (ADMIN,))
    return {
        "allowed": allowed,
        "current": request.session.get(PREVIEW_SESSION_KEY, "") if allowed else "",
        "options": [(key, label, moment.strftime("%H:%M")) for key, (label, moment) in PREVIEW_TIMES.items()],
        "next": request.get_full_path() if allowed else "",
        "csrf_token": context.get("csrf_token"),
    }
