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
    path("app/", include("internal_portal.urls")),
    path("pedir/", include("public_portal.urls")),
]
