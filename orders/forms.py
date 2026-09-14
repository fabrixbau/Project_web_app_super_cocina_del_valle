# NOTA TEMPORAL PARA APRENDIZAJE:
# La modalidad se elige antes del menú. Checkout elimina campos innecesarios para recoger
# y normaliza las opciones de efectivo para entrega. Borra esta nota después de leerla.
# Los paquetes públicos usan radios y reservan pierna/muslo para cuando se elige pollo.
# Para recoger ahora validamos nombre y apellido por separado; en entrega el apellido es opcional.
# Este formulario amplía el selector del menú con los datos necesarios para enviar una
# orden. La dirección solo es obligatoria para entrega y los datos de cambio solo aplican
# cuando el cliente pagará en efectivo. Borra esta nota después de leerla.

from datetime import datetime

from django import forms
from django.utils import timezone

from menu.forms import PackageSelectionForm

from .models import Customer, CustomerAddress, Order


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


class InternalPackageForm(PackageCartForm):
    bread = forms.BooleanField(label="Lleva bolillo", required=False)
    customization_comment = forms.CharField(
        label="Comentario para cocina", required=False, max_length=150,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ej. Sin cebolla"}),
    )

    def clean_customization_comment(self):
        return " ".join(self.cleaned_data["customization_comment"].split())


class InternalPackageExtrasForm(forms.Form):
    # NOTA TEMPORAL PARA APRENDIZAJE: Este formulario edita sólo extras del paquete;
    # los tres tiempos permanecen intactos. Borra esta nota después de leerla.
    with_water = forms.BooleanField(label="Con agua del día", required=False)
    tortillas = forms.BooleanField(label="Lleva tortillas", required=False)
    bread = forms.BooleanField(label="Lleva bolillo", required=False)
    beans = forms.BooleanField(label="Lleva frijoles", required=False)
    customization_comment = forms.CharField(
        label="Comentario para cocina", required=False, max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Empacar por separado"}),
    )

    def clean_customization_comment(self):
        return " ".join(self.cleaned_data["customization_comment"].split())

    def clean(self):
        data = super().clean()
        if data.get("tortillas") and data.get("bread"):
            raise forms.ValidationError("Selecciona tortillas o bolillo, no ambos.")
        return data


class ProductCartForm(forms.Form):
    quantity = forms.IntegerField(label="Cantidad", min_value=1, max_value=99, initial=1)


class InternalOrderForm(forms.Form):
    # NOTA TEMPORAL PARA APRENDIZAJE:
    # Un solo formulario atiende Recoger y Entrega. Django siempre valida todos los datos
    # importantes aunque JavaScript oculte los que no aplican. Borra esta nota al probarlo.
    order_type = forms.ChoiceField(label="Modalidad", choices=Order.OrderType.choices, widget=forms.RadioSelect)
    agenda_customer_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    agenda_address_id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    customer_name = forms.CharField(label="Nombre del cliente", max_length=150)
    phone = forms.CharField(label="Teléfono", max_length=30, required=False)
    requested_date = forms.DateField(label="Fecha de entrega", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), input_formats=("%Y-%m-%d",))
    requested_time = forms.TimeField(label="Hora de entrega", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"), input_formats=("%H:%M",))
    street = forms.CharField(label="Calle", max_length=150, required=False)
    exterior_number = forms.CharField(label="Número exterior", max_length=20, required=False)
    interior_number = forms.CharField(label="Número interior", max_length=20, required=False)
    neighborhood = forms.CharField(label="Colonia", max_length=150, required=False)
    references = forms.CharField(label="Referencias", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    payment_method = forms.ChoiceField(label="Forma de pago", required=False, choices=Order.PaymentMethod.choices, widget=forms.RadioSelect)
    cash_bill = forms.ChoiceField(label="Billete", required=False, choices=(("", "Selecciona"), ("20", "$20"), ("50", "$50"), ("100", "$100"), ("200", "$200"), ("500", "$500")))
    cash_custom_amount = forms.DecimalField(label="Otra cantidad", required=False, min_value=0, max_digits=10, decimal_places=2)
    pays_exact = forms.BooleanField(label="Pago exacto", required=False)
    notes = forms.CharField(label="Notas generales", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, order_total=0, closing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_total = order_total
        self.closing = closing

    def clean(self):
        data = super().clean()
        order_type = data.get("order_type")
        requested_date = data.get("requested_date")
        requested_time = data.get("requested_time")
        data["requested_for"] = (
            timezone.make_aware(datetime.combine(requested_date, requested_time))
            if requested_date and requested_time else None
        )
        if self.closing and order_type == Order.OrderType.DELIVERY:
            for name in ("street", "exterior_number"):
                if not data.get(name):
                    self.add_error(name, "Este dato es obligatorio para entrega.")
        method = data.get("payment_method")
        # NOTA TEMPORAL PARA APRENDIZAJE: Entrega necesita pago antes de salir de
        # captura. Recoger puede definirlo después, pero no podrá finalizar como
        # Recogido mientras siga vacío. Borra esta nota después de leerla.
        if self.closing and order_type == Order.OrderType.DELIVERY and not method:
            self.add_error("payment_method", "Selecciona la forma de pago de la entrega antes de cerrar.")
            return data
        if not method:
            data.update({"needs_change": False, "cash_tendered": None})
            return data
        if method != Order.PaymentMethod.CASH:
            data.update({"needs_change": False, "cash_tendered": None})
            return data
        choices = sum(bool(data.get(name)) for name in ("cash_bill", "cash_custom_amount", "pays_exact"))
        # NOTA TEMPORAL PARA APRENDIZAJE: en captura interna basta saber que será en
        # efectivo para cerrar Entrega o Recoger; Caja puede definir el billete después.
        # None significa "monto pendiente", no "pago exacto". Borra esta nota.
        if choices == 0:
            data.update({"needs_change": False, "cash_tendered": None})
            return data
        if choices != 1:
            self.add_error("cash_bill", "Elige un billete, otra cantidad o pago exacto.")
            return data
        amount = self.order_total if data.get("pays_exact") else data.get("cash_custom_amount")
        if data.get("cash_bill"):
            amount = int(data["cash_bill"])
        if amount is not None and amount < self.order_total:
            self.add_error("cash_custom_amount", "El efectivo no alcanza para cubrir el pedido.")
        data.update({"needs_change": not data.get("pays_exact"), "cash_tendered": amount})
        return data


class InternalOrderAutosaveForm(forms.Form):
    # NOTA TEMPORAL PARA APRENDIZAJE: El autoguardado acepta campos parciales mientras el
    # telefonista escribe; la validación estricta continúa ocurriendo al cerrar. Borra esta nota.
    order_type = forms.ChoiceField(choices=Order.OrderType.choices)
    agenda_customer_id = forms.IntegerField(required=False)
    agenda_address_id = forms.IntegerField(required=False)
    payment_method = forms.ChoiceField(choices=Order.PaymentMethod.choices, required=False)
    cash_bill = forms.ChoiceField(required=False, choices=(('', 'Selecciona'), ('20', '$20'), ('50', '$50'), ('100', '$100'), ('200', '$200'), ('500', '$500')))
    cash_custom_amount = forms.DecimalField(required=False, min_value=0, max_digits=10, decimal_places=2)
    pays_exact = forms.BooleanField(required=False)
    customer_name = forms.CharField(max_length=150, required=False)
    phone = forms.CharField(max_length=30, required=False)
    requested_date = forms.DateField(required=False, input_formats=("%Y-%m-%d",))
    requested_time = forms.TimeField(required=False, input_formats=("%H:%M",))
    street = forms.CharField(max_length=150, required=False)
    exterior_number = forms.CharField(max_length=20, required=False)
    interior_number = forms.CharField(max_length=20, required=False)
    neighborhood = forms.CharField(max_length=150, required=False)
    references = forms.CharField(required=False)
    notes = forms.CharField(required=False)

    def __init__(self, *args, order_total=0, for_print=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_total = order_total
        self.for_print = for_print

    def clean(self):
        data = super().clean()
        if data.get("payment_method") != Order.PaymentMethod.CASH:
            data.update({"cash_tendered": None, "needs_change": False})
            return data
        choices = sum(bool(data.get(name)) for name in ("cash_bill", "cash_custom_amount", "pays_exact"))
        if choices > 1 and self.for_print:
            self.add_error("cash_bill", "Elige solo una cantidad de efectivo.")
        amount = None
        if choices == 1:
            amount = self.order_total if data.get("pays_exact") else data.get("cash_custom_amount")
            if data.get("cash_bill"):
                amount = int(data["cash_bill"])
        if amount is not None and amount < self.order_total:
            if self.for_print:
                self.add_error("cash_custom_amount", "El efectivo no alcanza para cubrir el pedido.")
            amount = None
        data.update({"cash_tendered": amount, "needs_change": amount is not None and not data.get("pays_exact")})
        return data


class DeliveryTipForm(forms.Form):
    tip_amount = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2)


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ("name", "phone", "notes")
        labels = {"name": "Nombre", "phone": "Teléfono", "notes": "Indicaciones generales"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean_phone(self):
        # NOTA TEMPORAL PARA APRENDIZAJE: normalizamos sólo para comparar; el valor
        # escrito conserva su formato visible. La validación del servidor evita que
        # un segundo formulario salte la advertencia del navegador. Borra esta nota.
        phone = self.cleaned_data["phone"].strip()
        phone_key = "".join(character for character in phone if character.isdigit())
        if not phone_key:
            return phone
        duplicate = Customer.objects.filter(phone_key=phone_key).exclude(pk=self.instance.pk).first()
        if duplicate:
            raise forms.ValidationError(f"Este teléfono ya pertenece a {duplicate.name}. Revisa su ficha antes de crear otro registro.")
        return phone


class CustomerAddressForm(forms.ModelForm):
    class Meta:
        model = CustomerAddress
        fields = ("street", "exterior_number", "interior_number", "neighborhood", "references")
        labels = {
            "street": "Calle", "exterior_number": "Número exterior",
            "interior_number": "Número interior", "neighborhood": "Colonia",
            "references": "Referencias",
        }
        widgets = {"references": forms.Textarea(attrs={"rows": 3})}


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
