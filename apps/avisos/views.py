from django.shortcuts import render

# Create your views here.

from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Aviso
from .serializers import AvisoSerializer
from .onesignal_service import OneSignalService
import logging

logger = logging.getLogger(__name__)

class AvisoViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar avisos"""
    queryset = Aviso.objects.all()
    serializer_class = AvisoSerializer
    
    def create(self, request):
        """Crear aviso y enviar notificación push"""
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            # Guardar aviso
            aviso = serializer.save()
            
            # Preparar datos adicionales para la notificación
            datos_adicionales = {
                'tipo': 'aviso',
                'avisoId': str(aviso.id),
                'prioridad': aviso.prioridad,
                'fecha': aviso.creado_en.isoformat()
            }
            
            # Enviar notificación push
            resultado = OneSignalService.enviar_notificacion(
                titulo=aviso.titulo,
                mensaje=aviso.mensaje,
                target_user=aviso.target_user,
                datos_adicionales=datos_adicionales
            )
            
            # Guardar ID de notificación
            if resultado['success']:
                aviso.notification_id = resultado['notification_id']
                aviso.save()
                
                logger.info(f"📢 Aviso creado y notificación enviada: {aviso.titulo}")
                
                return Response({
                    'success': True,
                    'message': 'Aviso creado y notificación enviada',
                    'aviso': serializer.data,
                    'notification_id': resultado['notification_id'],
                    'recipients': resultado['recipients']
                }, status=status.HTTP_201_CREATED)
            else:
                logger.warning(f"⚠️ Aviso creado pero error al enviar notificación: {resultado['error']}")
                return Response({
                    'success': False,
                    'message': 'Aviso creado pero error al enviar notificación',
                    'aviso': serializer.data,
                    'error': resultado['error']
                }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['put'])
    def marcar_leido(self, request, pk=None):
        """Marcar aviso como leído"""
        aviso = self.get_object()
        aviso.leido = True
        aviso.save()
        
        serializer = self.get_serializer(aviso)
        return Response({
            'success': True,
            'aviso': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def por_usuario(self, request):
        """Obtener avisos de un usuario específico"""
        user_id = request.query_params.get('userId', 'all')
        
        if user_id == 'all':
            avisos = self.queryset
        else:
            avisos = self.queryset.filter(target_user__in=[user_id, 'all'])
        
        serializer = self.get_serializer(avisos, many=True)
        return Response({
            'avisos': serializer.data
        })
    
    @action(detail=False, methods=['get'])
    def estadisticas(self, request):
        """Obtener estadísticas de avisos"""
        total = Aviso.objects.count()
        leidos = Aviso.objects.filter(leido=True).count()
        no_leidos = Aviso.objects.filter(leido=False).count()
        
        return Response({
            'total_avisos': total,
            'avisos_leidos': leidos,
            'avisos_no_leidos': no_leidos,
            'por_prioridad': {
                'normal': Aviso.objects.filter(prioridad='normal').count(),
                'alta': Aviso.objects.filter(prioridad='alta').count(),
                'urgente': Aviso.objects.filter(prioridad='urgente').count(),
            }
        })

@api_view(['POST'])
def test_notificacion(request):
    """Endpoint para probar notificaciones"""
    resultado = OneSignalService.enviar_notificacion_test()
    
    if resultado['success']:
        return Response({
            'success': True,
            'message': 'Notificación de prueba enviada',
            'notification_id': resultado['notification_id'],
            'recipients': resultado['recipients']
        })
    else:
        return Response({
            'success': False,
            'message': 'Error al enviar notificación',
            'error': resultado['error']
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def health_check(request):
    """Health check para UptimeRobot"""
    return Response({
        'status': 'ok',
        'service': 'Backend Django - Sistema de Avisos',
        'timestamp': timezone.now().isoformat()
    })
