from django.shortcuts import render

from orders.cart import cart_control_summary, get_order_mode


def home(request):
    # Primera pantalla del cliente: elegir Recoger o Entrega. Cada opción abre el menú
    # con la modalidad en la URL; si ya había un pedido en curso se ofrece continuarlo.
    return render(request, "public_portal/home.html", {
        "current_mode": get_order_mode(request.session),
        "cart_count": cart_control_summary(request.session)["count"],
    })
