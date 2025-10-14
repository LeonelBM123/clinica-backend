def get_actor_usuario_from_request(request):
    """
    Intenta obtener el usuario actor desde el request.
    Retorna None si no se puede obtener.
    """
    try:
        # Si tienes autenticación por token
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Buscar el Usuario correspondiente por email
            from .models import Usuario
            return Usuario.objects.filter(correo=request.user.email).first()
        return None
    except:
        return None


def log_action(request, accion, objeto=None, usuario=None):
    """
    Registra una acción en la bitácora, asegurando grupo_id.
    """
    try:
        from .models import Bitacora

        ip = get_client_ip(request)

        if not usuario:
            usuario = get_actor_usuario_from_request(request)

        grupo = None
        # Si tenemos usuario, tomamos su grupo
        if usuario and hasattr(usuario, 'grupo') and usuario.grupo:
            grupo = usuario.grupo
        else:
            # Si no hay usuario (login, anon, etc.), intentar tomar el grupo del request
            # Por ejemplo, si usas MultiTenantMixin, podrías agregar:
            if hasattr(request, 'user') and request.user.is_authenticated:
                from .models import Usuario
                try:
                    perfil = Usuario.objects.get(correo=request.user.email)
                    grupo = perfil.grupo
                except Usuario.DoesNotExist:
                    pass

        Bitacora.objects.create(
            usuario=usuario,
            grupo=grupo,
            accion=accion,
            ip=ip,
            objeto=objeto
        )

    except Exception as e:
        print(f"Error al registrar en bitácora: {e}")

def get_client_ip(request):
    """
    Obtiene la IP del cliente desde el request.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
