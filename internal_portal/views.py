# NOTA TEMPORAL PARA APRENDIZAJE:
# La tarjeta Repartos ahora abre el panel operativo en lugar del placeholder.
# La tarjeta Pedidos del dashboard ahora apunta al listado real de la app orders.
# Borra esta nota después de comprobar el acceso.

from django.urls import reverse
from django.shortcuts import render

from accounts.roles import OPERATIONAL_ROLES, SECTION_ROLE_MATRIX, role_required, user_has_any_role


SECTIONS = (
    {"key": "tables", "title": "Mesas", "description": "Atención y cuentas de mesas.", "url_name": "internal_portal:tables"},
    {"key": "orders", "title": "Pedidos", "description": "Pedidos internos y externos.", "url_name": "orders:order_list"},
    {"key": "deliveries", "title": "Repartos", "description": "Asignación y seguimiento de entregas.", "url_name": "deliveries:delivery_board"},
    {"key": "reports", "title": "Reportes", "description": "Información administrativa.", "url_name": "internal_portal:reports"},
    {"key": "menu", "title": "Menú", "description": "Categorías y productos.", "url_name": "menu:configuration"},
)


@role_required(*OPERATIONAL_ROLES)
def dashboard(request):
    role_names = list(request.user.groups.order_by("name").values_list("name", flat=True))
    allowed_sections = [
        {**section, "url": reverse(section["url_name"])}
        for section in SECTIONS
        if user_has_any_role(request.user, SECTION_ROLE_MATRIX[section["key"]])
    ]
    return render(
        request,
        "internal_portal/dashboard.html",
        {"role_names": role_names, "allowed_sections": allowed_sections},
    )


def _render_section(request, *, title, description):
    return render(
        request,
        "internal_portal/section_placeholder.html",
        {"title": title, "description": description},
    )


@role_required(*SECTION_ROLE_MATRIX["tables"])
def tables(request):
    return _render_section(request, title="Mesas", description="Aquí construiremos la operación de mesas.")


@role_required(*SECTION_ROLE_MATRIX["orders"])
def orders(request):
    return _render_section(request, title="Pedidos", description="Aquí construiremos la captura y seguimiento de pedidos.")


@role_required(*SECTION_ROLE_MATRIX["deliveries"])
def deliveries(request):
    return _render_section(request, title="Repartos", description="Aquí construiremos la asignación y entrega de pedidos.")


@role_required(*SECTION_ROLE_MATRIX["reports"])
def reports(request):
    return _render_section(request, title="Reportes", description="Esta sección será exclusiva de administración.")
