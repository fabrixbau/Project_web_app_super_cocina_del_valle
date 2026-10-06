from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.roles import ADMIN, ORDER_TAKER

from .models import Customer, CustomerAddress, CustomerCreditMovement, CustomerDebt, Order
from .services import create_customer_debt, link_public_order_customer, merge_customers


class CustomerDuplicateTests(TestCase):
    """Un celular = un cliente: depuración de duplicados y "No pagó" sin cliente."""

    def setUp(self):
        self.admin = self.user("dup_admin", ADMIN)
        self.client.force_login(self.admin)

    def user(self, username, role):
        user = get_user_model().objects.create_user(username=username)
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        return user

    def order(self, **extra):
        data = dict(
            daily_number=7000 + Order.objects.count(), operating_date=timezone.localdate(),
            order_type=Order.OrderType.PICKUP, source=Order.Source.INTERNAL, status=Order.Status.PICKED_UP,
            customer_name="Cliente", phone="", total=Decimal("85"),
            requested_date=timezone.localdate(), requested_time=timezone.localtime().time(), created_by=self.admin,
        )
        return Order.objects.create(**{**data, **extra})

    def test_merge_moves_history_and_deletes_others(self):
        keep = Customer.objects.create(name="Juan Pérez", phone="+52 55 1234 5678")
        # Con el candado de la base ya no puede haber dos clientes con el mismo celular;
        # la unión se prueba con otro número (el procedimiento es el mismo).
        dup = Customer.objects.create(name="Juan P.", phone="5512340000", notes="Timbre roto", credit_balance=Decimal("50"))
        CustomerAddress.objects.create(customer=keep, street="Amores", exterior_number="900")
        same = CustomerAddress.objects.create(customer=dup, street="amores", exterior_number="900")
        other = CustomerAddress.objects.create(customer=dup, street="Pilares", exterior_number="10")
        order = self.order(agenda_customer=dup, agenda_address=same)
        debt = create_customer_debt(order=order, actor=self.admin)
        CustomerCreditMovement.objects.create(customer=dup, action=CustomerCreditMovement.Action.DEPOSIT, amount=Decimal("50"), registered_by=self.admin)

        self.assertEqual(merge_customers(keep=keep, others=[dup]), 1)
        keep.refresh_from_db()
        order.refresh_from_db()
        debt.refresh_from_db()
        self.assertFalse(Customer.objects.filter(pk=dup.pk).exists())
        self.assertEqual(order.agenda_customer, keep)
        self.assertEqual(order.agenda_address.customer, keep)  # el domicilio repetido se unió
        self.assertEqual(debt.customer, keep)
        self.assertEqual(keep.credit_balance, Decimal("50"))
        self.assertIn("Timbre roto", keep.notes)
        self.assertEqual(sorted(keep.addresses.values_list("street", flat=True)), ["Amores", "Pilares"])
        self.assertEqual(CustomerCreditMovement.objects.get().customer, keep)
        self.assertFalse(CustomerAddress.objects.filter(pk=same.pk).exists())
        self.assertTrue(CustomerAddress.objects.filter(pk=other.pk, customer=keep).exists())

    def test_database_rejects_repeated_phone_and_panel_is_clean(self):
        from django.db import IntegrityError, transaction
        self.client.force_login(self.user("dup_phone", ORDER_TAKER))
        Customer.objects.create(name="Ana", phone="5511112222")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Customer.objects.create(name="Ana R.", phone="+52 55 1111 2222")
        Customer.objects.create(name="Sin teléfono 1", phone="")
        Customer.objects.create(name="Sin teléfono 2", phone="")  # sin celular no cuenta
        self.assertNotContains(self.client.get(reverse("orders:customer_list")), "Duplicados (")
        self.assertContains(self.client.get(reverse("orders:customer_duplicates")), "No hay clientes con el celular repetido")

    def test_web_order_cannot_create_a_second_customer_with_same_phone(self):
        Customer.objects.create(name="Registrado", phone="5512345678")
        order = self.order(source=Order.Source.PUBLIC_WEB, phone="55 1234 5678", customer_name="Nueva")
        with self.assertRaises(ValidationError):
            link_public_order_customer(order=order, actor=self.admin, customer=None)
        self.assertEqual(Customer.objects.filter(phone_key="5512345678").count(), 1)

    def test_unpaid_without_customer_uses_chosen_or_new_customer(self):
        chosen = Customer.objects.create(name="Elegido", phone="5500000001")
        order = self.order()
        url = reverse("cashier:order_debt_create", args=(order.pk,))
        self.client.post(url, {"customer_id": chosen.pk, "next": "/app/caja/"})
        order.refresh_from_db()
        self.assertEqual(order.agenda_customer, chosen)
        self.assertTrue(CustomerDebt.objects.filter(order=order, customer=chosen).exists())

        new_order = self.order()
        self.client.post(reverse("cashier:order_debt_create", args=(new_order.pk,)), {
            "new_customer_name": "Cliente Nuevo", "new_customer_phone": "5500000002", "next": "/app/caja/",
        })
        new_order.refresh_from_db()
        self.assertEqual(new_order.agenda_customer.name, "Cliente Nuevo")
        self.assertTrue(CustomerDebt.objects.filter(order=new_order).exists())

        # Un celular que ya existe no crea otro cliente ni registra el adeudo.
        third = self.order()
        self.client.post(reverse("cashier:order_debt_create", args=(third.pk,)), {
            "new_customer_name": "Repetido", "new_customer_phone": "+52 5500000001", "next": "/app/caja/",
        })
        third.refresh_from_db()
        self.assertIsNone(third.agenda_customer)
        self.assertFalse(CustomerDebt.objects.filter(order=third).exists())
        self.assertEqual(Customer.objects.filter(phone_key="5500000001").count(), 1)
