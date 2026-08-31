from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    # NOTA TEMPORAL PARA APRENDIZAJE:
    # El PIN nunca se guarda legible: Django conserva un hash igual que con una contraseña.
    # Los contadores permiten frenar intentos repetidos en la tablet compartida. Borra esta nota.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    image = models.ImageField(upload_to="profiles/", blank=True)
    quick_pin_hash = models.CharField(max_length=128, blank=True)
    pin_failed_attempts = models.PositiveSmallIntegerField(default=0)
    pin_locked_until = models.DateTimeField(null=True, blank=True)

    @property
    def has_quick_pin(self):
        return bool(self.quick_pin_hash)

    @property
    def pin_is_locked(self):
        return bool(self.pin_locked_until and self.pin_locked_until > timezone.now())

    def set_quick_pin(self, pin):
        self.quick_pin_hash = make_password(pin)
        self.pin_failed_attempts = 0
        self.pin_locked_until = None

    def check_quick_pin(self, pin):
        return bool(self.quick_pin_hash) and check_password(pin, self.quick_pin_hash)

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()
