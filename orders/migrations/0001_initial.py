# NOTA TEMPORAL PARA APRENDIZAJE:
# La primera migración de orders crea el contador de folios, el encabezado del pedido y
# su partida de paquete con snapshots históricos. Borra esta nota después de leerla.

import uuid

from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [("menu", "0004_meal_packages")]
    operations = [
        migrations.CreateModel(
            name="DailyOrderCounter",
            fields=[
                ("operating_date", models.DateField(primary_key=True, serialize=False)),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("public_token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("daily_number", models.PositiveIntegerField(editable=False)),
                ("operating_date", models.DateField(default=django.utils.timezone.localdate)),
                ("order_type", models.CharField(choices=[("pickup", "Recoger en la fonda"), ("delivery", "Entrega a domicilio")], max_length=20)),
                ("source", models.CharField(choices=[("public_web", "Portal público"), ("internal", "Captura interna")], default="public_web", max_length=20)),
                ("status", models.CharField(choices=[("pending_confirmation", "Pendiente de confirmar"), ("confirmed", "Confirmado"), ("preparing", "En preparación"), ("ready", "Listo"), ("out_for_delivery", "En reparto"), ("delivered", "Entregado"), ("canceled", "Cancelado")], default="pending_confirmation", max_length=30)),
                ("customer_name", models.CharField(max_length=150)),
                ("phone", models.CharField(max_length=30)),
                ("street", models.CharField(blank=True, max_length=150)),
                ("exterior_number", models.CharField(blank=True, max_length=20)),
                ("interior_number", models.CharField(blank=True, max_length=20)),
                ("neighborhood", models.CharField(blank=True, max_length=150)),
                ("references", models.TextField(blank=True)),
                ("notes", models.TextField(blank=True)),
                ("payment_method", models.CharField(choices=[("cash", "Efectivo"), ("card", "Tarjeta"), ("transfer", "Transferencia")], max_length=20)),
                ("needs_change", models.BooleanField(default=False)),
                ("cash_tendered", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ("total", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="OrderItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("package_name_snapshot", models.CharField(max_length=100)),
                ("first_course_name_snapshot", models.CharField(max_length=150)),
                ("second_course_name_snapshot", models.CharField(max_length=150)),
                ("main_course_name_snapshot", models.CharField(max_length=150)),
                ("chicken_piece", models.CharField(blank=True, choices=[("leg", "Pierna"), ("thigh", "Muslo")], max_length=20)),
                ("with_water", models.BooleanField(default=False)),
                ("water_name_snapshot", models.CharField(blank=True, max_length=150)),
                ("tortillas", models.BooleanField()),
                ("beans", models.BooleanField()),
                ("unit_price", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("quantity", models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
                ("subtotal", models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(0)])),
                ("first_course", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items_as_first_course", to="menu.product")),
                ("main_course", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items_as_main_course", to="menu.product")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="orders.order")),
                ("package", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items", to="menu.mealpackage")),
                ("second_course", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_items_as_second_course", to="menu.product")),
            ],
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(fields=("operating_date", "daily_number"), name="unique_daily_order_number"),
        ),
    ]
