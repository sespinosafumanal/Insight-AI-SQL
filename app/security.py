import re
import sqlparse

# Palabras clave no permitidas para garantizar consultas de solo lectura.
FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "grant", "revoke", "copy", "call", "do", "execute"
}

def validate_readonly_sql(sql: str) -> tuple[bool, str]:
    """
    Valida que el SQL sea una única consulta de lectura segura.

    Args:
        sql (str): Consulta SQL a validar.

    Returns:
        tuple[bool, str]: Un booleano indicando si es segura y un mensaje explicativo.
    """
    # Rechaza entradas vacias.
    if not sql or not sql.strip():
        return False, "SQL vacío."

    # Normaliza y verifica que exista una sola sentencia.
    sql_clean = sql.strip()

    statements = sqlparse.split(sql_clean)
    if len(statements) != 1:
        return False, "No se permiten múltiples sentencias SQL."

    # Verifica que la consulta pueda parsearse.
    parsed = sqlparse.parse(sql_clean)
    if not parsed:
        return False, "No se pudo parsear el SQL."

    first_token = parsed[0].token_first(skip_cm=True)
    if not first_token:
        return False, "SQL sin tokens válidos."

    first = first_token.value.lower()

    # Solo se permiten consultas SELECT o WITH.
    if first not in {"select", "with"}:
        return False, "Solo se permiten consultas SELECT o WITH."

    # Bloquea cualquier palabra clave potencialmente peligrosa.
    lowered = sql_clean.lower()
    for keyword in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{keyword}\b", lowered):
            return False, f"Palabra clave prohibida detectada: {keyword}"

    return True, "Consulta SQL de solo lectura válida."


def enforce_limit(sql: str, max_rows: int = 100) -> str:
    """
    Añade la cláusula LIMIT si la consulta no la incluye.

    Args:
        sql (str): Consulta SQL original.
        max_rows (int, optional): Número máximo de filas a devolver. Por defecto 100.

    Returns:
        str: Consulta SQL modificada con el límite de filas asegurado.
    """
    lowered = sql.lower()

    # Respeta el LIMIT existente.
    if re.search(r"\blimit\b", lowered):
        return sql

    return sql.rstrip().rstrip(";") + f"\nLIMIT {max_rows};"
