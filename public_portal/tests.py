import json
from datetime import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from menu.forms import ProductForm
from menu.models import Category, DailyMenu, DailyProductStock, MealPackage, Product
from orders.cart import cart_control_summary, product_is_orderable
from orders.forms import InternalPackageForm, PackageCartForm, PublicCheckoutForm
from orders.models import OrderItem


class PublicPortalAccessTests(TestCase):
    def test_public_home_does_not_require_login(self):
        response = self.client.get(reverse("public_portal:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/app/")


class PublicOrderModeTests(TestCase):
    def test_home_offers_both_modes_linking_to_menu(self):
        response = self.client.get(reverse("public_portal:home"))
        menu_url = reverse("public_portal:menu")
        self.assertContains(response, f"{menu_url}?modalidad=pickup")
        self.assertContains(response, f"{menu_url}?modalidad=delivery")

    def test_menu_saves_mode_from_url_and_cleans_it(self):
        response = self.client.get(reverse("public_portal:menu"), {"modalidad": "delivery"})
        self.assertRedirects(response, reverse("public_portal:menu"), fetch_redirect_response=False)
        self.assertEqual(self.client.session["public_order_mode"], "delivery")
        self.assertEqual(self.client.get(reverse("public_portal:menu")).status_code, 200)

    def test_menu_without_mode_returns_to_home(self):
        response = self.client.get(reverse("public_portal:menu"))
        self.assertRedirects(response, reverse("public_portal:home"), fetch_redirect_response=False)

    def test_old_mode_page_no_longer_exists(self):
        with self.assertRaises(NoReverseMatch):
            reverse("public_portal:order_mode")
        self.assertEqual(self.client.get("/pedir/modalidad/").status_code, 404)


class CustomerVisibilityTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Antojitos")
        self.visible = Product.objects.create(category=self.category, name="Sope visible", price=Decimal("30.00"))
        self.hidden = Product.objects.create(
            category=self.category, name="Gordita oculta", price=Decimal("35.00"), show_to_customers=False,
        )

    def test_existing_products_default_to_visible(self):
        self.assertTrue(Product.objects.create(category=self.category, name="Nuevo", price=1).show_to_customers)

    def test_hidden_product_is_not_in_public_menu_nor_orderable(self):
        session = self.client.session
        session["public_order_mode"] = "pickup"
        session.save()
        response = self.client.get(reverse("public_portal:menu"))
        self.assertNotContains(response, "Gordita oculta")
        self.assertFalse(product_is_orderable(self.hidden))
        add = self.client.post(
            reverse("public_portal:product_add", args=(self.hidden.pk,)), {"quantity": 1},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(add.status_code, 400)

    def test_admin_toggles_visibility_from_menu_card(self):
        admin = get_user_model().objects.create_superuser(username="visibilidad_admin", password="x")
        self.client.force_login(admin)
        page = self.client.get(reverse("menu:configuration"))
        self.assertContains(page, reverse("menu:product_toggle_customer_visibility", args=(self.visible.pk,)))
        self.client.post(reverse("menu:product_toggle_customer_visibility", args=(self.visible.pk,)))
        self.visible.refresh_from_db()
        self.assertFalse(self.visible.show_to_customers)

    def test_new_product_form_requires_customer_visibility_answer(self):
        data = {
            "category": self.category.pk, "name": "Tlacoyo", "price": "25", "component_type": "general",
            "packaging_kind": "none", "sort_order": 0, "image_position_x": 50, "image_position_y": 50,
            "image_zoom": 1, "is_available": "on", "is_sold_individually": "on",
        }
        form = ProductForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("show_to_customers", form.errors)
        form = ProductForm({**data, "show_to_customers": "no"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertFalse(form.save().show_to_customers)
        # Al editar, la pregunta llega contestada con el valor actual.
        self.assertEqual(ProductForm(instance=self.visible)["show_to_customers"].value(), "yes")

    def test_hidden_component_disappears_only_from_public_package(self):
        consomme = Product.objects.create(category=self.category, name="Consomé", price=0, component_type="chicken_consomme")
        soup = Product.objects.create(category=self.category, name="Sopa oculta", price=0, component_type="variable_first_course", show_to_customers=False)
        rice = Product.objects.create(category=self.category, name="Arroz", price=0, component_type="second_course")
        stew = Product.objects.create(category=self.category, name="Guisado", price=0, component_type="beef_stew")
        menu = DailyMenu.objects.create(
            date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED, chicken_consomme=consomme,
            variable_first_course=soup, second_course_one=rice,
        )
        menu.set_stews([stew])
        package = MealPackage.objects.get(package_type=MealPackage.PackageType.RUNNING)
        public = PackageCartForm(package=package, daily_menu=menu, customers_only=True)
        labels = [choice.choice_label for choice in public["first_course"]]
        self.assertEqual(labels, ["Consomé"])
        internal = InternalPackageForm(package=package, daily_menu=menu)
        self.assertIn(soup, internal.fields["first_course"].queryset)


class CartAjaxMessagesTests(TestCase):
    """Los botones del ticket (AJAX) no deben dejar avisos acumulados para otra pantalla."""

    def setUp(self):
        category = Category.objects.create(name="Postres caseros")
        self.product = Product.objects.create(category=category, name="Flan", price=Decimal("25.00"))
        session = self.client.session
        session["public_order_mode"] = "pickup"
        session.save()

    def test_removing_from_ticket_does_not_queue_messages(self):
        ajax = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        with patch("orders.views.product_is_orderable", return_value=True), \
                patch("orders.cart.product_is_orderable", return_value=True):
            added = self.client.post(reverse("public_portal:product_add", args=(self.product.pk,)), {"quantity": 2}, **ajax)
            key = added.json()["cart"]["items"][0]["key"]
            self.client.post(reverse("public_portal:cart_update", args=(key,)), {"quantity": 1}, **ajax)
            self.client.post(reverse("public_portal:cart_remove", args=(key,)), **ajax)
            response = self.client.get(reverse("public_portal:menu"))
        self.assertNotContains(response, "La partida fue eliminada")
        self.assertNotContains(response, "La cantidad fue actualizada")


class PublicPackageBuilderTests(TestCase):
    """Comidas de 3 o 2 tiempos (primero + guisado o segundo + guisado) y varias a la vez."""

    def setUp(self):
        category = Category.objects.create(name="Comida del día")
        make = lambda name, kind: Product.objects.create(category=category, name=name, price=0, component_type=kind)
        self.consomme = make("Consomé", "chicken_consomme")
        self.rice = make("Arroz", "second_course")
        self.stew = make("Res en salsa", "beef_stew")
        self.menu = DailyMenu.objects.create(
            date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED,
            chicken_consomme=self.consomme, second_course_one=self.rice,
        )
        self.menu.set_stews([self.stew])
        self.package = MealPackage.objects.get(package_type=MealPackage.PackageType.RUNNING)
        for product in (self.consomme, self.rice, self.stew):
            DailyProductStock.objects.create(
                date=timezone.localdate(), product=product, daily_menu=self.menu,
                channel=DailyProductStock.Channel.ORDERS, initial_quantity=20,
            )
        DailyProductStock.objects.create(
            date=timezone.localdate(), item_kind=DailyProductStock.ItemKind.TORTILLAS,
            channel=DailyProductStock.Channel.ORDERS, initial_quantity=20,
        )
        session = self.client.session
        session["public_order_mode"] = "pickup"
        session.save()

    def form(self, **data):
        base = {"main_course": self.stew.pk, "tortillas": "yes", "beans": "no", "quantity": 1}
        return PackageCartForm({**base, **data}, package=self.package, daily_menu=self.menu, customers_only=True)

    def test_two_course_combinations_are_detected(self):
        three = self.form(first_course=self.consomme.pk, second_course=self.rice.pk)
        self.assertTrue(three.is_valid(), three.errors)
        self.assertFalse(three.cleaned_data["two_course"])
        for course in ({"first_course": self.consomme.pk}, {"second_course": self.rice.pk}):
            two = self.form(**course)
            self.assertTrue(two.is_valid(), two.errors)
            self.assertTrue(two.cleaned_data["two_course"])
        self.assertFalse(self.form().is_valid())  # sólo guisado: no es un paquete válido

    def test_batch_adds_several_meals_and_order_keeps_two_course(self):
        fields = lambda extra: [["main_course", str(self.stew.pk)], ["tortillas", "yes"], ["beans", "no"], ["quantity", "1"], *extra]
        batch = [
            {"fields": fields([["first_course", str(self.consomme.pk)], ["second_course", str(self.rice.pk)], ["with_water", "on"]]), "quantity": 2},
            {"fields": fields([["second_course", str(self.rice.pk)]]), "quantity": 1},
        ]
        response = self.client.post(
            reverse("public_portal:package_selection", args=("running",)), {"package_batch": json.dumps(batch)},
        )
        self.assertRedirects(response, reverse("public_portal:menu"), fetch_redirect_response=False)
        cart = cart_control_summary(self.client.session)
        self.assertEqual(cart["count"], 3)
        details = [item["detail"] for item in cart["items"]]
        self.assertTrue(any(detail.startswith("2 tiempos") and "Arroz" in detail and "Consomé" not in detail for detail in details))
        self.assertTrue(any("con agua" in detail and "con tortillas" in detail for detail in details))

        response = self.client.post(reverse("public_portal:checkout"), {
            "customer_first_name": "Ana", "customer_last_name": "López", "phone": "5512345678", "notes": "",
        })
        self.assertEqual(response.status_code, 302, response.context and response.context["form"].errors)
        items = OrderItem.objects.filter(item_type=OrderItem.ItemType.PACKAGE)
        two_course = items.get(is_two_course=True)
        self.assertIsNone(two_course.first_course)
        self.assertEqual(two_course.second_course, self.rice)
        self.assertEqual(items.get(is_two_course=False).quantity, 2)

    def test_stale_csrf_on_checkout_returns_with_data(self):
        from django.test import Client
        self.client.get(reverse("public_portal:menu") + "?modalidad=pickup")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.cookies = self.client.cookies
        response = csrf_client.post(reverse("public_portal:checkout"), {
            "csrfmiddlewaretoken": "viejo", "customer_first_name": "Ana", "phone": "5512345678",
        })
        self.assertRedirects(response, reverse("public_portal:checkout"), fetch_redirect_response=False)
        self.assertEqual(csrf_client.session["public_checkout_draft"]["customer_first_name"], "Ana")
        self.assertNotIn("csrfmiddlewaretoken", csrf_client.session["public_checkout_draft"])
        internal = Client(enforce_csrf_checks=True).post("/app/pedidos/clientes/nuevo/", {"name": "x"})
        self.assertEqual(internal.status_code, 403)

    def test_add_and_go_to_checkout(self):
        batch = [{"fields": [["first_course", str(self.consomme.pk)], ["main_course", str(self.stew.pk)], ["tortillas", "yes"], ["beans", "no"], ["quantity", "1"]], "quantity": 1}]
        response = self.client.post(
            reverse("public_portal:package_selection", args=("running",)),
            {"package_batch": json.dumps(batch), "next": "checkout"},
        )
        self.assertRedirects(response, reverse("public_portal:checkout"), fetch_redirect_response=False)
        self.assertEqual(cart_control_summary(self.client.session)["count"], 1)

    def test_invalid_meal_in_batch_adds_nothing(self):
        batch = [{"fields": [["main_course", str(self.stew.pk)], ["tortillas", "yes"], ["beans", "no"], ["quantity", "1"]], "quantity": 1}]
        response = self.client.post(
            reverse("public_portal:package_selection", args=("running",)), {"package_batch": json.dumps(batch)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(cart_control_summary(self.client.session)["count"], 0)


class DailyBoardExecutiveTests(TestCase):
    def test_board_shows_three_fixed_grill_options_and_the_rest_behind_more(self):
        category = Category.objects.create(name="Plancha")
        for index in range(7):
            Product.objects.create(
                category=category, name=f"Plancha {index}", price=0,
                component_type=Product.ComponentType.GRILL, eligible_for_executive_meal=True,
            )
        Product.objects.create(category=category, name="Plancha oculta", price=0, component_type=Product.ComponentType.GRILL,
                               eligible_for_executive_meal=True, show_to_customers=False)
        stew = Product.objects.create(category=category, name="Guisado", price=0, component_type="beef_stew")
        DailyMenu.objects.create(date=timezone.localdate(), status=DailyMenu.Status.PUBLISHED).set_stews([stew])
        session = self.client.session
        session["public_order_mode"] = "delivery"
        session.save()
        first = self.client.get(reverse("public_portal:menu"))
        second = self.client.get(reverse("public_portal:menu"))
        featured = [product.pk for product in first.context["executive_featured"]]
        self.assertEqual(len(featured), 3)
        self.assertEqual(featured, [product.pk for product in second.context["executive_featured"]])
        self.assertEqual(len(first.context["executive_more"]), 4)
        self.assertContains(first, "+4 opciones más")
        self.assertContains(first, 'data-pp-board-select="executive"')
        self.assertNotContains(first, "Plancha oculta")


class PreviewTimeSwitchTests(TestCase):
    """VISTA DE PRUEBA: sólo un administrador simula la hora del portal."""

    def setUp(self):
        session = self.client.session
        session["public_order_mode"] = "pickup"
        session.save()

    def test_customers_do_not_see_nor_use_the_switch(self):
        response = self.client.get(reverse("public_portal:menu"))
        self.assertNotContains(response, "Vista de prueba")
        response = self.client.post(reverse("public_portal:preview_time"), {"time": "breakfast"})
        self.assertFalse(response.get("Location", "").startswith("/pedir/"))  # lo manda a iniciar sesión
        self.assertNotIn("public_preview_time", self.client.session)

    def test_admin_switches_between_breakfast_and_lunch(self):
        admin = get_user_model().objects.create_superuser(username="preview_admin", password="x")
        self.client.force_login(admin)
        session = self.client.session
        session["public_order_mode"] = "pickup"
        session.save()
        self.assertContains(self.client.get(reverse("public_portal:menu")), "Vista de prueba")
        for choice, mode in (("breakfast", "breakfast"), ("lunch", "lunch")):
            response = self.client.post(reverse("public_portal:preview_time"), {"time": choice, "next": "/pedir/menu/"})
            self.assertRedirects(response, "/pedir/menu/", fetch_redirect_response=False)
            self.assertEqual(self.client.get(reverse("public_portal:menu")).context["public_menu_mode"], mode)
        self.client.post(reverse("public_portal:preview_time"), {"time": ""})
        self.assertNotIn("public_preview_time", self.client.session)


class BreakfastCategoryAndScheduleTests(TestCase):
    """Menú único: Desayunos primero hasta las 12:30 y oculto después; hora solicitada sólo hoy."""

    def setUp(self):
        self.breakfast = Category.objects.create(name="Desayunos", show_on_public_breakfast=True, show_on_public_lunch=False, public_lunch_order=0)
        self.drinks = Category.objects.create(name="Bebidas", show_on_public_breakfast=True, show_on_public_lunch=True, public_lunch_order=1)
        Product.objects.create(category=self.breakfast, name="Hot cakes", price=Decimal("50"))
        Product.objects.create(category=self.drinks, name="Café", price=Decimal("25"))
        session = self.client.session
        session["public_order_mode"] = "pickup"
        session.save()

    def menu_at(self, moment):
        with patch("public_portal.preview.public_time", return_value=moment):
            return self.client.get(reverse("public_portal:menu"))

    def test_breakfast_category_goes_first_in_the_morning_and_hides_after(self):
        morning = self.menu_at(time(9, 0))
        self.assertEqual([c.name for c in morning.context["categories"]], ["Desayunos", "Bebidas"])
        self.assertContains(morning, "Nuestro menú")
        afternoon = self.menu_at(time(14, 0))
        self.assertEqual([c.name for c in afternoon.context["categories"]], ["Bebidas"])
        self.assertNotContains(afternoon, "Hot cakes")

    def test_slots_every_15_minutes_and_lunch_starts_at_one(self):
        slots = PublicCheckoutForm.available_slots(time(8, 7), time(13, 0))
        self.assertEqual(slots[0], time(13, 0))
        self.assertEqual(slots[1], time(13, 15))
        self.assertEqual(slots[-1], time(18, 0))
        self.assertEqual(PublicCheckoutForm.available_slots(time(8, 7))[0], time(8, 45))
        # Antes de abrir se ofrece desde las 8:30; a las 10:00 ya no salen 8 ni 9.
        self.assertEqual(PublicCheckoutForm.available_slots(time(6, 0))[0], time(8, 30))
        self.assertEqual(PublicCheckoutForm.available_slots(time(10, 0))[0], time(10, 30))
        self.assertEqual(PublicCheckoutForm.available_slots(time(6, 0), time(13, 0))[0], time(13, 0))
        self.assertEqual(PublicCheckoutForm.available_slots(time(17, 40)), [])

    def test_checkout_form_keeps_requested_time_only_when_chosen(self):
        base = {"customer_first_name": "Ana", "customer_last_name": "Ruiz", "phone": "5511112222"}
        make = lambda data: PublicCheckoutForm(data, cart_total=Decimal("70"), order_type="pickup", now=time(9, 0), earliest=time(13, 0))
        chosen = make({**base, "schedule": "later", "requested_time": "15:15"})
        self.assertTrue(chosen.is_valid(), chosen.errors)
        self.assertEqual(chosen.cleaned_data["requested_time"], time(15, 15))
        self.assertEqual(timezone.localtime(chosen.cleaned_data["requested_for"]).time(), time(15, 15))
        asap = make({**base, "schedule": "asap", "requested_time": "08:00"})
        self.assertTrue(asap.is_valid(), asap.errors)
        self.assertIsNone(asap.cleaned_data["requested_for"])
        too_early = make({**base, "schedule": "later", "requested_time": "10:00"})
        self.assertFalse(too_early.is_valid())
        self.assertIn("requested_time", too_early.errors)


class CheckoutErrorsAndConfirmationTests(TestCase):
    def form(self, order_type="delivery", **data):
        return PublicCheckoutForm(data, cart_total=Decimal("120"), order_type=order_type, now=time(9, 0))

    def test_last_name_is_optional_for_pickup(self):
        form = self.form("pickup", customer_first_name="Ana", phone="5512345678")
        self.assertTrue(form.is_valid(), form.errors)

    def test_phone_needs_ten_digits_and_credit_is_not_offered(self):
        form = self.form("pickup", customer_first_name="Ana", customer_last_name="Ruiz", phone="55 1234")
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors["phone"], ["El número que escribiste tiene 6 dígitos."])
        ok = self.form("pickup", customer_first_name="Ana", customer_last_name="Ruiz", phone="+52 55 1234 5678")
        self.assertTrue(ok.is_valid(), ok.errors)
        self.assertEqual(ok.cleaned_data["phone"], "5512345678")
        self.assertNotIn("credit", [value for value, _label in self.form().fields["payment_method"].choices])

    def test_errors_are_grouped_by_section_with_what_to_do(self):
        form = self.form(customer_first_name="Ana", phone="5512345678", payment_method="cash", cash_bill="100")
        self.assertFalse(form.is_valid())
        sections = form.error_sections
        self.assertEqual(set(sections), {"domicilio", "pago"})
        street = next(item for item in sections["domicilio"] if item["field"] == "street")
        self.assertTrue(street["help"].startswith("Escribe la calle de tu domicilio."))
        self.assertIn("No encontramos un domicilio registrado", street["error"])
        self.assertIn("no alcanza", sections["pago"][0]["error"])

    def test_confirmation_explains_whatsapp_follow_up(self):
        from orders.models import Order
        order = Order.objects.create(
            daily_number=1, operating_date=timezone.localdate(), order_type="pickup",
            customer_name="Ana Ruiz", phone="5512345678", total=Decimal("70"),
        )
        response = self.client.get(reverse("public_portal:order_confirmation", args=(order.public_token,)))
        self.assertContains(response, "Pendiente de confirmar")
        self.assertContains(response, "te enviará un WhatsApp al <b>5512345678</b>", html=False)
        self.assertContains(response, "Si no recibes mensaje en 10 minutos")


class DeliveryZoneAndAgendaTests(TestCase):
    """Calles de reparto, cliente registrado por celular y asociación a la agenda por el personal."""

    def setUp(self):
        from orders.models import Customer, CustomerAddress
        self.customer = Customer.objects.create(name="Hijo Registrado", phone="55 1111 2222")
        self.address = CustomerAddress.objects.create(customer=self.customer, street="Adolfo Prieto", exterior_number="1047")

    def form(self, **data):
        base = {"customer_first_name": "Mamá", "phone": "5511112222", "payment_method": "card"}
        return PublicCheckoutForm({**base, **data}, cart_total=Decimal("70"), order_type="delivery", now=time(9, 0))

    def test_zone_matching_uses_street_and_number_only(self):
        from orders.delivery_zone import is_in_delivery_zone
        self.assertTrue(is_in_delivery_zone("adolfo prieto", "1047"))
        self.assertTrue(is_in_delivery_zone("Avenida Gabriel Mancera", "1070"))
        self.assertFalse(is_in_delivery_zone("Adolfo Prieto", "1300"))
        self.assertTrue(is_in_delivery_zone("San Francisco", "5"))  # sin rango: toda la calle
        self.assertFalse(is_in_delivery_zone("Insurgentes", "10"))

    def test_registered_phone_may_omit_address_and_others_may_not(self):
        registered = self.form()
        self.assertTrue(registered.is_valid(), registered.errors)
        self.assertTrue(registered.cleaned_data["address_from_agenda"])
        stranger = self.form(phone="5599998888")
        self.assertFalse(stranger.is_valid())
        self.assertIn("street", stranger.errors)
        half = self.form(street="Amores")
        self.assertFalse(half.is_valid())
        self.assertIn("exterior_number", half.errors)
        self.assertNotIn("neighborhood", self.form().fields)

    def make_order(self, **extra):
        from orders.models import Order
        data = dict(daily_number=1, operating_date=timezone.localdate(), order_type="delivery",
                    customer_name="Mamá", phone="5511112222", total=Decimal("70"), source="public_web")
        return Order.objects.create(**{**data, **extra})

    def test_staff_links_order_to_registered_customer_filling_saved_address(self):
        order = self.make_order(address_from_agenda=True, outside_delivery_zone=True)
        admin = get_user_model().objects.create_superuser(username="agenda_admin", password="x")
        self.client.force_login(admin)
        page = self.client.get(reverse("orders:order_detail", args=(order.pk,)))
        self.assertContains(page, "Asociar a Hijo Registrado")
        self.client.post(reverse("orders:order_link_customer", args=(order.pk,)), {"customer_id": self.customer.pk})
        order.refresh_from_db()
        self.assertEqual(order.agenda_customer, self.customer)
        self.assertEqual((order.street, order.exterior_number), ("Adolfo Prieto", "1047"))
        self.assertFalse(order.outside_delivery_zone)
        # Nombre principal: el del cliente registrado; se conserva con el que pidió y su celular.
        self.assertEqual((order.customer_name, order.web_customer_name), ("Hijo Registrado", "Mamá"))
        self.assertEqual(order.phone, "5511112222")
        page = self.client.get(reverse("orders:order_detail", args=(order.pk,)))
        self.assertContains(page, "Pidió como: Mamá")

    def test_unattended_web_order_opens_detail_until_notification_is_opened(self):
        from datetime import timedelta
        from notifications.models import InternalNotification
        admin = get_user_model().objects.create_superuser(username="agenda_admin3", password="x")
        self.client.force_login(admin)
        order = self.make_order(street="Amores", exterior_number="900")
        notification = InternalNotification.objects.create(
            notification_type="new_public_order", order=order, title="Nuevo pedido web", message="x",
        )
        detail_url = reverse("orders:order_detail", args=(order.pk,))
        listing = self.client.get(reverse("orders:order_list"))
        self.assertContains(listing, f'data-order-row-url="{detail_url}"')
        self.assertContains(listing, "Sin atender")
        # Una notificación sin leer de ayer sigue apareciendo (el contador ya la contaba).
        InternalNotification.objects.filter(pk=notification.pk).update(created_at=timezone.now() - timedelta(days=1))
        inbox = self.client.get(reverse("notifications:notification_list"))
        self.assertContains(inbox, "De ayer")
        self.assertContains(inbox, "Sin asociar")
        # Alerta de pantalla: el estado reporta el pedido sin atender y la base marca el body.
        state = self.client.get(reverse("notifications:notification_pending")).json()
        self.assertEqual((state["pending"], state["latest"]), (1, notification.pk))
        self.assertContains(listing, 'class="has-order-alert"')
        self.client.post(reverse("notifications:notification_open", args=(notification.pk,)))
        self.assertEqual(self.client.get(reverse("notifications:notification_pending")).json()["pending"], 0)
        listing = self.client.get(reverse("orders:order_list"))
        self.assertNotContains(listing, 'class="has-order-alert"')
        self.assertNotContains(listing, "Sin atender")
        self.assertContains(listing, reverse("orders:internal_order_edit", args=(order.pk,)))

    def test_typed_address_is_replaced_or_new_customer_is_created(self):
        from orders.models import Customer
        admin = get_user_model().objects.create_superuser(username="agenda_admin2", password="x")
        self.client.force_login(admin)
        order = self.make_order(street="Amores", exterior_number="900")
        self.client.post(reverse("orders:order_link_customer", args=(order.pk,)), {"customer_id": self.customer.pk})
        order.refresh_from_db()
        self.assertEqual((order.customer_name, order.street), ("Hijo Registrado", "Adolfo Prieto"))
        new_order = self.make_order(daily_number=2, phone="5577776666", customer_name="Nueva Clienta", street="Amores", exterior_number="900")
        self.client.post(reverse("orders:order_link_customer", args=(new_order.pk,)), {"action": "create"})
        new_order.refresh_from_db()
        created = Customer.objects.get(phone_key="5577776666")
        self.assertEqual(new_order.agenda_customer, created)
        self.assertEqual((new_order.customer_name, new_order.web_customer_name), ("Nueva Clienta", ""))
        self.assertEqual(created.addresses.get().street, "Amores")
