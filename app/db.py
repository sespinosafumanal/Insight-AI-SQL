import psycopg2
from app.config import settings
from app.security import enforce_limit

def get_connection():
    """
    Crea una conexión a PostgreSQL usando la configuración del entorno.

    Returns:
        psycopg2.extensions.connection: Conexión activa a la base de datos.
    """
    return psycopg2.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        dbname=settings.POSTGRES_DB,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        connect_timeout=10,
    )

def run_select(sql: str) -> dict:
    """
    Ejecuta una consulta SELECT, aplicando límite y devolviendo un payload estructurado.

    Args:
        sql (str): Consulta SQL a ejecutar.

    Returns:
        dict: Estructura que contiene las columnas recuperadas y sus filas de datos.
    """
    # Garantiza un limite de filas para evitar consultas demasiado grandes.
    sql = enforce_limit(sql, settings.SQL_MAX_ROWS)

    # Muestra la consulta si el modo debug esta activo.
    if settings.SQL_DEBUG_CONTEXT:
        print("\n[SQL_DEBUG_CONTEXT] SQL ejecutada:\n" + sql + "\n", flush=True)

    # Ejecuta la consulta y construye un resultado con metadatos y filas.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 30000;")
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()

    return {
        "columns": columns,
        "rows": [list(row) for row in rows],
        "row_format": "array",
        "row_count": len(rows),
    }
