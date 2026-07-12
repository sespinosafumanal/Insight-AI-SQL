import sqlparse
from sqlparse.tokens import Keyword, DML, DDL

# Palabras clave no permitidas para garantizar consultas de solo lectura.
# Al usar sqlparse no bloquearemos falsos positivos en nombres de columnas o literales.
FORBIDDEN_KEYWORDS = {
    "GRANT", "REVOKE", "CALL", "DO", "EXECUTE", "COPY",
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"
}

def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Valida que el SQL sea una única consulta de lectura segura,
    utilizando análisis de tokens (AST) para evitar falsos positivos
    en cadenas de texto o nombres de columnas.

    Args:
        sql (str): Consulta SQL a validar.

    Returns:
        tuple[bool, str]: Un booleano indicando si es segura y un mensaje explicativo.
    """
    if not sql or not sql.strip():
        return False, "SQL vacío."

    sql_clean = sql.strip()

    statements = sqlparse.split(sql_clean)
    if len(statements) != 1:
        return False, "No se permiten múltiples sentencias SQL."

    parsed = sqlparse.parse(sql_clean)
    if not parsed:
        return False, "No se pudo parsear el SQL."

    stmt = parsed[0]

    first_token = stmt.token_first(skip_cm=True)
    if not first_token:
        return False, "SQL sin tokens válidos."

    first = first_token.value.lower()
    if first not in {"select", "with"}:
        return False, "Solo se permiten consultas SELECT o WITH."

    # Validar todos los tokens analizados para detectar DML o DDL oculto
    for token in stmt.flatten():
        # Rechaza operaciones de modificación y definición explícitas
        if token.ttype in DML or token.ttype in DDL:
            if token.value.upper() not in ('SELECT', 'WITH'):
                return False, f"Operación prohibida detectada: {token.value}"
        
        # Rechaza palabras reservadas peligrosas
        if token.ttype is Keyword:
            if token.value.upper() in FORBIDDEN_KEYWORDS:
                return False, f"Palabra clave prohibida detectada: {token.value}"

    return True, "Consulta SQL de solo lectura válida."


def enforce_limit(sql: str, max_rows: int = 100) -> str:
    """
    Envuelve la consulta SQL en una subconsulta para forzar un límite máximo
    de filas devueltas, previniendo riesgos de saturación de memoria (OOM).

    Args:
        sql (str): Consulta SQL original.
        max_rows (int, optional): Número máximo de filas a devolver. Por defecto 100.

    Returns:
        str: Consulta SQL modificada con el límite de filas asegurado a nivel de base de datos.
    """
    # Se elimina el punto y coma final para evitar errores de sintaxis en la subconsulta
    sql_clean = sql.strip().rstrip(";")
    
    # Envolver la consulta garantiza que el límite se aplique sin importar 
    # la presencia previa de la cláusula LIMIT o estructuras complejas (ej: WITH).
    return f"SELECT * FROM ({sql_clean}) AS _mcp_limit_wrapper LIMIT {max_rows};"
