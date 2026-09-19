# NOTA TEMPORAL PARA APRENDIZAJE:
# El cambio rápido de mesero ya no pide PIN: sólo se puede cambiar hacia un mesero
# que ya inició sesión con su contraseña hoy mismo en esta tablet (ver
# accounts/quick_switch.py). Este formulario sólo valida que se eligió alguien.
# Borra esta nota después de leerla.

from django import forms
from django.contrib.auth import authenticate, get_user_model


class EmployeeLoginForm(forms.Form):
    user = forms.ModelChoiceField(
        label="Perfil",
        queryset=get_user_model().objects.filter(is_active=True).order_by("first_name", "username"),
        empty_label=None,
        widget=forms.Select(attrs={"autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.authenticated_user = None

    def clean(self):
        data = super().clean()
        selected_user = data.get("user")
        password = data.get("password")
        if selected_user and password:
            self.authenticated_user = authenticate(
                self.request,
                username=selected_user.username,
                password=password,
            )
            if self.authenticated_user is None:
                raise forms.ValidationError("La contraseña no es correcta.")
        return data

    def get_user(self):
        return self.authenticated_user


class QuickSwitchForm(forms.Form):
    waiter_id = forms.IntegerField(widget=forms.HiddenInput)
    # NOTA TEMPORAL PARA APRENDIZAJE: la contraseña sólo es obligatoria (y se valida
    # en la vista, no aquí) la primera vez que un mesero se elige en esta tablet en
    # el día; si ya inició sesión hoy, este campo se ignora aunque venga vacío.
    # Borra esta nota después de leerla.
    password = forms.CharField(
        label="Contraseña", required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
