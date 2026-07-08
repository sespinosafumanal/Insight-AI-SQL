from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI
import concurrent.futures

from app.config import settings

def get_openai_client() -> AzureOpenAI:
    """
    Crea un cliente de Azure OpenAI configurado con el entorno.

    Returns:
        AzureOpenAI: Cliente configurado.
    """
    return AzureOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

def get_search_client() -> SearchClient:
    """
    Crea un cliente de Azure AI Search para consultar el indice.

    Returns:
        SearchClient: Cliente de búsqueda configurado.
    """
    return SearchClient(
        endpoint=settings.AZURE_SEARCH_ENDPOINT,
        index_name=settings.AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(settings.AZURE_SEARCH_API_KEY),
    )


def _normalize_value(value):
    """
    Normaliza valores opcionales devueltos por el indice.

    Args:
        value: Valor a normalizar.

    Returns:
        Valor normalizado o None.
    """
    if value is None:
        return None

    if isinstance(value, list):
        return [item for item in value if item is not None]

    return value


def _get_question_embedding(question: str) -> list[float] | None:
    """
    Calcula el embedding si hay deployment configurado.

    Args:
        question (str): La pregunta a vectorizar.

    Returns:
        list[float] | None: Lista de floats que representan el vector, o None si no hay deployment.
    """
    if not settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT:
        return None

    client = get_openai_client()
    response = client.embeddings.create(
        model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        input=question,
    )

    return response.data[0].embedding


def _format_doc_search_score(score) -> float | None:
    """
    Convierte el score a float y lo redondea para salida.

    Args:
        score: Puntuación cruda de la búsqueda.

    Returns:
        float | None: Puntuación redondeada, o None si falla.
    """
    if score is None:
        return None

    try:
        return round(float(score), 4)
    except (TypeError, ValueError):
        return None


def format_context_docs_for_prompt(context_docs: list[dict]) -> str:
    """
    Convierte documentos en un bloque de texto para el prompt.

    Args:
        context_docs (list[dict]): Lista de documentos recuperados de AI Search.

    Returns:
        str: Cadena de texto formateada para insertar en el prompt.
    """
    sections: list[str] = []

    for index, doc in enumerate(context_docs, start=1):
        metadata_lines = [
            f"ID: {doc.get('id')}",
            f"Tipo: {doc.get('doc_type')}",
            f"Título: {doc.get('title')}",
            f"Tabla: {doc.get('table_name')}",
            f"Columna: {doc.get('column_name')}",
            f"Sistema origen: {doc.get('source_system')}",
            f"Dialect SQL: {doc.get('sql_dialect')}",
            f"Tags: {', '.join(doc.get('tags') or []) if doc.get('tags') else 'N/A'}",
            f"Tablas relacionadas: {', '.join(doc.get('related_tables') or []) if doc.get('related_tables') else 'N/A'}",
            f"Columnas relacionadas: {', '.join(doc.get('related_columns') or []) if doc.get('related_columns') else 'N/A'}",
            f"Creado: {doc.get('created_at')}",
            f"Actualizado: {doc.get('updated_at')}",
            f"Score: {doc.get('score')}",
        ]

        content = (doc.get('content') or '').strip()
        sections.append(
            f"DOC {index}\n" + "\n".join(metadata_lines) + f"\n\nContenido:\n{content}"
        )

    return "\n\n---\n\n".join(sections)

def search_context(question: str, top: int = 5, max_query_example_pct: float = None) -> list[dict]:
    """
    Busca contexto en Azure AI Search realizando múltiples consultas en paralelo.
    Garantiza estrictamente que la proporción de 'query_examples' no supere
    el porcentaje indicado, permitiendo que otros tipos de documentos (DDL, negocio)
    no sean desplazados en los resultados.

    Args:
        question (str): Pregunta a buscar.
        top (int, optional): Número máximo total de resultados a devolver. Por defecto 5.
        max_query_example_pct (float, optional): Porcentaje máximo de 'query_examples' (0.0 a 1.0). Toma el valor del .env por defecto.


    Returns:
        list[dict]: Lista de documentos más relevantes, combinados y ordenados por score.
    """
    client = get_search_client()
    question_embedding = None

    try:
        question_embedding = _get_question_embedding(question)
    except Exception:
        question_embedding = None

    select_fields = [
        "id", "doc_type", "title", "content", "table_name",
        "column_name", "source_system", "sql_dialect", "tags",
        "related_tables", "related_columns", "created_at", "updated_at",
    ]

    if max_query_example_pct is None:
        max_query_example_pct = settings.MAX_QUERY_EXAMPLE_PCT

    # Calcular el límite máximo duro para query_examples
    max_query_examples = int(top * max_query_example_pct)

    def _do_search(filter_clause: str, search_top: int) -> list:
        """Función auxiliar para ejecutar una consulta específica en su propio hilo."""
        if search_top <= 0:
            return []
            
        search_options = {
            "search_text": question,
            "top": search_top,
            "select": select_fields,
            "filter": filter_clause,
        }

        if question_embedding:
            search_options["vector_queries"] = [
                VectorizedQuery(
                    vector=question_embedding,
                    k_nearest_neighbors=search_top,
                    fields="content_vector",
                )
            ]

        try:
            # Consumimos el iterador a una lista dentro del hilo
            return list(client.search(**search_options))
        except Exception as e:
            print(f"Error en AI Search con filtro '{filter_clause}': {e}")
            return []

    # Lanzar ambas consultas en paralelo usando ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Hilo 1: Solo recupera query_examples limitados estrictamente al máximo permitido
        future_examples = executor.submit(_do_search, "doc_type eq 'query_example'", max_query_examples)
        
        # Hilo 2: Recupera el resto de documentos (todo lo que NO sea query_example).
        # Pedimos el 'top' total por si el Hilo 1 no encuentra suficientes query_examples
        # y así garantizamos que podemos rellenar el hueco.
        future_others = executor.submit(_do_search, "doc_type ne 'query_example'", top)

        # Esperar y recolectar los resultados crudos
        raw_examples = future_examples.result()
        raw_others = future_others.result()

    # Calcular cuántos documentos del segundo grupo necesitamos para llegar al 'top'
    needed_others = top - len(raw_examples)
    
    # Combinar los resultados truncando los documentos secundarios al número necesario
    combined_raw_results = raw_examples + raw_others[:needed_others]

    # Normalizar los resultados y aplicar formateos de salida
    docs = []
    for r in combined_raw_results:
        docs.append({
            "id": r.get("id"),
            "doc_type": r.get("doc_type"),
            "title": r.get("title"),
            "content": r.get("content"),
            "table_name": r.get("table_name"),
            "column_name": r.get("column_name"),
            "source_system": r.get("source_system"),
            "sql_dialect": r.get("sql_dialect"),
            "tags": _normalize_value(r.get("tags")),
            "related_tables": _normalize_value(r.get("related_tables")),
            "related_columns": _normalize_value(r.get("related_columns")),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "score": _format_doc_search_score(r.get("@search.score")),
        })

    # Como hemos combinado dos listas de búsquedas distintas, el orden global se pierde.
    # Reordenamos la lista combinada por su score de búsqueda de mayor a menor.
    docs.sort(key=lambda x: x.get("score") or 0.0, reverse=True)

    return docs
