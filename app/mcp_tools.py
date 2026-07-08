from typing import Any

from app.rag_search import search_context
from app.sql_generator import build_sql_prompt, generate_sql_from_context, reconstruct_sql_on_error
from app.config import settings
from app.security import validate_readonly_sql
from app.db import run_select
from app.query_store import save_candidate, log_query_execution

# Plantillas recomendadas para que el agente sepa qué incluir en un informe.
REPORT_BLUEPRINTS = {
    "fraud": {
        "report_type": "fraud",
        "title": "Informe ejecutivo de fraude transaccional",
        "recommended_audience": "dirección",
        "default_period": "último año disponible",
        "sections": [
            {
                "id": "fraud_overview",
                "title": "Resumen general del fraude",
                "question": (
                    "¿Cuál es el volumen total de transacciones, el número de transacciones "
                    "fraudulentas, el importe total, el importe fraudulento y la tasa de fraude?"
                ),
                "priority": "required",
            },
            {
                "id": "monthly_fraud_evolution",
                "title": "Evolución mensual del fraude",
                "question": (
                    "¿Cuál es la evolución mensual del fraude en número de operaciones, "
                    "importe total fraudulento y tasa de fraude durante el periodo analizado?"
                ),
                "priority": "required",
            },
            {
                "id": "fraud_by_card_type",
                "title": "Fraude por tipo de tarjeta",
                "question": (
                    "¿Qué tipos de tarjeta presentan mayor volumen de fraude, importe "
                    "fraudulento y tasa de fraude?"
                ),
                "priority": "recommended",
            },
            {
                "id": "fraud_by_merchant_category",
                "title": "Fraude por categoría de comercio",
                "question": (
                    "¿Qué categorías de comercio presentan mayor volumen de fraude, "
                    "importe fraudulento y tasa de fraude?"
                ),
                "priority": "recommended",
            },
            {
                "id": "fraud_by_channel",
                "title": "Fraude por canal de operación",
                "question": (
                    "¿Cómo se distribuye el fraude según el método de uso de tarjeta "
                    "o canal de operación?"
                ),
                "priority": "optional",
            },
            {
                "id": "fraud_geography",
                "title": "Concentración geográfica del fraude",
                "question": (
                    "¿Qué ciudades o estados concentran más transacciones fraudulentas "
                    "e importe fraudulento?"
                ),
                "priority": "optional",
            },
        ],
    }
}

def tool_get_context(question: str) -> dict:
    """
    Recupera documentos de contexto desde Azure AI Search.

    Args:
        question (str): La pregunta del usuario.

    Returns:
        dict: Diccionario con la pregunta, documentos encontrados y cantidad de documentos.
    """
    # Obtiene los documentos mas relevantes para la pregunta.
    docs = search_context(question, top=settings.SEARCH_TOP_DOCS)

    return {
        "question": question,
        "documents": docs,
        "document_count": len(docs),
    }

def tool_generate_sql(question: str, debug: bool = settings.SQL_DEBUG_CONTEXT) -> dict:
    """
    Genera SQL a partir del contexto y devuelve metadatos de seguridad.

    Args:
        question (str): La pregunta del usuario.
        debug (bool, optional): Indica si se debe incluir información de depuración.

    Returns:
        dict: Diccionario con la consulta SQL generada y resultados de validación.
    """
    # Recupera contexto y construye el prompt para el modelo.
    docs = search_context(question, top=settings.SEARCH_TOP_DOCS)
    prompt = build_sql_prompt(question, docs)
    sql = generate_sql_from_context(question, docs)
    safe, reason = validate_readonly_sql(sql)

    response = {
        "question": question,
        "sql": sql,
        "safe": safe,
        "reason": reason,
        "context_documents": [
            {
                "id": d.get("id"),
                "doc_type": d.get("doc_type"),
                "title": d.get("title"),
                "score": d.get("score"),
            }
            for d in docs
        ],
    }

    if debug:
        # Expone informacion adicional para depuracion.
        response["prompt"] = prompt
        response["full_context_documents"] = docs

    return response

def _execute_query_with_retry(question: str) -> dict:
    """
    Ejecuta una consulta SQL con reintentos automáticos en caso de error usando LLM para reconstrucción,
    y registra el resultado final para las estadísticas del dashboard.

    Args:
        question (str): La pregunta original del usuario.

    Returns:
        dict: Resultado de la ejecución con su estado de éxito, columnas, filas o errores.
    """
    res = _execute_query_with_retry_internal(question)
    
    # Registrar ejecución para el cálculo de éxito
    if "success" in res:
        try:
            log_query_execution(res["success"])
        except Exception:
            pass
            
    return res

def _execute_query_with_retry_internal(question: str) -> dict:
    """
    Función interna que ejecuta la consulta y maneja los reintentos.
    """
    docs = search_context(question, top=settings.SEARCH_TOP_DOCS)
    
    try:
        current_sql = generate_sql_from_context(question, docs)
    except Exception as exc:
        return {
            "success": False,
            "safe": True,
            "sql": None,
            "error": f"Error de generación inicial: {str(exc)}",
            "context_documents": docs,
            "attempts": []
        }

    attempts = []
    max_retries = settings.SQL_MAX_RETRIES
    
    for attempt_idx in range(max_retries + 1):
        safe, reason = validate_readonly_sql(current_sql)
        if not safe:
            return {
                "success": False,
                "safe": False,
                "sql": current_sql,
                "error": reason,
                "context_documents": docs,
                "attempts": attempts
            }
            
        try:
            result = run_select(current_sql)
            
            try:
                context_ids = [d.get("id") for d in docs if d.get("id")]
                sample = result["rows"][:settings.QUERY_STORE_SAMPLE_ROWS]
                save_candidate(
                    question=question,
                    sql=current_sql,
                    columns=result["columns"],
                    row_count=result["row_count"],
                    sample_rows=sample,
                    context_doc_ids=context_ids,
                )
            except Exception:
                pass
                
            return {
                "success": True,
                "safe": True,
                "sql": current_sql,
                "columns": result["columns"],
                "rows": result["rows"],
                "row_count": result["row_count"],
                "row_format": result["row_format"],
                "context_documents": docs,
                "attempts": attempts,
            }
        except Exception as exc:
            error_str = str(exc)
            attempts.append({
                "attempt": attempt_idx + 1,
                "sql": current_sql,
                "error": error_str
            })
            
            if attempt_idx >= max_retries:
                break
                
            try:
                current_sql = reconstruct_sql_on_error(question, docs, current_sql, error_str)
            except Exception as llm_exc:
                return {
                    "success": False,
                    "safe": True,
                    "sql": current_sql,
                    "error": f"Error de BD: {error_str}. Falló la reconstrucción por IA: {str(llm_exc)}",
                    "context_documents": docs,
                    "attempts": attempts
                }
                
    return {
        "success": False,
        "safe": True,
        "sql": current_sql,
        "error": f"Fallo tras {max_retries + 1} intentos. Último error: {attempts[-1]['error']}",
        "context_documents": docs,
        "attempts": attempts
    }

def tool_ask_database(question: str) -> dict:
    """
    Genera SQL, valida y ejecuta contra PostgreSQL si es seguro.

    Args:
        question (str): La pregunta analítica del usuario.

    Returns:
        dict: Resultados de la consulta, incluyendo seguridad, error, o filas resultantes.
    """
    res = _execute_query_with_retry(question)

    ctx_docs = [
        {
            "id": d.get("id"),
            "doc_type": d.get("doc_type"),
            "title": d.get("title"),
            "score": d.get("score"),
        }
        for d in res["context_documents"]
    ]

    if not res["success"]:
        return {
            "question": question,
            "sql": res["sql"],
            "safe": res["safe"],
            "error": res["error"],
            "context_documents": ctx_docs,
            "attempts": res.get("attempts", [])
        }

    return {
        "question": question,
        "sql": res["sql"],
        "safe": True,
        "columns": res["columns"],
        "rows": res["rows"],
        "row_format": res["row_format"],
        "row_count": res["row_count"],
        "attempts": res.get("attempts", [])
    }



# Herramienta que ejecuta las preguntas/secciones necesarias para construir un informe ejecutivo
def tool_generate_executive_report(
    report_title: str,
    user_request: str,
    sections: list[dict],
    audience: str = "dirección",
    period: str | None = None,
    include_sql: bool = True,
    include_tables: bool = True,
    max_rows_per_section: int = settings.REPORT_MAX_ROWS_PER_SECTION,
) -> dict:
    """
    Ejecuta las preguntas/secciones necesarias para construir un informe ejecutivo.

    Esta función NO redacta el informe final. Devuelve evidencias estructuradas:
    SQL, columnas, filas, errores y advertencias para que el agente redacte el informe.

    Args:
        report_title (str): Título del informe a generar.
        user_request (str): Solicitud original del usuario.
        sections (list[dict]): Lista de secciones que componen el informe.
        audience (str, optional): Audiencia objetivo. Por defecto 'dirección'.
        period (str | None, optional): Periodo de tiempo a analizar.
        include_sql (bool, optional): Si se incluye SQL en la respuesta. Por defecto True.
        include_tables (bool, optional): Si se incluyen filas. Por defecto True.
        max_rows_per_section (int, optional): Máximo de filas por sección. Por defecto 50.

    Returns:
        dict: Resultados compilados del informe con advertencias y directrices para el agente.
    """

    if not sections:
        return {
            "status": "failed",
            "error": "No se han proporcionado secciones para el informe.",
            "expected_section_format": {
                "id": "fraud_overview",
                "title": "Resumen general del fraude",
                "question": "¿Cuál es el volumen total de fraude?",
            },
        }

    executed_sections = []
    global_warnings = []
    completed_count = 0
    failed_count = 0
    rejected_count = 0

    for index, raw_section in enumerate(sections):
        section = _normalize_section(raw_section, index)

        section_id = section["id"]
        title = section["title"]
        question = section["question"]

        if raw_section.get("sql"):
            failed_count += 1
            executed_sections.append({
                "id": section_id,
                "title": title,
                "question": question,
                "status": "failed",
                "safe": False,
                "error": "No se acepta SQL en las secciones. Envia solo 'question'.",
            })
            continue

        if not question:
            failed_count += 1
            executed_sections.append({
                "id": section_id,
                "title": title,
                "status": "failed",
                "error": "La sección no contiene question.",
            })
            continue

        try:
            res = _execute_query_with_retry(question)
            
            context_documents = [
                {
                    "id": d.get("id"),
                    "doc_type": d.get("doc_type"),
                    "title": d.get("title"),
                    "score": d.get("score"),
                }
                for d in res["context_documents"]
            ]
            
            if not res["success"]:
                if not res.get("safe", True):
                    rejected_count += 1
                    executed_sections.append({
                        "id": section_id,
                        "title": title,
                        "question": question,
                        "status": "rejected",
                        "safe": False,
                        "error": res["error"],
                        "sql": res["sql"] if include_sql else None,
                        "context_documents": context_documents,
                    })
                else:
                    failed_count += 1
                    executed_sections.append({
                        "id": section_id,
                        "title": title,
                        "question": question,
                        "status": "failed",
                        "safe": True,
                        "sql": res["sql"] if include_sql else None,
                        "error": res["error"],
                        "context_documents": context_documents,
                        "attempts": res.get("attempts", [])
                    })
                continue

            rows = res["rows"]
            trimmed_rows = _trim_rows(rows, max_rows_per_section)
            completed_count += 1

            executed_section = {
                "id": section_id,
                "title": title,
                "question": question,
                "priority": section["priority"],
                "status": "completed",
                "safe": True,
                "generation_mode": "generated_sql",
                "columns": res["columns"],
                "row_count": res["row_count"],
                "returned_row_count": len(trimmed_rows),
                "row_format": res["row_format"],
            }

            if include_sql:
                executed_section["sql"] = res["sql"]

            if include_tables:
                executed_section["rows"] = trimmed_rows

            if context_documents:
                executed_section["context_documents"] = context_documents
                
            if res.get("attempts"):
                executed_section["attempts"] = res["attempts"]

            if res["row_count"] > max_rows_per_section:
                executed_section["warning"] = (
                    f"La consulta devolvió {res['row_count']} filas, "
                    f"pero solo se devuelven {max_rows_per_section}."
                )

            executed_sections.append(executed_section)

        except Exception as exc:
            failed_count += 1
            executed_sections.append({
                "id": section_id,
                "title": title,
                "question": question,
                "status": "failed",
                "safe": True,
                "sql": None,
                "error": str(exc),
            })

    if completed_count == len(sections):
        status = "completed"
    elif completed_count > 0:
        status = "partial"
    else:
        status = "failed"

    if period is None:
        global_warnings.append(
            "No se ha indicado un periodo explícito. Las preguntas generadas por el agente "
            "deben incluir el periodo deseado si es relevante para el informe."
        )

    return {
        "status": status,
        "report_title": report_title,
        "user_request": user_request,
        "audience": audience,
        "period": period,
        "section_count": len(sections),
        "completed_sections": completed_count,
        "failed_sections": failed_count,
        "rejected_sections": rejected_count,
        "sections": executed_sections,
        "global_warnings": global_warnings,
        "agent_instructions": [
            "Redacta el informe final usando únicamente los datos devueltos en sections.",
            "No inventes métricas, porcentajes ni conclusiones que no estén soportadas por los resultados.",
            "Si una sección aparece como failed o rejected, menciónalo como limitación.",
            "Si hay global_warnings, tenlas en cuenta al redactar el informe.",
            "No incluyas SQL en las secciones; solo aporta questions.",
            "Incluye el SQL solo si el usuario lo solicita o si es necesario para trazabilidad.",
        ],
    }


def _normalize_section(section: dict, index: int) -> dict:
    """
    Normaliza una sección enviada por el agente.
    Permite que el agente envíe id, title y question.

    Args:
        section (dict): La sección a normalizar.
        index (int): Índice de la sección para valores por defecto.

    Returns:
        dict: Sección normalizada.
    """

    section_id = section.get("id") or f"section_{index + 1}"
    title = section.get("title") or f"Sección {index + 1}"
    question = section.get("question")
    return {
        "id": section_id,
        "title": title,
        "question": question,
        "priority": section.get("priority", "required"),
    }


def _trim_rows(rows: list[Any], max_rows: int) -> list[Any]:
    """
    Limita el número de filas devueltas por sección para no saturar al agente.

    Args:
        rows (list[Any]): Lista de filas original.
        max_rows (int): Límite de filas.

    Returns:
        list[Any]: Lista truncada de filas.
    """
    if not rows:
        return []

    return rows[:max_rows]



def tool_get_report_blueprint() -> dict:
    """
    Devuelve todos los blueprints de informes disponibles como ejemplos de referencia
    de estructura y sintaxis.

    Úsala ANTES de llamar a generate_executive_report para entender el formato
    esperado de las secciones. Los blueprints incluidos son ejemplos reales del dominio
    de este servidor; puedes adaptar su estructura para construir cualquier otro tipo
    de informe personalizado.

    No requiere parámetros, no usa IA generativa, no ejecuta SQL y no consulta
    la base de datos.

    Returns:
        dict: Blueprints disponibles e instrucciones de uso.
    """

    return {
        "status": "completed",
        "description": (
            "Los blueprints son plantillas de ejemplo que muestran la estructura y sintaxis "
            "esperada por generate_executive_report. Puedes usarlas tal cual o como base para "
            "construir secciones propias adaptadas a la petición del usuario."
        ),
        "available_blueprints": REPORT_BLUEPRINTS,
        "section_field_reference": {
            "id": "Identificador único de la sección (string, sin espacios).",
            "title": "Título descriptivo de la sección para el informe final.",
            "question": (
                "Pregunta en lenguaje natural que describe qué dato se quiere obtener. "
                "Este campo es el único que generate_executive_report necesita por sección."
            ),
            "priority": (
                "Nivel de importancia: 'required' (siempre incluir), "
                "'recommended' (incluir si es relevante) u 'optional' (incluir si hay espacio)."
            ),
        },
        "usage_instructions": [
            "Revisa los blueprints disponibles para entender la estructura de secciones.",
            "Crea o adapta secciones propias siguiendo el mismo formato si los blueprints "
            "no cubren exactamente la petición del usuario.",
            "Pasa las secciones seleccionadas a generate_executive_report usando solo "
            "los campos 'id', 'title' y 'question'. No incluyas SQL.",
            "Redacta el informe final únicamente con los resultados devueltos por "
            "generate_executive_report.",
        ],
    }