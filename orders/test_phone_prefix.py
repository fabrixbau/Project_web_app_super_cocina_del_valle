from django.test import TestCase

from .forms import CustomerForm
from .models import Customer
from .phones import phone_key


class MexicanPhonePrefixTests(TestCase):
    def test_mexican_prefix_matches_local_number(self):
        self.assertEqual(phone_key("+52 55 1234 5678"), "5512345678")
        self.assertEqual(phone_key("55 1234 5678"), "5512345678")

    def test_agenda_can_store_optional_prefix_without_duplicate(self):
        form = CustomerForm({"name": "Ana", "phone": "5512345678", "include_country_code": "on"})
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save()
        self.assertEqual(customer.phone, "+52 5512345678")
        self.assertEqual(customer.phone_key, "5512345678")
        duplicate = CustomerForm({"name": "Otra", "phone": "55 1234 5678"})
        self.assertFalse(duplicate.is_valid())
        self.assertIn("phone", duplicate.errors)

    def test_unchecking_prefix_keeps_same_contact(self):
        customer = Customer.objects.create(name="Ana", phone="+52 5512345678")
        form = CustomerForm({"name": "Ana", "phone": customer.phone}, instance=customer)
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save()
        self.assertEqual(customer.phone, "5512345678")
