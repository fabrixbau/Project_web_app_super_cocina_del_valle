from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from menu.forms import ProductForm
from menu.models import Category, DailyMenu, MealPackage, Product
from orders.cart import product_is_orderable
from orders.forms import InternalPackageForm, PackageCartForm


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
            variable_first_course=soup, second_course_one=rice, beef_stew=stew,
        )
        package = MealPackage.objects.get(package_type=MealPackage.PackageType.RUNNING)
        public = PackageCartForm(package=package, daily_menu=menu, customers_only=True)
        labels = [choice.choice_label for choice in public["first_course"]]
        self.assertEqual(labels, ["Consomé"])
        internal = InternalPackageForm(package=package, daily_menu=menu)
        self.assertIn(soup, internal.fields["first_course"].queryset)
