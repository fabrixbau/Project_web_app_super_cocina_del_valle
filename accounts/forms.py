# NOTA TEMPORAL PARA APRENDIZAJE:
# Configurar el PIN exige la contraseña actual; cambiar de mesero exige solo el PIN en una tablet
# previamente habilitada. La validación sensible permanece en Django. Borra esta nota.

from django import forms


class QuickPinSetupForm(forms.Form):
    current_password = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    pin = forms.RegexField(label="Nuevo PIN", regex=r"^[0-9]{1,10}$", error_messages={"invalid": "Usa entre 1 y 10 dígitos."}, widget=forms.PasswordInput(attrs={"inputmode": "numeric", "maxlength": "10"}))
    pin_confirmation = forms.CharField(label="Confirmar PIN", widget=forms.PasswordInput(attrs={"inputmode": "numeric", "maxlength": "10"}))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.has_existing_pin = bool(hasattr(user, "profile") and user.profile.has_quick_pin)
        if self.has_existing_pin:
            self.fields["pin"].required = False
            self.fields["pin"].label = "Nuevo PIN (opcional)"
            self.fields["pin_confirmation"].required = False
            self.fields["pin_confirmation"].label = "Confirmar nuevo PIN"

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("La contraseña actual no es correcta.")
        return password

    def clean(self):
        data = super().clean()
        if not self.has_existing_pin and not data.get("pin"):
            self.add_error("pin", "Configura un PIN para continuar.")
        if data.get("pin") and data.get("pin_confirmation") != data["pin"]:
            self.add_error("pin_confirmation", "Los PIN no coinciden.")
        if data.get("pin_confirmation") and not data.get("pin"):
            self.add_error("pin", "Escribe el nuevo PIN que deseas confirmar.")
        return data


class QuickSwitchForm(forms.Form):
    waiter_id = forms.IntegerField(widget=forms.HiddenInput)
    pin = forms.RegexField(label="PIN", regex=r"^[0-9]{1,10}$", error_messages={"invalid": "Usa entre 1 y 10 dígitos."}, widget=forms.PasswordInput(attrs={"inputmode": "numeric", "autocomplete": "off", "maxlength": "10"}))
