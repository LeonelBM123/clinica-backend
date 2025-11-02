import spacy
from spacy.matcher import Matcher
from spacy.pipeline import EntityRuler
import traceback
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


nlp = None
matcher = None

def _convertir_entidad_fecha(entidad_texto: str) -> dict:
    """
    Convierte un texto de entidad (ej: "ULTIMO_MES") en un rango de fechas real.
    """
    hoy = datetime.now().date()
    fecha_inicio = None
    fecha_fin = hoy

    try:
        if entidad_texto == "HOY":
            fecha_inicio = hoy
        elif entidad_texto == "AYER":
            fecha_inicio = hoy - timedelta(days=1)
            fecha_fin = fecha_inicio
        elif entidad_texto == "ULTIMA_SEMANA":
            fecha_inicio = hoy - timedelta(days=7)
        elif entidad_texto == "ULTIMO_MES":
            fecha_inicio = hoy - relativedelta(months=1)
        
        if fecha_inicio:
            return {
                "fecha_inicio": fecha_inicio.isoformat(),
                "fecha_fin": fecha_fin.isoformat()
            }
    except Exception as e:
        print(f"[NLP ERROR] No se pudo convertir la fecha para '{entidad_texto}': {e}")
    
    return {}


try:
    #cargar el modelode spacy en español
    print("[NLP Service] Intentando cargar 'es_core_news_sm'...")
    nlp = spacy.load("es_core_news_sm")
    print("[NLP Service] ¡Éxito! Modelo cargado.")

except IOError:
    print("[NLP Service] Método 1 falló. Intentando Método 2 ...")
    try:
        #si no funciona el metodo 1 importar directamente el paqueton
        import es_core_news_sm
        nlp = es_core_news_sm.load()
        print("[NLP Service] ¡Éxito! Modelo cargado (Método 2).")
    except Exception:
        #solo depuracion
        print("[NLP Service] ERROR CRÍTICO: No se pudo cargar el modelo spaCy.")
        print("Asegúrate de haber ejecutado en tu .venv:")
        print("1. pip install spacy python-dateutil")
        print("2. python -m spacy download es_core_news_sm")
        print("3. Reinicia este servidor de Django.")
        traceback.print_exc()
        nlp = None

#definicion de patrones
if nlp:
    #definicion de fechas
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    patterns = [
        {"label": "FECHA_RELATIVA", "pattern": "hoy", "id": "HOY"},
        {"label": "FECHA_RELATIVA", "pattern": "ayer", "id": "AYER"},
        {"label": "FECHA_RELATIVA", "pattern": [{"LOWER": "última"}, {"LOWER": "semana"}], "id": "ULTIMA_SEMANA"},
        {"label": "FECHA_RELATIVA", "pattern": [{"LOWER": "último"}, {"LOWER": "mes"}], "id": "ULTIMO_MES"},
    ]
    ruler.add_patterns(patterns)
    
    #definir lo que se quiere
    matcher = Matcher(nlp.vocab)
    
    #todos llevan a la desarga de un pdf o navegacion al dashboard
    pattern_pdf_pacientes = [{"LOWER": {"IN": ["reporte", "listado", "descargar"]}}, {"LOWER": "de", "OP": "?"}, {"LOWER": "pacientes"}]
    pattern_pdf_medicos = [{"LOWER": {"IN": ["reporte", "listado", "descargar"]}}, {"LOWER": "de", "OP": "?"}, {"LOWER": "médicos"}]
    pattern_pdf_citas = [{"LOWER": {"IN": ["reporte", "listado", "descargar"]}}, {"LOWER": "de", "OP": "?"}, {"LOWER": "citas"}]

    pattern_dash_pacientes = [{"LOWER": "dashboard"}, {"LOWER": "de", "OP": "?"}, {"LOWER": "pacientes"}]
    pattern_dash_citas = [{"LOWER": "dashboard"}, {"LOWER": "de", "OP": "?"}, {"LOWER": "citas"}]

    matcher.add("REPORTE_PDF_PACIENTES", [pattern_pdf_pacientes])
    matcher.add("REPORTE_PDF_MEDICOS", [pattern_pdf_medicos])
    matcher.add("REPORTE_PDF_CITAS", [pattern_pdf_citas])
    matcher.add("REPORTE_DASH_PACIENTES", [pattern_dash_pacientes])
    matcher.add("REPORTE_DASH_CITAS", [pattern_dash_citas])
    
    print("[NLP Service] Patrones de voz e intenciones cargados.")
else:
    print("[NLP Service] ADVERTENCIA: NLP deshabilitado (modelo no cargado).")



def procesar_comando_voz(texto: str) -> dict:
    if not nlp or not matcher:
        return {"error": "Servicio NLP no inicializado."}
        
    doc = nlp(texto.lower())
    
    #encontrar la intencion
    matches = matcher(doc)
    if not matches:
        return {"error": "Comando no reconocido. Intente 'reporte de pacientes de ayer'."}

    matches.sort(key=lambda x: x[2] - x[1], reverse=True)
    match_id, start, end = matches[0]
    intent_string = nlp.vocab.strings[match_id]
    print(f"[NLP DEBUG] Comando '{texto}' -> Intención: {intent_string}")
    
    #encontrar entidades como fechas
    params = {}
    for ent in doc.ents:
        if ent.label_ == "FECHA_RELATIVA":
            entidad_id = ent.ent_id_
            print(f"[NLP DEBUG] Entidad encontrada: {ent.text} (ID: {entidad_id})")
            params.update(_convertir_entidad_fecha(entidad_id))
            break 

    # mapeo con los reportes estaticos que ya estan
    
    if intent_string == "REPORTE_PDF_PACIENTES":
        return {
            "accion": "descargar",
            "reporte_id": "pacientes",
            "url": "/reportes/pacientes/pdf/",
            "fileName": "listado_pacientes.pdf",
            "params": params 
        }
        
    elif intent_string == "REPORTE_PDF_MEDICOS":
        return {
            "accion": "descargar",
            "reporte_id": "medicos",
            "url": "/reportes/medicos/pdf/",
            "fileName": "listado_medicos.pdf",
            "params": params
        }

    elif intent_string == "REPORTE_PDF_CITAS":
        return {
            "accion": "descargar",
            "reporte_id": "citas",
            "url": "/reportes/citas/pdf/",
            "fileName": "reporte_citas.pdf",
            "params": params
        }

    elif intent_string == "REPORTE_DASH_CITAS":
        return {
            "accion": "navegar",
            "reporte_id": "citas",
            "url": "/dashboard/reportes/personalizar/citas",
            "params": params
        }

    elif intent_string == "REPORTE_DASH_PACIENTES":
        return {
            "accion": "navegar",
            "reporte_id": "pacientes",
            "url": "/dashboard/reportes/personalizar/pacientes",
            "params": params
        }

    return {"error": "Intención no mapeada."}

