# NOTA TEMPORAL PARA APRENDIZAJE:
# Un context processor agrega datos a todas las plantillas internas. Aquí construimos los
# enlaces permitidos para el usuario actual sin repetir lógica en cada vista. Borra la nota.

from django.urls import reverse

from accounts.roles import SECTION_ROLE_MATRIX, user_has_any_role

from .navigation import SECTIONS


def internal_navigation(request):
    if not request.user.is_authenticated:
        return {"internal_navigation_sections": ()}
    sections = []
    for section in SECTIONS:
        if not user_has_any_role(request.user, SECTION_ROLE_MATRIX[section["key"]]):
            continue
        url = reverse(section["url_name"])
        sections.append({**section, "url": url, "is_active": request.path.startswith(url)})
    return {"internal_navigation_sections": sections}
