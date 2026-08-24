from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    role_names = list(request.user.groups.order_by("name").values_list("name", flat=True))
    return render(request, "internal_portal/dashboard.html", {"role_names": role_names})
