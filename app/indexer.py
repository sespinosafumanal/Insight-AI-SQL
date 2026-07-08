import re
from datetime import datetime, timezone

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from app.config import settings


def _get_search_client() -> SearchClient:
    """
    Crea un cliente de Azure AI Search para subir documentos al indice.

    Returns:
        SearchClient: Cliente de búsqueda configurado.
    """
    return SearchClient(
        endpoint=settings.AZURE_SEARCH_ENDPOINT,
        index_name=settings.AZURE_SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(settings.AZURE_SEARCH_API_KEY),
    )


def _get_openai_client() -> AzureOpenAI:
    """
    Crea un cliente Azure OpenAI para generar embeddings.

    Returns:
        AzureOpenAI: Cliente de OpenAI configurado.
    """
    return AzureOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )


def _get_embedding(client: AzureOpenAI, text: str) -> list[float]:
    """
    Genera el embedding del texto usando el deployment configurado.

    Args:
        client (AzureOpenAI): Cliente de OpenAI.
        text (str): Texto a vectorizar.

    Returns:
        list[float]: Vector resultante.
    """
    response = client.embeddings.create(
        model=settings.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
        input=text,
    )
    return response.data[0].embedding


def _extract_tables_from_sql(sql: str) -> list[str]:
    """
    Extrae nombres de tablas del SQL usando patrones FROM y JOIN.

    Args:
        sql (str): Consulta SQL.

    Returns:
        list[str]: Lista de nombres de tablas únicos extraídos.
    """
    pattern = r"(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    matches = re.findall(pattern, sql, re.IGNORECASE)
    # Eliminar duplicados preservando orden.
    seen = set()
    tables = []
    for table in matches:
        lower = table.lower()
        if lower not in seen:
            seen.add(lower)
            tables.append(table)
    return tables


def _extract_columns_from_sql(sql: str, tables: list[str]) -> list[str]:
    """
    Extrae referencias tabla.columna del SQL.

    Args:
        sql (str): Consulta SQL.
        tables (list[str]): Nombres de las tablas detectadas en la consulta.

    Returns:
        list[str]: Lista de columnas únicas extraídas en formato 'tabla.columna'.
    """
    pattern = r"([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)"
    matches = re.findall(pattern, sql)
    seen = set()
    columns = []
    for table_ref, col in matches:
        ref = f"{table_ref}.{col}"
        if ref.lower() not in seen:
            seen.add(ref.lower())
            columns.append(ref)
    return columns


def index_approved_query(candidate: dict) -> dict:
    """
    Indexa una consulta aprobada en Azure AI Search.

    Sigue la misma estructura que query_examples.jsonl y el patron
    de upload_ai_search_documents.py: genera embedding, construye el
    documento con todos los campos del indice, y lo sube con
    merge_or_upload_documents.

    Args:
        candidate (dict): Diccionario con al menos 'id', 'question' y 'sql'.

    Returns:
        dict: Diccionario con 'status', 'document_id' y posible 'error'.
    """
    question = candidate["question"]
    sql = candidate["sql"]
    candidate_id = candidate["id"]
    now = datetime.now(timezone.utc).isoformat()

    # Construir el content con el mismo formato que query_examples.jsonl.
    content = f"Pregunta del usuario: {question} SQL validada: {sql}"

    # Extraer tablas y columnas del SQL para campos de metadatos.
    tables = _extract_tables_from_sql(sql)
    columns = _extract_columns_from_sql(sql, tables)
    primary_table = tables[0] if tables else None

    # Generar embedding del contenido.
    try:
        openai_client = _get_openai_client()
        content_vector = _get_embedding(openai_client, content)
    except Exception as exc:
        return {
            "status": "error",
            "document_id": None,
            "error": f"Error al generar embedding: {exc}",
        }

    # Construir documento con la misma estructura que query_examples.jsonl.
    document = {
        "id": f"query-example-admin-{candidate_id}",
        "doc_type": "query_example",
        "title": f"Consulta validada: {question[:80]}",
        "content": content,
        "table_name": primary_table,
        "column_name": None,
        "source_system": "postgresql_wsl_fraud_db",
        "sql_dialect": "postgresql",
        "tags": [
            "query_example",
            "admin_approved",
            "executed_successfully",
        ],
        "related_tables": tables,
        "related_columns": columns,
        "created_at": candidate.get("created_at", now),
        "updated_at": now,
        "content_vector": content_vector,
    }

    # Subir al indice usando el mismo metodo que upload_ai_search_documents.py.
    try:
        search_client = _get_search_client()
        results = search_client.merge_or_upload_documents([document])

        for result in results:
            if not result.succeeded:
                return {
                    "status": "error",
                    "document_id": document["id"],
                    "error": f"Error en Azure AI Search: {result.error_message}",
                }

        return {
            "status": "indexed",
            "document_id": document["id"],
            "error": None,
        }

    except Exception as exc:
        return {
            "status": "error",
            "document_id": document["id"],
            "error": f"Error al subir documento: {exc}",
        }
