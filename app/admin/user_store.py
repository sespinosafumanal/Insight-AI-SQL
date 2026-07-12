import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

from app.config import settings


# Base de datos SQLite dedicada para la administración.
_DB_PATH = Path(settings.ADMIN_STORE_PATH)


def _get_connection() -> sqlite3.Connection:
    """
    Abre la conexion SQLite y crea el directorio si no existe.

    Returns:
        sqlite3.Connection: Conexión activa a SQLite.
    """
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    """
    Crea la tabla de usuarios admin si no existe.

    Args:
        conn (sqlite3.Connection): Conexión activa a SQLite.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id          TEXT PRIMARY KEY,
            username    TEXT NOT NULL UNIQUE,
            password    TEXT NOT NULL,
            created_at  TEXT NOT NULL
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Validacion de contraseña
# ---------------------------------------------------------------------------

def validate_password(password: str) -> tuple[bool, str]:
    """
    Valida que la contraseña cumpla los requisitos minimos.

    Requisitos:
    - Al menos 6 caracteres.
    - Al menos una letra.
    - Al menos un numero.

    Args:
        password (str): La contraseña a validar.

    Returns:
        tuple[bool, str]: Un booleano de éxito y un mensaje explicativo.
    """
    if len(password) < 6:
        return False, "La contraseña debe tener al menos 6 caracteres."

    if not re.search(r"[a-zA-Z]", password):
        return False, "La contraseña debe contener al menos una letra."

    if not re.search(r"[0-9]", password):
        return False, "La contraseña debe contener al menos un número."

    return True, "Contraseña válida."


# ---------------------------------------------------------------------------
# Operaciones de usuario
# ---------------------------------------------------------------------------

def user_exists(username: str) -> bool:
    """
    Comprueba si un nombre de usuario ya esta registrado.

    Args:
        username (str): El nombre de usuario a buscar.

    Returns:
        bool: True si existe, False en caso contrario.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT 1 FROM admin_users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def create_user(username: str, password: str) -> str:
    """
    Crea un nuevo usuario admin.

    Args:
        username (str): El nombre de usuario.
        password (str): La contraseña en texto plano.

    Returns:
        str: El ID único del usuario creado.

    Raises:
        ValueError: Si el nombre ya existe o la contraseña no cumple los requisitos.
    """
    username_clean = username.strip().lower()

    if not username_clean:
        raise ValueError("El nombre de usuario no puede estar vacío.")

    if len(username_clean) < 3:
        raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")

    if user_exists(username_clean):
        raise ValueError("El nombre de usuario ya está registrado.")

    valid, reason = validate_password(password)
    if not valid:
        raise ValueError(reason)

    # Hash de la contraseña con bcrypt.
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    conn = _get_connection()
    try:
        _ensure_table(conn)
        conn.execute(
            """
            INSERT INTO admin_users (id, username, password, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, username_clean, hashed.decode("utf-8"), now),
        )
        conn.commit()
    finally:
        conn.close()

    return user_id


def verify_user(username: str, password: str) -> bool:
    """
    Verifica las credenciales de un usuario admin.

    Args:
        username (str): El nombre de usuario.
        password (str): La contraseña proporcionada.

    Returns:
        bool: True si la contraseña es correcta, False si es incorrecta o no existe el usuario.
    """
    username_clean = username.strip().lower()

    conn = _get_connection()
    try:
        _ensure_table(conn)
        row = conn.execute(
            "SELECT password FROM admin_users WHERE username = ?",
            (username_clean,),
        ).fetchone()

        if not row:
            return False

        stored_hash = row["password"].encode("utf-8")
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash)
    finally:
        conn.close()


def init_db() -> None:
    """
    Inicializa la base de datos de administración y crea el usuario admin por defecto si no existe ninguno.
    """
    conn = _get_connection()
    try:
        _ensure_table(conn)
        row = conn.execute("SELECT COUNT(*) as count FROM admin_users").fetchone()
        count = row["count"] if row else 0
    finally:
        conn.close()

    if count == 0:
        try:
            create_user("admin", "admin12345")
            print("  [INIT] Usuario 'admin' por defecto creado en admin_store.db.")
        except Exception as e:
            print(f"  [ERROR] No se pudo crear el usuario por defecto: {e}")
