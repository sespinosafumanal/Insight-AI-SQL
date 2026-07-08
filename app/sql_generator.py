from openai import AzureOpenAI, NotFoundError
from app.config import settings
from app.rag_search import format_context_docs_for_prompt

def get_openai_client():
    """
    Crea un cliente Azure OpenAI con la configuracion del entorno.

    Returns:
        AzureOpenAI: Cliente de OpenAI configurado.
    """
    return AzureOpenAI(
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_key=settings.AZURE_OPENAI_API_KEY,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )

def build_sql_prompt(question: str, context_docs: list[dict]) -> str:
    """
    Construye el prompt con reglas de seguridad y contexto RAG.

    Args:
        question (str): Pregunta del usuario.
        context_docs (list[dict]): Documentos de contexto recuperados.

    Returns:
        str: Prompt formateado para el LLM.
    """
    context_text = format_context_docs_for_prompt(context_docs)

    return f"""
Eres un experto en PostgreSQL.

Tu tarea es generar una consulta SQL de solo lectura para responder a la pregunta del usuario.

Reglas obligatorias:
- Devuelve únicamente SQL, sin explicación.
- Usa solo tablas, columnas y relaciones presentes en el contexto.
- No inventes columnas.
- No uses INSERT, UPDATE, DELETE, DROP, ALTER, CREATE ni TRUNCATE.
- Usa PostgreSQL.
- Prioriza los documentos con mayor score y usa los campos `table_name`, `column_name`, `related_tables`, `related_columns` y `sql_dialect` cuando existan.
- Si necesitas saber si una transacción es fraudulenta, dedúcelo exclusivamente del contexto RAG.
	- Añade LIMIT {settings.SQL_MAX_ROWS} si la consulta puede devolver muchas filas.

Contexto recuperado desde Azure AI Search:
{context_text}

Pregunta del usuario:
{question}

SQL:
""".strip()

def generate_sql_from_context(question: str, context_docs: list[dict]) -> str:
    """
    Llama al modelo para generar SQL y limpia el resultado.

    Args:
        question (str): Pregunta del usuario.
        context_docs (list[dict]): Documentos de contexto recuperados.

    Returns:
        str: Consulta SQL generada y limpia.
    """
    client = get_openai_client()
    prompt = build_sql_prompt(question, context_docs)

    try:
        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un generador estricto de SQL PostgreSQL de solo lectura."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
        )
    except NotFoundError as exc:
        # Mensaje claro cuando el deployment no existe en el endpoint.
        raise RuntimeError(
            "Foundry no encuentra el deployment '"
            f"{settings.AZURE_OPENAI_CHAT_DEPLOYMENT}' en el endpoint '{settings.AZURE_OPENAI_ENDPOINT}'. "
            "Comprueba el nombre exacto del deployment en Azure Foundry."
        ) from exc

    sql = response.choices[0].message.content.strip()

    # Elimina cercas de codigo si el modelo las incluyo.
    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql

def build_reconstruct_sql_prompt(question: str, context_docs: list[dict], failed_sql: str, error_message: str) -> str:
    """
    Construye el prompt para reconstruir una consulta fallida.

    Args:
        question (str): Pregunta original del usuario.
        context_docs (list[dict]): Documentos de contexto recuperados.
        failed_sql (str): Consulta SQL que falló.
        error_message (str): Mensaje de error de la base de datos.

    Returns:
        str: Prompt formateado para reconstruir la consulta.
    """
    context_text = format_context_docs_for_prompt(context_docs)

    return f"""
Eres un experto en PostgreSQL.
Recientemente generaste una consulta SQL que falló al ejecutarse debido a un error de base de datos.

Pregunta original del usuario:
{question}

Consulta SQL fallida:
{failed_sql}

Mensaje de error de PostgreSQL:
{error_message}

Tu tarea es analizar el error de PostgreSQL y reconstruir una consulta SQL corregida y válida utilizando el contexto RAG proporcionado a continuación.

Reglas obligatorias:
- Devuelve únicamente la consulta SQL corregida, sin explicaciones ni cercas de código.
- Usa solo tablas, columnas y relaciones presentes en el contexto.
- No inventes columnas.
- No uses INSERT, UPDATE, DELETE, DROP, ALTER, CREATE ni TRUNCATE.
- Usa PostgreSQL.
- Prioriza los documentos con mayor score y usa los campos `table_name`, `column_name`, `related_tables`, `related_columns` y `sql_dialect` cuando existan.
- Añade LIMIT {settings.SQL_MAX_ROWS} si la consulta puede devolver muchas filas.

Contexto recuperado desde Azure AI Search:
{context_text}

SQL corregido:
""".strip()

def reconstruct_sql_on_error(question: str, context_docs: list[dict], failed_sql: str, error_message: str) -> str:
    """
    Llama al modelo para reconstruir SQL tras un error de ejecución.

    Args:
        question (str): Pregunta original del usuario.
        context_docs (list[dict]): Documentos de contexto recuperados.
        failed_sql (str): Consulta SQL que falló.
        error_message (str): Mensaje de error de la base de datos.

    Returns:
        str: Nueva consulta SQL generada y limpia.
    """
    client = get_openai_client()
    prompt = build_reconstruct_sql_prompt(question, context_docs, failed_sql, error_message)

    try:
        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un experto en PostgreSQL encargado de depurar y corregir consultas SQL erróneas basándote en el esquema y en el error devuelto."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
        )
    except NotFoundError as exc:
        raise RuntimeError(
            "Foundry no encuentra el deployment '"
            f"{settings.AZURE_OPENAI_CHAT_DEPLOYMENT}' en el endpoint '{settings.AZURE_OPENAI_ENDPOINT}'. "
            "Comprueba el nombre exacto del deployment en Azure Foundry."
        ) from exc

    sql = response.choices[0].message.content.strip()

    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "").strip()

    return sql
