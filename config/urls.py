# NOTA TEMPORAL PARA APRENDIZAJE:
# `/app/repartos/` conecta el nuevo panel real antes del portal interno general.
# `/app/mesas/` carga el mapa y las cuentas activas del nuevo módulo de mesas.
# `/app/pedidos/` ahora carga el listado real de orders antes del portal interno general.
# `/app/notificaciones/` carga la bandeja interna de alertas. Borra esta nota.
# Conectamos `/app/menu/` con el módulo de menú y servimos imágenes en desarrollo.
# En producción las imágenes serán responsabilidad del servidor web. Borra esta nota al terminar.

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from accounts.views import login_view
from public_portal.views import qr_menu


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "cuentas/iniciar-sesion/",
        login_view,
        name="login",
    ),
    path("cuentas/login/", login_view, name="account_login"),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("app/perfil/", include("accounts.urls")),
    path("app/menu/", include("menu.urls")),
    path("app/mesas/", include("tables.urls")),
    path("app/pedidos/", include("orders.urls")),
    path("app/repartos/", include("orders.delivery_urls")),
    path("app/caja/", include("orders.cashier_urls")),
    path("app/notificaciones/", include("notifications.urls")),
    path("app/impresion/", include("print_station.urls")),
    path("app/", include("internal_portal.urls")),
    path("pedir/", include("public_portal.urls")),
    # Carta del QR: menú fijo de consulta (sin pedidos).
    path("menu/", qr_menu, name="qr_menu"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
