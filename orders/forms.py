# NOTA TEMPORAL PARA APRENDIZAJE:
# Separamos tres pasos: agregar paquete, agregar producto y capturar datos al finalizar.
# Para recoger ahora validamos nombre y apellido por separado; en entrega el apellido es opcional.
# Este formulario amplía el selector del menú con los datos necesarios para enviar una
# orden. La dirección solo es obligatoria para entrega y los datos de cambio solo aplican
# cuando el cliente pagará en efectivo. Borra esta nota después de leerla.

from django import forms

from menu.forms import PackageSelectionForm

from .models import Order


class PackageCartForm(PackageSelectionForm):
    quantity = forms.IntegerField(label="Cantidad", min_value=1, max_value=99, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("order_type")


class ProductCartForm(forms.Form):
    quantity = forms.IntegerField(label="Cantidad", min_value=1, max_value=99, initial=1)


class PublicCheckoutForm(forms.Form):
    order_type = forms.ChoiceField(label="Tipo de pedido", choices=Order.OrderType.choices)
    customer_first_name = forms.CharField(label="Nombre", max_length=80)
    customer_last_name = forms.CharField(label="Apellido", max_length=80, required=False)
    phone = forms.CharField(label="Teléfono", max_length=30)
    street = forms.CharField(label="Calle", max_length=150, required=False)
    exterior_number = forms.CharField(label="Número exterior", max_length=20, required=False)
    interior_number = forms.CharField(label="Número interior", max_length=20, required=False)
    neighborhood = forms.CharField(label="Colonia", max_length=150, required=False)
    references = forms.CharField(label="Referencias para encontrar el domicilio", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    notes = forms.CharField(label="Notas adicionales", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    payment_method = forms.ChoiceField(label="Forma de pago", choices=Order.PaymentMethod.choices)
    needs_change = forms.BooleanField(label="Necesito cambio", required=False)
    cash_tendered = forms.DecimalField(label="Pagaré con", required=False, min_value=0, decimal_places=2, max_digits=10)

    def __init__(self, *args, cart_total, **kwargs):
        super().__init__(*args, **kwargs)
        self.cart_total = cart_total

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("order_type") == Order.OrderType.PICKUP and not cleaned_data.get("customer_last_name"):
            self.add_error("customer_last_name", "El apellido es obligatorio para recoger.")
        if cleaned_data.get("order_type") == Order.OrderType.DELIVERY:
            for field_name in ("street", "exterior_number", "neighborhood", "references"):
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, "Este dato es obligatorio para entrega a domicilio.")
        is_cash = cleaned_data.get("payment_method") == Order.PaymentMethod.CASH
        if cleaned_data.get("needs_change") and not is_cash:
            self.add_error("needs_change", "El cambio solamente aplica al pago en efectivo.")
        if is_cash and cleaned_data.get("needs_change"):
            cash_tendered = cleaned_data.get("cash_tendered")
            if cash_tendered is None:
                self.add_error("cash_tendered", "Indica con cuánto pagarás.")
            elif cash_tendered < self.cart_total:
                self.add_error("cash_tendered", "La cantidad debe cubrir el total del pedido.")
        elif cleaned_data.get("cash_tendered") is not None:
            self.add_error("cash_tendered", "Este dato solo aplica si necesitas cambio en efectivo.")
        return cleaned_data
