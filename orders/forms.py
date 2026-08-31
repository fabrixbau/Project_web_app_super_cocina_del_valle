# NOTA TEMPORAL PARA APRENDIZAJE:
# La modalidad se elige antes del menú. Checkout elimina campos innecesarios para recoger
# y normaliza las opciones de efectivo para entrega. Borra esta nota después de leerla.
# Los paquetes públicos usan radios y reservan pierna/muslo para cuando se elige pollo.
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
        for name in ("first_course", "second_course", "main_course", "chicken_piece", "tortillas", "beans"):
            choices = self.fields[name].choices
            if name == "chicken_piece":
                choices = [choice for choice in choices if choice[0]]
            self.fields[name].widget = forms.RadioSelect(choices=choices)


class ProductCartForm(forms.Form):
    quantity = forms.IntegerField(label="Cantidad", min_value=1, max_value=99, initial=1)


class PublicOrderModeForm(forms.Form):
    order_type = forms.ChoiceField(
        label="¿Cómo quieres recibir tu pedido?",
        choices=Order.OrderType.choices,
        widget=forms.RadioSelect,
    )


class PublicCheckoutForm(forms.Form):
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
    cash_bill = forms.ChoiceField(
        label="Billete con el que pagarás", required=False,
        choices=(("", "Selecciona"), ("50", "$50"), ("100", "$100"), ("200", "$200"), ("500", "$500")),
    )
    cash_custom_amount = forms.DecimalField(
        label="Otra cantidad", required=False, min_value=0, decimal_places=2, max_digits=10
    )
    pays_exact = forms.BooleanField(label="No requiero cambio (pago exacto)", required=False)

    def __init__(self, *args, cart_total, order_type, **kwargs):
        super().__init__(*args, **kwargs)
        self.cart_total = cart_total
        self.order_type = order_type
        if order_type == Order.OrderType.PICKUP:
            for field_name in (
                "street", "exterior_number", "interior_number", "neighborhood", "references",
                "payment_method", "cash_bill", "cash_custom_amount", "pays_exact",
            ):
                self.fields.pop(field_name)

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["order_type"] = self.order_type
        if self.order_type == Order.OrderType.PICKUP and not cleaned_data.get("customer_last_name"):
            self.add_error("customer_last_name", "El apellido es obligatorio para recoger.")
        if self.order_type == Order.OrderType.DELIVERY:
            for field_name in ("street", "exterior_number", "neighborhood", "references"):
                if not cleaned_data.get(field_name):
                    self.add_error(field_name, "Este dato es obligatorio para entrega a domicilio.")
        if self.order_type == Order.OrderType.PICKUP:
            cleaned_data.update({"payment_method": "", "needs_change": False, "cash_tendered": None})
            return cleaned_data

        payment_method = cleaned_data.get("payment_method")
        if payment_method != Order.PaymentMethod.CASH:
            cleaned_data.update({"needs_change": False, "cash_tendered": None})
            return cleaned_data

        selected_values = sum(bool(cleaned_data.get(name)) for name in ("cash_bill", "cash_custom_amount", "pays_exact"))
        if selected_values != 1:
            self.add_error("cash_bill", "Elige un billete, escribe otra cantidad o marca pago exacto.")
            return cleaned_data
        if cleaned_data.get("pays_exact"):
            cleaned_data.update({"needs_change": False, "cash_tendered": self.cart_total})
            return cleaned_data
        amount = cleaned_data.get("cash_custom_amount")
        if cleaned_data.get("cash_bill"):
            amount = int(cleaned_data["cash_bill"])
        if amount < self.cart_total:
            self.add_error("cash_custom_amount", "La cantidad debe cubrir el total del pedido.")
        cleaned_data.update({"needs_change": True, "cash_tendered": amount})
        return cleaned_data
