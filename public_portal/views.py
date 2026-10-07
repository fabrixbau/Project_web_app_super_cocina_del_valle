from datetime import time

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.csrf import csrf_failure as django_csrf_failure
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.roles import ADMIN, role_required
from orders.cart import cart_control_summary, get_order_mode

from .preview import PREVIEW_SESSION_KEY, PREVIEW_TIMES

CHECKOUT_DRAFT_SESSION_KEY = "public_checkout_draft"
# Datos de Finalizar pedido que se conservan si el envío se rechaza por el código de seguridad.
CHECKOUT_DRAFT_FIELDS = (
    "customer_first_name", "customer_last_name", "phone", "street", "exterior_number",
    "interior_number", "references", "notes", "schedule", "requested_time",
    "payment_method", "cash_bill", "cash_custom_amount", "pays_exact",
)
STALE_PAGE_MESSAGE = "La página estuvo abierta mucho tiempo; revisa tus datos y vuelve a enviar."


QR_MENU_CATEGORY_ORDER = ("Desayunos", "Plancha", "Bebidas calientes", "Bebidas frías", "Postres")
QR_MENU_DAILY_WATER_CATEGORY = "Bebidas frías"
QR_MENU_DAILY_SERVICE_NOTE = "Servicio de comida del día a partir de la 1:00 p. m."
QR_MENU_NOTE = (
    "El menú está sujeto a disponibilidad. Los precios pueden cambiar sin previo aviso; "
    "cualquier cambio en un platillo puede modificar su precio."
)


def qr_menu(request):
    """Carta del QR (supercocina.win/menu/): sólo consulta, sin pedidos.

    Muestra los productos con "Mostrar en menú QR" que estén disponibles, por categoría en el
    orden acordado, y al inicio de Bebidas frías el "Agua del día" con el sabor de hoy.
    """
    from django.utils import timezone

    from menu.models import DailyMenu, Product

    products = Product.objects.filter(show_in_qr_menu=True, is_available=True).select_related("category").order_by(
        "category__name", "sort_order", "name",
    )
    sections = {}
    for product in products:
        sections.setdefault(product.category.name, []).append(product)
    ordered = [name for name in QR_MENU_CATEGORY_ORDER if name in sections]
    ordered += sorted(name for name in sections if name not in QR_MENU_CATEGORY_ORDER)

    today_menu = DailyMenu.objects.filter(
        date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
    ).select_related("water_product").first()
    water = today_menu.water_product if today_menu else None
    concept = Product.objects.filter(name__iexact="Agua del día").order_by("pk").first()
    daily_water = {
        "name": "Agua del día",
        "today": water.name if water else "",
        "price": water.price if water else (concept.price if concept else None),
    }
    # Menú del día al final de la carta: se actualiza solo con lo que se publique hoy.
    from menu.catalog import public_daily_menu
    from menu.models import MealPackage

    published_menu, daily_groups = public_daily_menu()
    packages = {package.package_type: package for package in MealPackage.objects.filter(is_active=True)}
    daily_section = {
        "menu": published_menu,
        "groups": [
            {"title": "Guisados del día" if group["title"] == "Guisados" else group["title"], "products": group["products"]}
            for group in daily_groups
        ],
        "running": packages.get(MealPackage.PackageType.RUNNING),
        "executive": packages.get(MealPackage.PackageType.EXECUTIVE),
        "service_note": QR_MENU_DAILY_SERVICE_NOTE,
    }
    if QR_MENU_DAILY_WATER_CATEGORY not in ordered:
        ordered.insert(min(len(ordered), QR_MENU_CATEGORY_ORDER.index(QR_MENU_DAILY_WATER_CATEGORY)), QR_MENU_DAILY_WATER_CATEGORY)
    return render(request, "public_portal/qr_menu.html", {
        "sections": [{"name": name, "slug": f"cat-{index}", "products": sections.get(name, [])} for index, name in enumerate(ordered, start=1)],
        "daily_water": daily_water,
        "daily_section": daily_section,
        "daily_water_category": QR_MENU_DAILY_WATER_CATEGORY,
        "note": QR_MENU_NOTE,
        "whatsapp_url": WHATSAPP_URL, "whatsapp_label": WHATSAPP_LABEL,
        "address_label": ADDRESS_LABEL, "maps_url": MAPS_URL,
    })


def csrf_failure(request, reason=""):
    """Código de seguridad vencido en /pedir/: regresar a la página con un aviso amable.

    En Finalizar pedido se guardan en la sesión los datos escritos (nunca el código) para
    volver a llenar el formulario. Fuera de /pedir/ se usa la página normal de Django.
    """
    if not request.path.startswith("/pedir/"):
        return django_csrf_failure(request, reason=reason)
    if request.headers.get("x-requested-with") == "XMLHttpRequest" or "application/json" in request.headers.get("accept", ""):
        # El JS recarga la página (con un código nuevo) y ahí se ve el aviso.
        messages.warning(request, STALE_PAGE_MESSAGE)
        return JsonResponse({"ok": False, "error": STALE_PAGE_MESSAGE, "reload": True}, status=403)
    if request.path.rstrip("/").endswith("/finalizar"):
        request.session[CHECKOUT_DRAFT_SESSION_KEY] = {
            name: request.POST.get(name, "") for name in CHECKOUT_DRAFT_FIELDS if request.POST.get(name)
        }
    messages.warning(request, STALE_PAGE_MESSAGE)
    return redirect(request.path if url_has_allowed_host_and_scheme(request.path, allowed_hosts={request.get_host()}) else "/pedir/")


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
