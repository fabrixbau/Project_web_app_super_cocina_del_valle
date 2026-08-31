# NOTA TEMPORAL PARA APRENDIZAJE:
# TableAccountCloseForm valida forma de pago, propina y las reglas especiales del efectivo.
# Estas reglas viven también en Django y no dependen solo de JavaScript. Borra esta nota.
# Los métodos se ordenan según el flujo visual del mesero: efectivo, transferencia y terminal.
# Reutilizamos las reglas del selector público y añadimos únicamente el refill de mesa.
# En mesa quitamos frijoles/tortillas y permitimos tiempos pendientes; `is_complete`
# informa al servicio si todavía falta una selección. Borra esta nota.

from django import forms

from menu.forms import PackageSelectionForm

from .models import TableAccount


class TablePackageForm(PackageSelectionForm):
    refill_extra = forms.BooleanField(label="Refill extra", required=False)
    customization_comment = forms.CharField(
        label="Comentario para cocina",
        required=False,
        max_length=150,
        widget=forms.Textarea(attrs={
            "rows": 2,
            "placeholder": "Ej. Sin cebolla, bien caliente, servir primero la sopa",
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("order_type", "tortillas", "beans"):
            self.fields.pop(name)
        for name in ("first_course", "second_course", "main_course"):
            self.fields[name].required = False
            self.fields[name].empty_label = "Pendiente"
        for name in ("first_course", "second_course", "main_course", "chicken_piece"):
            choices = self.fields[name].choices
            if name == "chicken_piece":
                choices = [choice for choice in choices if choice[0]]
            self.fields[name].widget = forms.RadioSelect(choices=choices)

    def clean(self):
        cleaned_data = forms.Form.clean(self)
        comment = " ".join((cleaned_data.get("customization_comment") or "").split())
        cleaned_data["customization_comment"] = comment
        cleaned_data["configuration_signature"] = (
            f"comentario:{comment.casefold()}" if comment else ""
        )
        cleaned_data["configuration_snapshot"] = {
            "differences": [comment] if comment else [],
            "comment": comment,
        }
        cleaned_data["is_customized"] = bool(comment)
        main_course = cleaned_data.get("main_course")
        if cleaned_data.get("chicken_piece") and (
            not main_course or main_course.pk != self.daily_menu.chicken_stew_id
        ):
            self.add_error("chicken_piece", "La pieza solo aplica al guisado de pollo.")
        if cleaned_data.get("refill_extra") and not cleaned_data.get("with_water"):
            self.add_error("refill_extra", "El refill solo aplica cuando la comida lleva agua.")
        return cleaned_data

    def is_complete(self):
        courses_complete = all(self.cleaned_data.get(name) for name in (
            "first_course", "second_course", "main_course",
        ))
        main_course = self.cleaned_data.get("main_course")
        chicken_complete = not (
            main_course and main_course.pk == self.daily_menu.chicken_stew_id
        ) or bool(self.cleaned_data.get("chicken_piece"))
        return courses_complete and chicken_complete

    def calculated_total(self):
        total = super().calculated_total()
        if self.cleaned_data.get("refill_extra"):
            total += self.package.table_refill_price
        return total


class TableAccountCloseForm(forms.Form):
    payment_method = forms.ChoiceField(
        label="Forma de pago", choices=(
            (TableAccount.PaymentMethod.CASH, "Efectivo"),
            (TableAccount.PaymentMethod.TRANSFER, "Transferencia"),
            (TableAccount.PaymentMethod.CARD, "Terminal"),
        ),
        widget=forms.RadioSelect,
    )
    tip_amount = forms.DecimalField(
        label="Propina para el mesero", min_value=0, max_digits=10,
        decimal_places=2, initial=0,
    )
    pays_exact = forms.BooleanField(label="Pago exacto", required=False)
    cash_tendered = forms.DecimalField(
        label="Efectivo recibido", required=False, min_value=0,
        max_digits=10, decimal_places=2,
    )

    def __init__(self, *args, account_total, **kwargs):
        super().__init__(*args, **kwargs)
        self.account_total = account_total

    def clean(self):
        cleaned_data = super().clean()
        method = cleaned_data.get("payment_method")
        tip = cleaned_data.get("tip_amount") or 0
        total = self.account_total + tip
        if method != TableAccount.PaymentMethod.CASH:
            cleaned_data["pays_exact"] = False
            cleaned_data["cash_tendered"] = None
            return cleaned_data
        pays_exact = cleaned_data.get("pays_exact")
        cash_tendered = cleaned_data.get("cash_tendered")
        if pays_exact and cash_tendered is not None:
            self.add_error("cash_tendered", "Usa pago exacto o efectivo recibido, no ambos.")
        elif pays_exact:
            cleaned_data["cash_tendered"] = total
        elif cash_tendered is None:
            self.add_error("cash_tendered", "Indica cuánto efectivo recibiste o marca pago exacto.")
        elif cash_tendered < total:
            self.add_error("cash_tendered", "El efectivo recibido no alcanza para cubrir total y propina.")
        return cleaned_data
