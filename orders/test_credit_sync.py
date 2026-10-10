from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone

from accounts.roles import ADMIN
from menu.models import Category, Product

from .models import Customer, CustomerCreditMovement, Order
from .services import (
    add_customer_credit, add_internal_order_product, apply_customer_credit_to_order,
    change_internal_order_item, transition_order,
)


class OrderCreditSyncTests(TestCase):
    """El saldo a favor usado por un pedido sigue a su total, suba o baje (decisión 2026-10-10)."""

    def setUp(self):
        self.admin = get_user_model().objects.create_user(username="saldo_admin")
        self.admin.groups.add(Group.objects.get_or_create(name=ADMIN)[0])
        self.customer = Customer.objects.create(name="Cliente saldo", phone="5550002222")
        add_customer_credit(customer=self.customer, amount="1000", payment_method=Order.PaymentMethod.CASH, actor=self.admin)
        category = Category.objects.create(name="Pruebas saldo")
        self.dish = Product.objects.create(category=category, name="Platillo 200", price=Decimal("200"))
        self.extra = Product.objects.create(category=category, name="Extra 50", price=Decimal("50"))
        self.order = Order.objects.create(
            daily_number=7000, operating_date=timezone.localdate(),
            order_type=Order.OrderType.DELIVERY, source=Order.Source.INTERNAL, status=Order.Status.PREPARING,
            customer_name=self.customer.name, agenda_customer=self.customer, total=0,
            requested_date=timezone.localdate(), requested_time=timezone.localtime().time(),
            created_by=self.admin,
        )
        add_internal_order_product(order=self.order, product=self.dish, actor=self.admin)
        apply_customer_credit_to_order(order=self.order, actor=self.admin)  # cierre de captura

    def balance(self):
        self.customer.refresh_from_db()
        self.order.refresh_from_db()
        return self.customer.credit_balance, self.order.credit_applied

    def test_total_up_then_down_keeps_balance_in_sync(self):
        self.assertEqual(self.balance(), (Decimal("800"), Decimal("200")))
        extra_item = add_internal_order_product(order=self.order, product=self.extra, actor=self.admin)
        self.assertEqual(self.balance(), (Decimal("750"), Decimal("250")))
        change_internal_order_item(order=self.order, item=extra_item, action="remove", actor=self.admin)
        self.assertEqual(self.balance(), (Decimal("800"), Decimal("200")))
        returned = CustomerCreditMovement.objects.get(action=CustomerCreditMovement.Action.ORDER_ADJUSTMENT)
        self.assertEqual(returned.amount, Decimal("50"))

    def test_delivered_order_can_still_be_edited_and_recalculated(self):
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.DELIVERED)
        self.order.refresh_from_db()
        add_internal_order_product(order=self.order, product=self.extra, actor=self.admin)
        self.assertEqual(self.balance(), (Decimal("750"), Decimal("250")))

    def test_cancel_returns_all_used_credit(self):
        transition_order(order=self.order, action="cancel", actor=self.admin)
        self.assertEqual(self.balance(), (Decimal("1000"), Decimal("0")))

    def test_increase_beyond_balance_uses_only_what_is_left(self):
        self.customer.credit_balance = Decimal("20")
        self.customer.save(update_fields=["credit_balance"])
        add_internal_order_product(order=self.order, product=self.extra, actor=self.admin)
        self.assertEqual(self.balance(), (Decimal("0"), Decimal("220")))
        self.assertEqual(self.order.amount_due, Decimal("30"))
