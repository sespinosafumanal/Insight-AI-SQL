import hashlib
import hmac
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.query_store import (
    list_candidates,
    get_candidate,
    approve_candidate,
    reject_candidate,
    get_query_stats,
    get_query_stats_by_day,
    get_context_docs_stats,
)
from app.indexer import index_approved_query
from app.security import validate_readonly_sql
from app.db import run_select, get_connection
from app.admin.user_store import create_user, verify_user, validate_password


# Configuracion de rutas y plantillas.
_BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(_BASE_DIR / "templates"))

router = APIRouter(prefix="/admin", tags=["admin"])

# Nombre de la cookie de sesion.
_SESSION_COOKIE = "mcp_admin_session"
# Duracion de la sesion en segundos (8 horas).
_SESSION_MAX_AGE = 8 * 60 * 60


# ---------------------------------------------------------------------------
# Sesion basada en cookie firmada con HMAC
# ---------------------------------------------------------------------------

def _sign_session(username: str) -> str:
    """
    Genera un token de sesion firmado: username|timestamp|signature.

    Args:
        username (str): Nombre del usuario.

    Returns:
        str: Token de sesión firmado.
    """
    ts = str(int(time.time()))
    payload = f"{username}|{ts}"
    sig = hmac.new(
        settings.ADMIN_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}|{sig}"


def _verify_session(token: str) -> str | None:
    """
    Verifica un token de sesion y devuelve el username si es valido.

    Args:
        token (str): Token de sesión firmado a validar.

    Returns:
        str | None: El nombre de usuario si es válido y no ha expirado, None en caso contrario.
    """
    parts = token.split("|")
    if len(parts) != 3:
        return None

    username, ts_str, sig = parts

    # Verificar firma.
    expected_payload = f"{username}|{ts_str}"
    expected_sig = hmac.new(
        settings.ADMIN_SECRET_KEY.encode("utf-8"),
        expected_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        return None

    # Verificar expiracion.
    try:
        ts = int(ts_str)
    except ValueError:
        return None

    if time.time() - ts > _SESSION_MAX_AGE:
        return None

    return username


class _RequiresLogin(Exception):
    """Excepcion interna para redirigir a login cuando no hay sesion valida."""
    pass


def _get_current_user(request: Request) -> str:
    """
    Extrae el usuario de la cookie de sesion.

    Si no hay sesion valida, lanza _RequiresLogin que se captura con un
    exception handler registrado en la app para redirigir a /admin/login.

    Args:
        request (Request): Petición actual HTTP de FastAPI.

    Returns:
        str: Nombre del usuario en la sesión activa.

    Raises:
        _RequiresLogin: Si no hay una sesión válida.
    """
    token = request.cookies.get(_SESSION_COOKIE)
    if not token:
        raise _RequiresLogin()

    username = _verify_session(token)
    if not username:
        raise _RequiresLogin()

    return username


# ---------------------------------------------------------------------------
# Rutas de autenticacion (login, register, logout)
# ---------------------------------------------------------------------------

@router.get("/login", response_class=HTMLResponse)
def admin_login_page(request: Request):
    """
    Muestra el formulario de inicio de sesion.

    Args:
        request (Request): Petición actual HTTP.

    Returns:
        HTMLResponse | RedirectResponse: Render del login o redirección si ya está autenticado.
    """
    # Si ya tiene sesion valida, redirigir al dashboard.
    token = request.cookies.get(_SESSION_COOKIE)
    if token and _verify_session(token):
        return RedirectResponse(url="/admin/", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Iniciar sesión",
            "error": None,
            "success": request.query_params.get("registered"),
        },
    )


@router.post("/login", response_class=HTMLResponse)
def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """
    Procesa el inicio de sesion.

    Args:
        request (Request): Petición actual HTTP.
        username (str): Usuario introducido en el formulario.
        password (str): Contraseña introducida en el formulario.

    Returns:
        HTMLResponse | RedirectResponse: Redirección con cookie si hay éxito, o vuelta al login con error.
    """
    if verify_user(username, password):
        token = _sign_session(username.strip().lower())
        response = RedirectResponse(url="/admin/", status_code=303)
        response.set_cookie(
            key=_SESSION_COOKIE,
            value=token,
            max_age=_SESSION_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
        return response

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "title": "Iniciar sesión",
            "error": "Usuario o contraseña incorrectos.",
            "success": None,
        },
    )

@router.get("/logout")
def admin_logout():
    """
    Cierra la sesion del usuario.

    Returns:
        RedirectResponse: Redirige a la pantalla de login borrando la cookie.
    """
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(_SESSION_COOKIE)
    return response


# ---------------------------------------------------------------------------
# Rutas protegidas del panel de administracion
# ---------------------------------------------------------------------------

@router.get("/api/chart_data", response_class=JSONResponse)
def admin_chart_data(days: int = 7, _user: str = Depends(_get_current_user)):
    """
    Devuelve los datos para renderizar la gráfica temporal de ejecución de consultas.

    Args:
        days (int): Número de días hacia atrás a consultar (ej: 7, 15, 30...).
        _user (str): Usuario autenticado (usado para verificar sesión).

    Returns:
        JSONResponse: Lista de objetos con 'date', 'successful' y 'failed'.
    """
    valid_days = [7, 15, 30, 90, 360]
    if days not in valid_days:
        days = 7
        
    data = get_query_stats_by_day(days)
    return JSONResponse(content={"data": data})


@router.get("/", response_class=HTMLResponse)
def admin_dashboard(request: Request, user: str = Depends(_get_current_user)):
    """
    Panel principal: lista de consultas pendientes de revision.

    Args:
        request (Request): Petición actual HTTP.
        user (str): Usuario autenticado.

    Returns:
        TemplateResponse: Página renderizada del dashboard con los candidatos.
    """
    candidates = list_candidates(status="pending", limit=100)
    query_stats = get_query_stats()
    return templates.TemplateResponse(
        request=request,
        name="candidates.html",
        context={
            "candidates": candidates,
            "query_stats": query_stats,
            "current_tab": "pending",
            "title": "Consultas SQL — Pendientes",
            "current_user": user,
        },
    )


@router.get("/history", response_class=HTMLResponse)
def admin_history(
    request: Request,
    status: str = "approved",
    user: str = Depends(_get_current_user),
):
    """
    Historial de consultas aprobadas o rechazadas.

    Args:
        request (Request): Petición actual HTTP.
        status (str, optional): Estado de filtro. Por defecto 'approved'.
        user (str): Usuario autenticado.

    Returns:
        TemplateResponse: Página renderizada del historial con el filtro correspondiente.
    """
    if status not in ("approved", "rejected"):
        status = "approved"
    candidates = list_candidates(status=status, limit=100)
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "candidates": candidates,
            "current_tab": status,
            "filter_status": status,
            "title": f"Consultas SQL — {'Aprobadas' if status == 'approved' else 'Rechazadas'}",
            "current_user": user,
        },
    )


@router.get("/candidate/{candidate_id}", response_class=HTMLResponse)
def admin_candidate_detail(
    request: Request,
    candidate_id: str,
    user: str = Depends(_get_current_user),
):
    """
    Detalle de una consulta candidata individual.

    Args:
        request (Request): Petición actual HTTP.
        candidate_id (str): Identificador del candidato a visualizar.
        user (str): Usuario autenticado.

    Returns:
        TemplateResponse: Página renderizada con el detalle y metadatos del candidato.
    """
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")
    return templates.TemplateResponse(
        request=request,
        name="candidate_detail.html",
        context={
            "candidate": candidate,
            "title": "Detalle de consulta",
            "current_tab": "pending",
            "current_user": user,
        },
    )


@router.post("/candidate/{candidate_id}/run", response_class=JSONResponse)
def admin_run_sql(
    candidate_id: str,
    sql: str = Form(...),
    _user: str = Depends(_get_current_user),
):
    """
    Consola interactiva: valida y ejecuta una consulta SQL editada por el revisor.
    Devuelve columnas, filas y conteo en JSON para renderizado dinámico en el frontend.
    """
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")

    # Validacion de seguridad: solo se permiten consultas de solo lectura.
    valid, reason = validate_readonly_sql(sql)
    if not valid:
        return JSONResponse(
            status_code=400,
            content={"error": f"SQL no válido: {reason}"},
        )

    try:
        result = run_select(sql)
        return JSONResponse(content=result)
    except Exception as exc:
        error_msg = str(exc)
        # Trunca el mensaje para evitar exponer detalles internos excesivos.
        return JSONResponse(
            status_code=500,
            content={"error": error_msg[:400]},
        )


@router.get("/schema", response_class=JSONResponse)
def admin_schema(_user: str = Depends(_get_current_user)):
    """
    Explorador de esquema: devuelve las tablas y columnas del esquema público
    de la base de datos PostgreSQL configurada.

    Args:
        _user (str): Usuario autenticado (ignorado en lógica interna).

    Returns:
        JSONResponse: Un JSON conteniendo la estructura del esquema de la base de datos.
    """
    query = """
        SELECT
            t.table_name,
            c.column_name,
            c.data_type,
            c.is_nullable,
            c.column_default
        FROM information_schema.tables t
        JOIN information_schema.columns c
            ON t.table_name = c.table_name
           AND t.table_schema = c.table_schema
        WHERE t.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name, c.ordinal_position;
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query)
                rows = cur.fetchall()

        # Agrupa columnas por tabla para devolver un árbol de esquema.
        schema: dict = {}
        for table_name, col_name, data_type, nullable, default in rows:
            if table_name not in schema:
                schema[table_name] = []
            schema[table_name].append({
                "column": col_name,
                "type": data_type,
                "nullable": nullable == "YES",
                "default": default,
            })

        return JSONResponse(content={"tables": schema})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)[:400]},
        )


@router.post("/candidate/{candidate_id}/approve")
def admin_approve(
    candidate_id: str,
    reviewer_notes: str = Form(default=""),
    modified_sql: str = Form(default=""),
    _user: str = Depends(_get_current_user),
):
    """
    Aprueba una consulta e indexa en Azure AI Search.
    Si se proporciona modified_sql, valida y usa ese SQL en lugar del original.

    Args:
        candidate_id (str): ID del candidato a aprobar.
        reviewer_notes (str, optional): Comentarios del revisor (por defecto "").
        modified_sql (str, optional): SQL modificado opcional (por defecto "").
        _user (str): Usuario autenticado.

    Returns:
        RedirectResponse: Redirige al dashboard principal después de completar con éxito.
    """
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")

    if candidate["status"] != "pending":
        raise HTTPException(status_code=400, detail="Solo se pueden aprobar consultas pendientes")

    # Si el revisor modificó el SQL, validar y usar el nuevo.
    sql_to_index = modified_sql.strip() if modified_sql.strip() else None
    if sql_to_index:
        valid, reason = validate_readonly_sql(sql_to_index)
        if not valid:
            raise HTTPException(
                status_code=400,
                detail=f"El SQL modificado no es válido: {reason}",
            )
        # Sustituye el SQL en el candidato antes de indexar.
        candidate = dict(candidate)
        candidate["sql"] = sql_to_index

    # Indexar en Azure AI Search.
    index_result = index_approved_query(candidate)

    if index_result["status"] == "error":
        raise HTTPException(
            status_code=500,
            detail=f"Error al indexar: {index_result['error']}",
        )

    # Marcar como aprobada en el store local.
    notes = reviewer_notes.strip() if reviewer_notes else None
    if index_result.get("document_id"):
        doc_note = f"Indexada como: {index_result['document_id']}"
        notes = f"{notes}\n{doc_note}" if notes else doc_note

    approve_candidate(candidate_id, reviewer_notes=notes)

    return RedirectResponse(url="/admin/", status_code=303)


@router.post("/candidate/{candidate_id}/reject")
def admin_reject(
    candidate_id: str,
    reviewer_notes: str = Form(default=""),
    _user: str = Depends(_get_current_user),
):
    """
    Rechaza una consulta candidata.

    Args:
        candidate_id (str): ID del candidato a rechazar.
        reviewer_notes (str, optional): Comentarios del revisor (por defecto "").
        _user (str): Usuario autenticado.

    Returns:
        RedirectResponse: Redirige al dashboard principal después del rechazo.
    """
    candidate = get_candidate(candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Consulta no encontrada")

    if candidate["status"] != "pending":
        raise HTTPException(status_code=400, detail="Solo se pueden rechazar consultas pendientes")

    notes = reviewer_notes.strip() if reviewer_notes else None
    reject_candidate(candidate_id, reviewer_notes=notes)

    return RedirectResponse(url="/admin/", status_code=303)


@router.get("/analytics", response_class=HTMLResponse)
def admin_analytics(request: Request, user: str = Depends(_get_current_user)):
    """
    Página de analíticas con Treemap interactivo de documentos de contexto.
    """
    return templates.TemplateResponse(
        request=request,
        name="analytics.html",
        context={
            "title": "Analíticas",
            "current_tab": "analytics",
            "current_user": user,
        },
    )


@router.get("/api/analytics/context_docs", response_class=JSONResponse)
def api_context_docs_stats(days: int = 30, _user: str = Depends(_get_current_user)):
    """
    API JSON para obtener las estadísticas de documentos de contexto de los últimos N días.
    """
    data = get_context_docs_stats(days=days)
    return JSONResponse(content={"data": data})
