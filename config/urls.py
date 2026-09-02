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
from django.contrib.auth import views as auth_views
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "cuentas/iniciar-sesion/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("cuentas/", include("django.contrib.auth.urls")),
    path("app/perfil/", include("accounts.urls")),
    path("app/menu/", include("menu.urls")),
    path("app/mesas/", include("tables.urls")),
    path("app/pedidos/", include("orders.urls")),
    path("app/repartos/", include("orders.delivery_urls")),
    path("app/caja/", include("orders.cashier_urls")),
    path("app/notificaciones/", include("notifications.urls")),
    path("app/", include("internal_portal.urls")),
    path("pedir/", include("public_portal.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
