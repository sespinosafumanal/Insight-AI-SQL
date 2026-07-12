import json
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from app.config import settings


# Ruta al fichero SQLite para almacenar consultas candidatas.
_DB_PATH = Path(settings.QUERY_STORE_PATH)


def _get_connection() -> sqlite3.Connection:
    """
    Crea el directorio si no existe y abre la conexion a la base de datos SQLite.

    Returns:
        sqlite3.Connection: Conexión activa a SQLite configurada con row_factory.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    """
    Crea la tabla de candidatas si no existe.

    Args:
        conn (sqlite3.Connection): Conexión activa a SQLite.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_candidates (
            id              TEXT PRIMARY KEY,
            question        TEXT NOT NULL,
            sql             TEXT NOT NULL,
            columns         TEXT,
            row_count       INTEGER,
            sample_rows     TEXT,
            context_doc_ids TEXT,
            status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
            created_at      TEXT NOT NULL,
            reviewed_at     TEXT,
            reviewer_notes  TEXT
        );
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS query_logs (
            id              TEXT PRIMARY KEY,
            success         INTEGER NOT NULL,
            created_at      TEXT NOT NULL
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_query_candidates_status_date ON query_candidates (status, created_at DESC);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_query_logs_date ON query_logs (created_at DESC);")
    conn.commit()


def save_candidate(
    question: str,
    sql: str,
    columns: list[str] | None = None,
    row_count: int | None = None,
    sample_rows: list | None = None,
    context_doc_ids: list[str] | None = None,
) -> str:
    """
    Guarda una consulta exitosa como candidata pendiente de revision.

    Args:
        question (str): Pregunta original del usuario.
        sql (str): Consulta SQL generada.
        columns (list[str] | None, optional): Columnas devueltas. Por defecto None.
        row_count (int | None, optional): Número de filas. Por defecto None.
        sample_rows (list | None, optional): Muestra de las filas. Por defecto None.
        context_doc_ids (list[str] | None, optional): IDs de documentos RAG usados. Por defecto None.

    Returns:
        str: ID único de la consulta candidata guardada.
    """
    candidate_id = str(uuid.uuid4())
    now = datetime.now(ZoneInfo("Europe/Madrid")).isoformat()

    conn = _get_connection()
    try:
        _ensure_table(conn)
        conn.execute(
            """
            INSERT INTO query_candidates
                (id, question, sql, columns, row_count, sample_rows, context_doc_ids, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                candidate_id,
                question,
                sql,
                json.dumps(columns) if columns else None,
                row_count,
                json.dumps(sample_rows, default=str) if sample_rows else None,
                json.dumps(context_doc_ids) if context_doc_ids else None,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return candidate_id


def log_query_execution(success: bool) -> None:
    """
    Registra la ejecución de una consulta (exitosa o fallida) para estadísticas.

    Args:
        success (bool): True si la consulta tuvo éxito, False si falló.
    """
    log_id = str(uuid.uuid4())
    now = datetime.now(ZoneInfo("Europe/Madrid")).isoformat()
    success_int = 1 if success else 0

    conn = _get_connection()
    try:
        _ensure_table(conn)
        conn.execute(
            "INSERT INTO query_logs (id, success, created_at) VALUES (?, ?, ?)",
            (log_id, success_int, now),
        )
        conn.commit()
    finally:
        conn.close()


def get_query_stats() -> dict:
    """
    Obtiene las estadísticas de ejecución de consultas.

    Returns:
        dict: Diccionario con total, éxitos, fallos y tasa de éxito.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
        row = conn.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
            FROM query_logs
            """
        ).fetchone()
        
        total = row["total"] or 0
        successful = row["successful"] or 0
        failed = row["failed"] or 0
        success_rate = (successful / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(success_rate, 1)
        }
    finally:
        conn.close()


def get_query_stats_by_day(days: int = 7) -> list[dict]:
    """
    Obtiene las estadísticas de ejecución de consultas agrupadas por día para los últimos N días.

    Args:
        days (int, optional): Número de días a recuperar. Por defecto 7.

    Returns:
        list[dict]: Lista de diccionarios con 'date', 'successful' y 'failed'.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
        # Se obtienen los datos de la base de datos
        rows = conn.execute(
            """
            SELECT
                date(created_at) as log_date,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
            FROM query_logs
            WHERE created_at >= date('now', ?)
            GROUP BY log_date
            ORDER BY log_date ASC
            """,
            (f"-{days} days",)
        ).fetchall()
        
        db_data = {row["log_date"]: {"successful": row["successful"], "failed": row["failed"]} for row in rows}
        
        # Se genera la secuencia de fechas para evitar saltos en la gráfica
        result = []
        base = datetime.now(ZoneInfo("Europe/Madrid")).date()
        for i in range(days - 1, -1, -1):
            d = base - timedelta(days=i)
            d_str = d.isoformat()
            stats = db_data.get(d_str, {"successful": 0, "failed": 0})
            result.append({
                "date": d_str,
                "successful": stats["successful"],
                "failed": stats["failed"]
            })
            
        return result
    finally:
        conn.close()


def list_candidates(status: str = "pending", limit: int = 50) -> list[dict]:
    """
    Lista consultas candidatas filtradas por estado.

    Args:
        status (str, optional): Estado de las consultas a buscar ('pending', 'approved', 'rejected'). Por defecto "pending".
        limit (int, optional): Número máximo de resultados. Por defecto 50.

    Returns:
        list[dict]: Lista de consultas candidatas encontradas.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
        rows = conn.execute(
            "SELECT * FROM query_candidates WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_candidate(candidate_id: str) -> dict | None:
    """
    Obtiene el detalle de una consulta candidata por su ID.

    Args:
        candidate_id (str): Identificador único de la candidata.

    Returns:
        dict | None: Detalles de la consulta o None si no se encuentra.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT * FROM query_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def approve_candidate(candidate_id: str, reviewer_notes: str | None = None) -> bool:
    """
    Marca una consulta como aprobada.

    Args:
        candidate_id (str): ID de la consulta a aprobar.
        reviewer_notes (str | None, optional): Notas del revisor. Por defecto None.

    Returns:
        bool: True si se actualizó correctamente, False en caso contrario.
    """
    return _update_status(candidate_id, "approved", reviewer_notes)


def reject_candidate(candidate_id: str, reviewer_notes: str | None = None) -> bool:
    """
    Marca una consulta como rechazada.

    Args:
        candidate_id (str): ID de la consulta a rechazar.
        reviewer_notes (str | None, optional): Notas del revisor. Por defecto None.

    Returns:
        bool: True si se actualizó correctamente, False en caso contrario.
    """
    return _update_status(candidate_id, "rejected", reviewer_notes)


def _update_status(candidate_id: str, new_status: str, reviewer_notes: str | None) -> bool:
    """
    Actualiza el estado de una consulta candidata.

    Args:
        candidate_id (str): ID de la consulta.
        new_status (str): Nuevo estado ('approved', 'rejected', etc.).
        reviewer_notes (str | None): Notas opcionales del revisor.

    Returns:
        bool: True si la actualización afectó al menos a una fila, False en caso contrario.
    """
    now = datetime.now(ZoneInfo("Europe/Madrid")).isoformat()
    conn = _get_connection()
    try:
        _ensure_table(conn)
        cursor = conn.execute(
            """
            UPDATE query_candidates
            SET status = ?, reviewed_at = ?, reviewer_notes = ?
            WHERE id = ? AND status = 'pending'
            """,
            (new_status, now, reviewer_notes, candidate_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """
    Convierte una fila SQLite en un dict con campos JSON deserializados.

    Args:
        row (sqlite3.Row): Fila obtenida de la base de datos.

    Returns:
        dict: Diccionario de Python con los campos parseados.
    """
    d = dict(row)
    for field in ("columns", "sample_rows", "context_doc_ids"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def get_context_docs_stats(days: int = 30) -> list[dict]:
    """
    Obtiene las estadísticas de uso de documentos de contexto (RAG) para los últimos N días.

    Args:
        days (int, optional): Número de días a recuperar. Por defecto 30.

    Returns:
        list[dict]: Lista de diccionarios con la frecuencia, tasa de aprobación y ejemplos.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
        rows = conn.execute(
            """
            SELECT question, context_doc_ids, status
            FROM query_candidates
            WHERE created_at >= date('now', ?)
            AND context_doc_ids IS NOT NULL
            """,
            (f"-{days} days",)
        ).fetchall()
        
        docs_stats = {}
        for row in rows:
            question = row["question"]
            status = row["status"]
            try:
                doc_ids = json.loads(row["context_doc_ids"]) if isinstance(row["context_doc_ids"], str) else row["context_doc_ids"]
            except (json.JSONDecodeError, TypeError):
                continue
                
            if not isinstance(doc_ids, list):
                continue
                
            for doc_id in doc_ids:
                if not doc_id:
                    continue
                if doc_id not in docs_stats:
                    docs_stats[doc_id] = {
                        "id": doc_id,
                        "count": 0,
                        "approved": 0,
                        "rejected": 0,
                        "sample_questions": []
                    }
                
                stats = docs_stats[doc_id]
                stats["count"] += 1
                if status == "approved":
                    stats["approved"] += 1
                elif status == "rejected":
                    stats["rejected"] += 1
                
                # Guardar algunas preguntas de ejemplo únicas
                if len(stats["sample_questions"]) < 5 and question not in stats["sample_questions"]:
                    stats["sample_questions"].append(question)
                    
        result = []
        for doc_id, stats in docs_stats.items():
            total_resolved = stats["approved"] + stats["rejected"]
            # Si no hay resueltas, asumimos 100% si al menos se ha usado, o 0% si no ha habido actividad (poco probable)
            approval_rate = (stats["approved"] / total_resolved * 100) if total_resolved > 0 else 100.0
            
            result.append({
                "id": doc_id,
                "count": stats["count"],
                "approval_rate": round(approval_rate, 1),
                "sample_questions": stats["sample_questions"]
            })
            
        # Ordenar por frecuencia descendente
        result.sort(key=lambda x: x["count"], reverse=True)
        return result
    finally:
        conn.close()


def init_db() -> None:
    """
    Inicializa las tablas de la base de datos de consultas.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
    finally:
        conn.close()

