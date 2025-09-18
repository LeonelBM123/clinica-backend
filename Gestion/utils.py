# Gestion/utils.py
from .models import Bitacora, Usuario

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')

def get_actor_usuario_from_request(request):
    """
    Intenta obtener la instancia Usuario (modelo de la app) a partir del Django user
    que viene en request.user (usando el correo como vínculo).
    Devuelve None si no existe.
    """
    if not request or not hasattr(request, "user"):
        return None
    django_user = request.user
    if not getattr(django_user, "is_authenticated", False):
        return None
    # Intentamos mapear por email (ustedes usan correo como username/email)
    correo = getattr(django_user, "email", None) or getattr(django_user, "username", None)
    if not correo:
        return None
    try:
        return Usuario.objects.get(correo=correo)
    except Usuario.DoesNotExist:
        return None

def log_action(request=None, accion="", objeto=None, extra=None, usuario=None):
    """
    Crea un registro en Bitacora.
    - usuario puede ser None (para acciones anónimas)
    """
    actor = usuario or get_actor_usuario_from_request(request)
    ip = get_client_ip(request) if request is not None else None
    return Bitacora.objects.create(
        usuario=actor,  # puede ser None
        accion=accion,
        ip=ip,
        objeto=objeto,
        extra=extra or {}
    )