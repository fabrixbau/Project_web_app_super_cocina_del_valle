from django.utils import timezone

# NOTA TEMPORAL PARA APRENDIZAJE:
# Ya no existe PIN. Un mesero sólo necesita iniciar sesión con su contraseña una
# vez al día en esta tablet; a partir de ahí, cambiar entre meseros que ya hicieron
# ese inicio de sesión hoy no vuelve a pedir nada. Django reinicia la sesión cada
# vez que login() autentica a un usuario distinto (protección contra fijación de
# sesión), así que quien llama a login() debe guardar una copia de este diccionario
# antes y restaurarla después con snapshot_daily_logins()/restore_daily_logins().
# Borra esta nota después de leerla.

IDLE_SECONDS = 180
LOCK_KEY = "quick_switch_locked"
DAILY_LOGINS_KEY = "quick_switch_daily_logins"


def _today_key():
    return timezone.localdate().isoformat()


def snapshot_daily_logins(session):
    """Copia los inicios de sesión de hoy antes de un login() que reinicia la sesión."""
    return dict(session.get(DAILY_LOGINS_KEY) or {})


def register_daily_login(session, user_id):
    """Marca que este usuario inició sesión con su contraseña hoy en esta tablet."""
    logins = session.get(DAILY_LOGINS_KEY) or {}
    logins[str(user_id)] = _today_key()
    session[DAILY_LOGINS_KEY] = logins
    session[LOCK_KEY] = False
    session.modified = True


def restore_daily_logins(session, snapshot, *, user_id=None):
    """Recupera los inicios de sesión previos a un login() y, si se indica, agrega
    o renueva el del usuario que acaba de autenticarse."""
    session[DAILY_LOGINS_KEY] = snapshot
    session.modified = True
    if user_id is not None:
        register_daily_login(session, user_id)


def logged_in_today_ids(session):
    """IDs de usuarios que ya iniciaron sesión con su contraseña hoy en esta tablet."""
    logins = session.get(DAILY_LOGINS_KEY) or {}
    today = _today_key()
    return {int(user_id) for user_id, day in logins.items() if day == today}
