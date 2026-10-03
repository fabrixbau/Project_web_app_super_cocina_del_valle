from datetime import time

from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, role_required
from orders.cart import cart_control_summary, get_order_mode

from .preview import PREVIEW_SESSION_KEY, PREVIEW_TIMES

WHATSAPP_URL = "https://wa.me/525619048431"
WHATSAPP_LABEL = "+52 56 1904 8431"
ADDRESS_LABEL = "Adolfo Prieto 1047, Col. del Valle Centro"
MAPS_URL = "https://maps.app.goo.gl/6MV2THKnzs2Q3voG8"


def home(request):
    # Primera pantalla del cliente (pizarra verde y dorado): saludo según la hora, elegir
    # Recoger o Entrega (cada opción abre el menú con la modalidad en la URL), vista previa
    # del menú del día, horario, WhatsApp y dirección. Si hay un pedido en curso se ofrece
    # continuarlo.
    from menu.catalog import public_daily_menu

    from .preview import public_time

    now = public_time(request.session)
    if now < time(12, 0):
        greeting = "Buenos días"
    elif now < time(19, 0):
        greeting = "Buenas tardes"
    else:
        greeting = "Buenas noches"
    daily_menu, daily_groups = public_daily_menu()
    return render(request, "public_portal/home.html", {
        "current_mode": get_order_mode(request.session),
        "cart_count": cart_control_summary(request.session)["count"],
        "greeting": greeting,
        "daily_menu": daily_menu,
        "daily_groups": daily_groups,
        "whatsapp_url": WHATSAPP_URL,
        "whatsapp_label": WHATSAPP_LABEL,
        "address_label": ADDRESS_LABEL,
        "maps_url": MAPS_URL,
    })


@role_required(ADMIN)
@require_POST
def preview_time(request):
    """VISTA DE PRUEBA: el administrador simula la hora del portal (o vuelve a la real)."""
    choice = request.POST.get("time", "")
    if choice in PREVIEW_TIMES:
        request.session[PREVIEW_SESSION_KEY] = choice
    else:
        request.session.pop(PREVIEW_SESSION_KEY, None)
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}) or not next_url.startswith("/pedir/"):
        next_url = "/pedir/menu/"
    return redirect(next_url)
