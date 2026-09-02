# NOTA TEMPORAL PARA APRENDIZAJE: esta migración crea la agenda y añade enlaces
# opcionales desde Order. Al ser opcionales, los pedidos anteriores siguen siendo
# válidos y conservan sus snapshots. Borra esta nota después de leerla.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("orders", "0013_order_delivery_tip")]

    operations = [
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("phone_key", models.CharField(blank=True, db_index=True, editable=False, max_length=30)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("name", "id")},
        ),
        migrations.CreateModel(
            name="CustomerAddress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("street", models.CharField(max_length=150)),
                ("exterior_number", models.CharField(max_length=20)),
                ("interior_number", models.CharField(blank=True, max_length=20)),
                ("neighborhood", models.CharField(blank=True, max_length=150)),
                ("references", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="addresses", to="orders.customer")),
            ],
            options={"ordering": ("-updated_at", "id")},
        ),
        migrations.AddField(
            model_name="order", name="agenda_customer",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="orders.customer"),
        ),
        migrations.AddField(
            model_name="order", name="agenda_address",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="orders", to="orders.customeraddress"),
        ),
    ]
