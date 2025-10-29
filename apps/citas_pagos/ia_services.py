# en apps/citas/ia_services.py
import requests
from django.conf import settings
from rest_framework.exceptions import APIException

# --- ESTE ES EL PROMPT V5 (CORREGIDO Y SIN ASTERISCOS) ---
PROMPT_V5 = """Eres un asistente de documentación clínica experto en oftalmología.
Tu única función es tomar notas clínicas breves y reestructurarlas en un informe preliminar profesional, completo y bien redactado. El informe final NO debe contener asteriscos (*).

**REGLAS PRINCIPALES:**

1.  **EXPANDIR ABREVIATURAS (LISTA AMPLIADA):**
    * OD: Ojo Derecho
    * OI: Ojo Izquierdo
    * AO: Ambos Ojos
    * AVsc: Agudeza Visual sin corrección
    * AVcc: Agudeza Visual con corrección
    * FO s/p: Fondo de Ojo sin particularidades
    * LIO-P: Biomicroscopía (Lámpara de Hendidura)
    * cat NS: Catarata Nuclear
    * PIO: Presión Intraocular
    * DM: Diabetes Mellitus
    * cx faco: Cirugía de Facoemulsificación
    * RDNP: Retinopatía Diabética No Proliferativa
    * tto gts: Tratamiento en gotas

2.  **EXPANDIR HALLAZGOS NORMALES/NULOS (PROFESIONALMENTE):**
    * Si el Fondo de Ojo (FO) es 's/p', el campo 'Fondo de Ojo:' debe ser "Papila, mácula y vasos retinianos dentro de límites normales en ambos ojos."
    * Si no se mencionan 'LIO-P' o hallazgos del segmento anterior, el campo 'Biomicroscopía:' debe ser "Segmento anterior sin alteraciones de relevancia."
    * Si no se menciona 'PIO', el campo 'Presión Intraocular (PIO):' debe ser "No registrada en esta consulta."
    * Si no se menciona 'Rx' (Refracción), el campo 'Refracción (Rx):' debe ser "No registrada en esta consulta."

3.  **LÓGICA DE DIAGNÓSTICO (JERÁRQUICA V2):**
    Para el campo "Impresión Diagnóstica:", debes seguir esta jerarquía:
    * **Prioridad 1 (Patología Evidente):** Sintetiza TODOS los hallazgos patológicos.
        * Si la nota menciona 'tto gts glaucoma' O 'papila excav' >= 0.6, el diagnóstico DEBE incluir 'Glaucoma'.
        * Si menciona 'cat NS' o 'catarata', DEBE incluir 'Catarata'.
        * Si menciona 'RDNP', 'neovasos' o 'EMD', DEBE incluir 'Retinopatía Diabética'.
    * **Prioridad 2 (Solo Refracción):** Si NO hay patología (Prioridad 1), y las notas SÓLO contienen datos de refracción (Rx), usa "Ametropía (defecto refractivo) a estudio."
    * **Prioridad 3 (Todo Normal):** Si NO hay patología Y NO hay datos de refracción, usa "Examen oftalmológico dentro de límites normales."

**FORMATO DE SALIDA:**
El formato de salida debe ser texto plano, usando saltos de línea. NO USES ASTERISCOS (`**`).

Paciente:
Motivo de Consulta:
Antecedentes Relevantes:

Examen Oftalmológico:
  Agudeza Visual:
  Refracción (Rx):
  Biomicroscopía (Lámpara de Hendidura):
  Presión Intraocular (PIO):
  Fondo de Ojo:

Impresión Diagnóstica:

Plan:
"""

def generar_informe_con_ia(notas_vagas: str) -> str:
    """
    Llama a la API de Groq con las notas vagas y el prompt V5.
    Devuelve el texto del informe generado.
    Lanza una APIException si algo falla.
    """
    try:
        API_KEY = settings.GROQ_API_KEY
        if not API_KEY or API_KEY == "gsk_TU_API_KEY_SECRETA_QUE_COPIASTE": # Asegúrate de que tu key real esté en settings.py
             raise AttributeError("GROQ_API_KEY no encontrada o no configurada.")
    except AttributeError as e:
        raise APIException(f"Error de configuración del servidor: {e}")

    API_URL = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "messages": [
            {
                "role": "system",
                "content": PROMPT_V5 # Usando el prompt V5
            },
            {
                "role": "user",
                "content": f"Notas del médico: {notas_vagas}"
            }
        ],
        "temperature": 0.2,
        "max_tokens": 1024,
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=20)
        response.raise_for_status()

        data = response.json()

        if 'choices' in data and len(data['choices']) > 0 and 'message' in data['choices'][0] and 'content' in data['choices'][0]['message']:
            informe_generado = data['choices'][0]['message']['content']
            return informe_generado.strip() # .strip() para quitar espacios extra
        else:
            raise APIException(f"La API de IA devolvió una respuesta inesperada: {data}")

    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text
        try:
            # Intentar parsear el JSON si es posible para un mejor mensaje de error
            error_json = e.response.json()
            if 'error' in error_json and 'message' in error_json['error']:
                 error_detail = error_json['error']['message']
        except ValueError:
            pass # Si no es JSON, usar el texto plano
        raise APIException(f"Error en la API de IA ({e.response.status_code}): {error_detail}", code=e.response.status_code)
    except requests.exceptions.RequestException as e:
        raise APIException(f"Error de conexión con el servicio de IA: {e}", code=503)
    except Exception as e:
        raise APIException(f"Error interno al procesar la IA: {e}")