from decimal import Decimal

from django.test import SimpleTestCase

from config.printing import _kitchen_payment_label

from .models import Order


class KitchenPaymentLabelTests(SimpleTestCase):
    """Comanda de cocina a domicilio: con cuánto paga y cuánto devolver (2026-10-15)."""

    def order(self, **fields):
        data = {"order_type": Order.OrderType.DELIVERY, "total": Decimal("200"), "payment_method": ""}
        data.update(fields)
        return Order(**data)

    def test_cash_with_change(self):
        order = self.order(payment_method=Order.PaymentMethod.CASH, needs_change=True, cash_tendered=Decimal("500"))
        self.assertEqual(_kitchen_payment_label(order), "Paga con $500 · devolver $300")

    def test_cash_exact(self):
        order = self.order(payment_method=Order.PaymentMethod.CASH, needs_change=False)
        self.assertEqual(_kitchen_payment_label(order), "Efectivo exacto")

    def test_without_method(self):
        self.assertEqual(_kitchen_payment_label(self.order()), "Pendiente definir método de pago")

    def test_change_uses_amount_left_after_credit(self):
        order = self.order(
            payment_method=Order.PaymentMethod.CASH, needs_change=True, cash_tendered=Decimal("200"),
            credit_applied=Decimal("50.50"),
        )
        self.assertEqual(_kitchen_payment_label(order), "Paga con $200 · devolver $50.50")

    def test_pickup_keeps_method_name(self):
        order = self.order(order_type=Order.OrderType.PICKUP, payment_method=Order.PaymentMethod.CASH,
                           needs_change=True, cash_tendered=Decimal("500"))
        self.assertEqual(_kitchen_payment_label(order), "Efectivo")
