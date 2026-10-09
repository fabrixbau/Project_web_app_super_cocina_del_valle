# NOTA TEMPORAL PARA APRENDIZAJE:
# La modalidad se elige antes del menú. Checkout elimina campos innecesarios para recoger
# y normaliza las opciones de efectivo para entrega. Borra esta nota después de leerla.
# Los paquetes públicos usan radios y reservan pierna/muslo para cuando se elige pollo.
# Para recoger ahora validamos nombre y apellido por separado; en entrega el apellido es opcional.
# Este formulario amplía el selector del menú con los datos necesarios para enviar una
# orden. La dirección solo es obligatoria para entrega y los datos de cambio solo aplican
# cuando el cliente pagará en efectivo. Borra esta nota después de leerla.

from datetime import datetime, time, timedelta

from django import forms
from django.utils import timezone

from menu.forms import PackageSelectionForm
from menu.egg import egg_products
from menu.models import Product

from .models import Customer, CustomerAddress, Order
from .phones import phone_key


class PackageCartForm(PackageSelectionForm):
    quantity = forms.IntegerField(label="Cantidad", min_value=1, max_value=99, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("order_type")
        if self.customers_only:
            # Portal de clientes: sin la opción vacía "---------" y con el nombre del
            # producto a secas (Product.__str__ antepone la categoría, p. ej. "Comida mexicana · ").
            for name in ("first_course", "second_course", "main_course"):
                self.fields[name].empty_label = None
                self.fields[name].label_from_instance = lambda product: product.name
            # El cliente puede armar 2 tiempos sin interruptor: primero + guisado o
            # segundo + guisado. clean() lo detecta y marca `two_course`.
            self.fields["first_course"].required = False
            self.fields["second_course"].required = False
        for name in ("first_course", "second_course", "main_course", "chicken_piece", "tortillas", "beans"):
            choices = self.fields[name].choices
            if name == "chicken_piece":
                choices = [choice for choice in choices if choice[0]]
            self.fields[name].widget = forms.RadioSelect(choices=choices)


    def clean(self):
        data = super().clean()
        if self.customers_only:
            has_first = bool(data.get("first_course"))
            has_second = bool(data.get("second_course"))
            if not has_first and not has_second:
                raise forms.ValidationError(
                    "Elige al menos el primer o el segundo tiempo, además del guisado."
                )
            data["two_course"] = has_first != has_second
        return data


class InternalPackageForm(PackageCartForm):
    two_course = forms.BooleanField(label="Paquete de 2 tiempos", required=False)
    egg_product = forms.ModelChoiceField(label="Huevo opcional", queryset=Product.objects.none(), required=False, empty_label="Sin huevo")
    bread = forms.BooleanField(label="Lleva bolillo", required=False)
    customization_comment = forms.CharField(
        label="Comentario para cocina", required=False, max_length=150,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ej. Sin cebolla"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["egg_product"].queryset = egg_products()
        self.fields["first_course"].required = False
        self.fields["second_course"].required = False

    def clean(self):
        data = super().clean()
        first = data.get("first_course")
        second = data.get("second_course")
        if data.get("two_course"):
            if bool(first) == bool(second):
                raise forms.ValidationError(
                    "Para 2 tiempos elige primer tiempo o segundo tiempo, y siempre el tercer tiempo."
                )
        else:
            if not first:
                self.add_error("first_course", "Selecciona el primer tiempo.")
            if not second:
                self.add_error("second_course", "Selecciona el segundo tiempo.")
        return data

    def clean_customization_comment(self):
        return " ".join(self.cleaned_data["customization_comment"].split())

    def calculated_total(self):
        total = super().calculated_total()
        egg = self.cleaned_data.get("egg_product")
        return total + (egg.price * self.cleaned_data.get("quantity", 1) if egg else 0)


class InternalPackageExtrasForm(forms.Form):
    # NOTA TEMPORAL PARA APRENDIZAJE: Este formulario edita sólo extras del paquete;
    # los tres tiempos permanecen intactos. Borra esta nota después de leerla.
    with_water = forms.BooleanField(label="Con agua del día", required=False)
    tortillas = forms.BooleanField(label="Lleva tortillas", required=False)
    bread = forms.BooleanField(label="Lleva bolillo", required=False)
    beans = forms.BooleanField(label="Lleva frijoles", required=False)
    egg_product = forms.ModelChoiceField(label="Huevo opcional", queryset=Product.objects.none(), required=False, empty_label="Sin huevo")
    customization_comment = forms.CharField(
        label="Comentario para cocina", required=False, max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ej. Empacar por separado"}),
    )

    def __init__(self, *args, existing_egg_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["egg_product"].queryset = egg_products(existing_egg_id)

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
    cash_bill = forms.ChoiceField(label="Billete", required=False, choices=(("", "Selecciona"), ("50", "$50"), ("100", "$100"), ("150", "$150"), ("200", "$200"), ("500", "$500")))
    cash_custom_amount = forms.DecimalField(label="Otra cantidad", required=False, min_value=0, max_digits=10, decimal_places=2)
    pays_exact = forms.BooleanField(label="Pago exacto", required=False)
    notes = forms.CharField(label="Notas generales", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, order_total=0, closing=False, available_credit=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_total = order_total
        self.closing = closing
        self.available_credit = available_credit

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
        # Recogido mientras siga vacío. Si el saldo a favor del cliente ya cubre el
        # total (available_credit >= order_total), no hace falta elegir nada — no
        # hay dinero real que cobrar; close_internal_order_capture asignará
        # PaymentMethod.CREDIT automáticamente al cerrar. Borra esta nota.
        covered_by_credit = self.order_total > 0 and self.available_credit >= self.order_total
        if self.closing and order_type == Order.OrderType.DELIVERY and not method and not covered_by_credit:
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
    cash_bill = forms.ChoiceField(required=False, choices=(('', 'Selecciona'), ('50', '$50'), ('100', '$100'), ('150', '$150'), ('200', '$200'), ('500', '$500')))
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
    include_country_code = forms.BooleanField(label="Agregar prefijo +52 (opcional)", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(("name", "phone", "include_country_code", "notes"))
        if not self.is_bound and self.instance.pk:
            self.fields["include_country_code"].initial = self.instance.phone.strip().startswith("+52")

    class Meta:
        model = Customer
        fields = ("name", "phone", "notes")
        labels = {"name": "Nombre", "phone": "Teléfono", "notes": "Indicaciones generales"}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        # NOTA TEMPORAL PARA APRENDIZAJE: normalizamos sólo para comparar; el valor
        # escrito conserva su formato visible. La validación del servidor evita que
        # un segundo formulario salte la advertencia del navegador. Borra esta nota.
        data = super().clean()
        phone = data.get("phone", "").strip()
        digits = phone_key(phone)
        if data.get("include_country_code") and len(digits) != 10:
            self.add_error("phone", "Para agregar +52, escribe un número mexicano de 10 dígitos.")
            return data
        if data.get("include_country_code"):
            data["phone"] = f"+52 {digits}"
        elif len(digits) == 10 and phone.startswith("+52"):
            data["phone"] = digits
        duplicate = Customer.objects.filter(phone_key=digits).exclude(pk=self.instance.pk).first() if digits else None
        if duplicate:
            self.add_error("phone", f"Este teléfono ya pertenece a {duplicate.name}. Revisa su ficha antes de crear otro registro.")
        return data


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


class PublicCheckoutForm(forms.Form):
    customer_first_name = forms.CharField(label="Nombre", max_length=80)
    customer_last_name = forms.CharField(label="Apellido", max_length=80, required=False)
    phone = forms.CharField(label="Teléfono", max_length=30)
    street = forms.CharField(label="Calle", max_length=150, required=False)
    exterior_number = forms.CharField(label="Número exterior", max_length=20, required=False)
    interior_number = forms.CharField(label="Número interior", max_length=20, required=False)
    references = forms.CharField(label="Referencias para encontrar el domicilio", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    notes = forms.CharField(label="Notas adicionales", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    # El cliente no puede pagar con "Saldo a favor": eso sólo lo aplica el personal.
    payment_method = forms.ChoiceField(label="Forma de pago", widget=forms.RadioSelect, choices=(
        (Order.PaymentMethod.CASH, "Efectivo"), (Order.PaymentMethod.CARD, "Terminal"),
        (Order.PaymentMethod.TRANSFER, "Transferencia"),
    ))
    cash_bill = forms.ChoiceField(
        label="Billete con el que pagarás", required=False, widget=forms.RadioSelect,
        choices=(("50", "$50"), ("100", "$100"), ("200", "$200"), ("500", "$500")),
    )
    cash_custom_amount = forms.DecimalField(
        label="Otra cantidad", required=False, min_value=0, decimal_places=2, max_digits=10
    )
    pays_exact = forms.BooleanField(label="No requiero cambio (pago exacto)", required=False)
    schedule = forms.ChoiceField(
        label="¿Para cuándo lo quieres?", initial="asap", widget=forms.RadioSelect, required=False,
        choices=(("asap", "Lo antes posible"), ("later", "Elegir hora")),
    )
    # Sin validación de opciones: la lista se valida en clean() sólo si eligió "Elegir hora".
    requested_time = forms.CharField(label="Hora", required=False, widget=forms.Select())

    SLOT_MINUTES = 15
    OPENING_TIME = time(8, 30)
    CLOSING_TIME = time(18, 0)

    # Errores para el cliente: "qué hacer" (aquí) y "qué pasó" (el mensaje del error).
    # Cada sección de la página se enmarca en rojo si alguno de sus campos falló.
    FIELD_HELP = {
        "customer_first_name": "Escribe tu nombre para saber de quién es el pedido.",
        "phone": "Escribe tu número celular a 10 dígitos; ahí te enviaremos la confirmación por WhatsApp.",
        "street": "Escribe la calle de tu domicilio. Si ya pediste antes con este celular, puedes dejar el domicilio en blanco.",
        "exterior_number": "Escribe el número exterior de tu domicilio.",
        "payment_method": "Elige cómo vas a pagar: efectivo, terminal o transferencia.",
        "cash_bill": "Elige el billete con el que pagarás, escribe otra cantidad o marca pago exacto.",
        "cash_custom_amount": "Escribe una cantidad igual o mayor al total de tu pedido.",
        "requested_time": "Toca el reloj y elige una de las horas disponibles, o deja «Lo antes posible».",
    }
    SECTIONS = (
        ("datos", "Tus datos", ("customer_first_name", "customer_last_name", "phone")),
        ("domicilio", "Domicilio de entrega", ("street", "exterior_number", "interior_number", "references")),
        ("horario", "¿Para cuándo lo quieres?", ("schedule", "requested_time")),
        ("pago", "Pago", ("payment_method", "cash_bill", "cash_custom_amount", "pays_exact")),
        ("notas", "Notas", ("notes",)),
    )

    def __init__(self, *args, cart_total, order_type, now=None, earliest=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cart_total = cart_total
        self.order_type = order_type
        # Horarios de hoy cada 15 minutos: desde 30 minutos después de ahora (o desde la
        # 1:00 p. m. si el pedido trae comida) hasta las 6:00 p. m.
        self.slots = self.available_slots(now or timezone.localtime().time(), earliest)
        self.fields["requested_time"].widget.choices = [("", "Selecciona una hora")] + [
            (slot.strftime("%H:%M"), self.slot_label(slot)) for slot in self.slots
        ]
        self.fields["requested_time"].label = "Hora para recoger" if order_type == Order.OrderType.PICKUP else "Hora de entrega"
        for field in self.fields.values():
            field.error_messages["required"] = "Este dato está vacío."
            field.error_messages["invalid_choice"] = "La opción elegida no es válida."
        # Etiquetas flotantes del portal: el campo necesita un placeholder (aunque sea un espacio).
        for name in ("customer_first_name", "customer_last_name", "street", "exterior_number", "interior_number", "references", "notes", "cash_custom_amount"):
            if name in self.fields:
                self.fields[name].widget.attrs.setdefault("placeholder", " ")
        if "street" in self.fields:
            self.fields["street"].widget.attrs.update({"autocomplete": "off", "data-pp-street": ""})
        if not self.slots:
            self.fields["schedule"].choices = (("asap", "Lo antes posible"),)
        if order_type == Order.OrderType.PICKUP:
            for field_name in (
                "street", "exterior_number", "interior_number", "references",
                "payment_method", "cash_bill", "cash_custom_amount", "pays_exact",
            ):
                self.fields.pop(field_name)

    @classmethod
    def available_slots(cls, now, earliest=None):
        start = datetime.combine(timezone.localdate(), now) + timedelta(minutes=30)
        remainder = (start.minute % cls.SLOT_MINUTES) or cls.SLOT_MINUTES
        if start.minute % cls.SLOT_MINUTES or start.second or start.microsecond:
            start = start.replace(second=0, microsecond=0) + timedelta(minutes=cls.SLOT_MINUTES - remainder)
        # Horario de atención 8:30 a. m.–6:00 p. m.; las horas que ya pasaron no se ofrecen.
        # Con comida en el pedido (earliest) se ofrece desde la 1:00 p. m.
        start = max(start, datetime.combine(start.date(), max(cls.OPENING_TIME, earliest or cls.OPENING_TIME)))
        end = datetime.combine(start.date(), cls.CLOSING_TIME)
        slots = []
        while start <= end and start.date() == end.date():
            slots.append(start.time())
            start += timedelta(minutes=cls.SLOT_MINUTES)
        return slots

    @staticmethod
    def slot_label(slot):
        hour = slot.hour % 12 or 12
        return f"{hour}:{slot.minute:02d} {'a. m.' if slot.hour < 12 else 'p. m.'}"

    @staticmethod
    def registered_with_address(phone):
        from .models import Customer
        return bool(phone) and Customer.objects.filter(phone_key=phone, addresses__isnull=False).exists()

    def clean_phone(self):
        digits = phone_key(self.cleaned_data["phone"])
        if len(digits) != 10:
            raise forms.ValidationError(f"El número que escribiste tiene {len(digits)} dígito{'s' if len(digits) != 1 else ''}.")
        return digits

    @property
    def error_sections(self):
        """{sección: [{campo, etiqueta, qué hacer, qué pasó}]} sólo con las secciones que fallaron."""
        report = {}
        for section_id, _title, field_names in self.SECTIONS:
            items = [
                {"field": name, "label": self.fields[name].label, "help": self.FIELD_HELP.get(name, ""), "error": error}
                for name in field_names if name in self.fields
                for error in self.errors.get(name, [])
            ]
            if items:
                report[section_id] = items
        return report

    @property
    def slot_values(self):
        return [slot.strftime("%H:%M") for slot in self.slots]

    @property
    def error_summary(self):
        titles = dict((section_id, title) for section_id, title, _fields in self.SECTIONS)
        return [{"id": section_id, "title": titles[section_id], "items": items} for section_id, items in self.error_sections.items()]

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["order_type"] = self.order_type
        # Hora solicitada (sólo hoy). "Lo antes posible" deja el pedido sin hora.
        cleaned_data.update({"requested_date": None, "requested_time": None, "requested_for": None})
        if self.data.get("schedule") == "later":
            chosen = self.data.get("requested_time", "")
            slot = next((slot for slot in self.slots if slot.strftime("%H:%M") == chosen), None)
            if not slot:
                self.add_error("requested_time", "No elegiste hora o esa hora ya no está disponible.")
            else:
                today = timezone.localdate()
                cleaned_data.update({
                    "requested_date": today, "requested_time": slot,
                    "requested_for": timezone.make_aware(datetime.combine(today, slot)),
                })
        cleaned_data["address_from_agenda"] = False
        if self.order_type == Order.OrderType.DELIVERY:
            street = (cleaned_data.get("street") or "").strip()
            number = (cleaned_data.get("exterior_number") or "").strip()
            if not street and not number and self.registered_with_address(cleaned_data.get("phone")):
                # Cliente que ya pidió antes: con su celular basta; el personal confirma el
                # domicilio por WhatsApp. Nunca se le muestra el domicilio guardado.
                cleaned_data["address_from_agenda"] = True
            else:
                if not street:
                    self.add_error("street", "Este dato está vacío." if number else "No encontramos un domicilio registrado con este celular; escríbelo.")
                if not number:
                    self.add_error("exterior_number", "Este dato está vacío.")
        if self.order_type == Order.OrderType.PICKUP:
            cleaned_data.update({"payment_method": "", "needs_change": False, "cash_tendered": None})
            return cleaned_data

        payment_method = cleaned_data.get("payment_method")
        if payment_method != Order.PaymentMethod.CASH:
            cleaned_data.update({"needs_change": False, "cash_tendered": None})
            return cleaned_data

        selected_values = sum(bool(cleaned_data.get(name)) for name in ("cash_bill", "cash_custom_amount", "pays_exact"))
        if selected_values != 1:
            self.add_error("cash_bill", "No elegiste billete, cantidad ni pago exacto." if not selected_values else "Elegiste más de una opción de efectivo.")
            return cleaned_data
        if cleaned_data.get("pays_exact"):
            cleaned_data.update({"needs_change": False, "cash_tendered": self.cart_total})
            return cleaned_data
        amount = cleaned_data.get("cash_custom_amount")
        if cleaned_data.get("cash_bill"):
            amount = int(cleaned_data["cash_bill"])
        if amount < self.cart_total:
            self.add_error(
                "cash_bill" if cleaned_data.get("cash_bill") else "cash_custom_amount",
                f"${amount} no alcanza para el total de ${self.cart_total}.",
            )
        cleaned_data.update({"needs_change": True, "cash_tendered": amount})
        return cleaned_data
