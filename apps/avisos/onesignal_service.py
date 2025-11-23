import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class OneSignalService:
    """Servicio para enviar notificaciones push con OneSignal"""
    
    BASE_URL = 'https://onesignal.com/api/v1'
    
    @staticmethod
    def enviar_notificacion(titulo, mensaje, target_user='all', datos_adicionales=None):
        """
        Envía notificación push a través de OneSignal
        
        Args:
            titulo (str): Título de la notificación
            mensaje (str): Cuerpo del mensaje
            target_user (str): 'all' para todos o ID específico
            datos_adicionales (dict): Datos extra para la app
        
        Returns:
            dict: Respuesta de OneSignal con ID de notificación y recipients
        """
        
        url = f"{OneSignalService.BASE_URL}/notifications"
        
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': f'Basic {settings.ONESIGNAL_REST_API_KEY}'
        }
        
        # Preparar payload
        payload = {
            'app_id': settings.ONESIGNAL_APP_ID,
            'headings': {'en': titulo, 'es': titulo},
            'contents': {'en': mensaje, 'es': mensaje},
            'priority': 10,
            # Configuración para Android
            'android_accent_color': '667EEA',
            'small_icon': 'ic_notification',
            # Configuración para iOS
            'ios_badgeType': 'Increase',
            'ios_badgeCount': 1,
        }
        
        # Agregar datos adicionales
        if datos_adicionales:
            payload['data'] = datos_adicionales
        
        # Determinar a quién enviar
        if target_user == 'all':
            payload['included_segments'] = ['All']
        else:
            # Enviar a usuarios específicos usando tags
            payload['filters'] = [
                {
                    "field": "tag",
                    "key": "userId",
                    "relation": "=",
                    "value": target_user
                }
            ]
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"✅ Notificación enviada. ID: {data.get('id')}, Recipients: {data.get('recipients')}")
            
            return {
                'success': True,
                'notification_id': data.get('id'),
                'recipients': data.get('recipients', 0),
                'errors': data.get('errors', [])
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error enviando notificación: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def enviar_notificacion_test():
        """Envía notificación de prueba"""
        return OneSignalService.enviar_notificacion(
            titulo='🔔 Notificación de Prueba',
            mensaje='Si ves esto, OneSignal está funcionando correctamente!',
            target_user='all'
        )