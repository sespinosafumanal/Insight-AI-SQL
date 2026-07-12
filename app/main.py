from fastmcp import FastMCP
from app.config import settings
from app.mcp_tools import (
    tool_get_context,
    tool_generate_sql,
    tool_ask_database,
    tool_generate_executive_report,
    tool_get_report_blueprint,
)
import time
from functools import wraps

def with_execution_time(func):
    """
    Decorador para medir el tiempo de ejecución de las herramientas MCP.
    Si la herramienta devuelve un diccionario, inyecta 'execution_time_ms'.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        
        execution_time_ms = round((end_time - start_time) * 1000, 2)
        if isinstance(result, dict):
            result["execution_time_ms"] = execution_time_ms
        return result
    return wrapper

# Inicializa el servidor MCP con un nombre de servicio descriptivo.
mcp = FastMCP("Insight AI-SQL MCP Server")

@mcp.tool
@with_execution_time
def get_context(question: str) -> dict:
    """
    Recupera desde Azure AI Search el contexto técnico relevante para una pregunta:
    DDL, documentación de negocio, relaciones, ejemplos SQL y valores categóricos.

    Args:
        question (str): La pregunta del usuario en lenguaje natural.

    Returns:
        dict: Diccionario que contiene el contexto recuperado estructurado o mensajes de error.
    """
    # Envoltorio directo a la herramienta interna de contexto.
    return tool_get_context(question)

@mcp.tool
@with_execution_time
def generate_sql(question: str, debug: bool = settings.SQL_DEBUG_CONTEXT) -> dict:
    """
    Genera una consulta SQL PostgreSQL de solo lectura a partir de una pregunta
    en lenguaje natural y del contexto recuperado desde Azure AI Search.
    No ejecuta la consulta.

    Args:
        question (str): La pregunta analítica del usuario.
        debug (bool): Si es True, incluye en la respuesta detalles adicionales del RAG y el prompt.

    Returns:
        dict: Estructura con la consulta SQL generada o los posibles errores.
    """
    # Envoltorio directo a la herramienta de generacion SQL.
    return tool_generate_sql(question, debug=debug)

@mcp.tool
@with_execution_time
def ask_database(question: str) -> dict:
    """
    Genera SQL de solo lectura, lo valida, lo ejecuta contra PostgreSQL fraud_db
    y devuelve los resultados en formato estructurado.

    Args:
        question (str): La pregunta analítica del usuario a resolver.

    Returns:
        dict: Resultado que incluye el SQL ejecutado, las columnas y filas obtenidas de la base de datos.
    """
    # Envoltorio directo a la herramienta que consulta la base de datos.
    return tool_ask_database(question)


@mcp.tool
@with_execution_time
def generate_executive_report(
    report_title: str,
    user_request: str,
    sections: list[dict],
    audience: str = "dirección",
    period: str | None = None,
    include_sql: bool = True,
    include_tables: bool = True,
    max_rows_per_section: int = settings.REPORT_MAX_ROWS_PER_SECTION
) -> dict:
    """
    Ejecuta las preguntas analíticas necesarias para construir un informe ejecutivo.

    Usa esta herramienta cuando el usuario pida un informe, análisis ejecutivo,
    diagnóstico, resumen con insights o documento, y el agente ya
    haya identificado qué preguntas o secciones deben incluirse en el informe.

    Esta herramienta NO redacta el informe final con IA generativa. Su función es
    obtener evidencias desde la base de datos: genera o ejecuta SQL de solo lectura,
    valida las consultas, recupera resultados y devuelve tablas estructuradas para
    que el agente redacte el informe final.

    El agente debe proporcionar una lista de secciones. Cada sección debe contener:
    - id: identificador corto y estable.
    - title: título de la sección.
    - question: pregunta analítica concreta que debe responderse con datos.

    Usa ask_database para preguntas simples de una sola métrica.
    Usa esta herramienta cuando haya varias preguntas relacionadas que formen parte
    de un mismo informe.

    Si el usuario pide un informe pero no especifica secciones concretas, el agente
    debe construir una propuesta razonable de secciones antes de llamar a esta tool.
    Por ejemplo, para un informe de fraude:
    - resumen general del fraude
    - evolución temporal
    - impacto económico
    - segmentación por tipo de tarjeta
    - segmentación por categoría de comercio
    - conclusiones basadas en datos

    La herramienta devuelve:
    - resultados por sección
    - SQL ejecutado
    - columnas
    - filas
    - advertencias
    - errores parciales si alguna sección no puede ejecutarse

    Args:
        report_title (str): Título del informe.
        user_request (str): La solicitud original del usuario.
        sections (list[dict]): Lista de secciones a ejecutar.
        audience (str): Audiencia objetivo del informe.
        period (str | None): Período temporal a analizar.
        include_sql (bool): Si se debe incluir el SQL en la respuesta de cada sección.
        include_tables (bool): Si se deben incluir los datos tabulares.
        max_rows_per_section (int): Límite de filas a retornar por sección.

    Returns:
        dict: Diccionario estructurado con los resultados para poblar el informe.
    """
    # Llamada a la herramienta interna con los parámetros recibidos.
    return tool_generate_executive_report(
        report_title=report_title,
        user_request=user_request,
        sections=sections,
        audience=audience,
        period=period,
        include_sql=include_sql,
        include_tables=include_tables,
        max_rows_per_section=max_rows_per_section,
    )
    


@mcp.tool
@with_execution_time
def get_report_blueprint() -> dict:
    """
    Devuelve todos los blueprints de informes disponibles como ejemplos de referencia
    de estructura y sintaxis.

    Úsala ANTES de llamar a generate_executive_report para entender el formato
    esperado de las secciones. Los blueprints son ejemplos reales del dominio de este servidor;
    puedes adaptar su estructura para construir cualquier tipo de informe personalizado.

    Esta herramienta no usa IA generativa, no consulta la base de datos y no ejecuta SQL.

    Returns:
        dict: Objeto que contiene la estructura y detalle de los blueprints.
    """
    return tool_get_report_blueprint()


def _create_admin_app():
    """
    Crea la aplicacion FastAPI del panel de administracion.

    Returns:
        FastAPI: Instancia de la aplicación FastAPI configurada.
    """
    from pathlib import Path
    from fastapi import FastAPI, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import RedirectResponse
    from app.admin.routes import router as admin_router, _RequiresLogin

    app_fastapi = FastAPI(title="TFM MCP Admin Panel")
    app_fastapi.include_router(admin_router)

    # Handler para redirigir a login cuando no hay sesion valida.
    @app_fastapi.exception_handler(_RequiresLogin)
    async def _redirect_to_login(request: Request, exc: _RequiresLogin):
        return RedirectResponse(url="/admin/login", status_code=303)

    # Servir archivos estaticos del panel admin.
    static_dir = Path(__file__).parent / "admin" / "static"
    app_fastapi.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin-static")

    return app_fastapi

# --- CONFIGURACIÓN DE LA APLICACIÓN PARA PRODUCCIÓN (ASGI) ---
# Se crea la app a nivel de módulo para que los servidores como Gunicorn/Uvicorn
# (usados por Azure Web Apps) puedan encontrarla automáticamente.
from app.admin.user_store import init_db as init_admin_db
from app.query_store import init_db as init_query_db

print("\n  [INIT] Inicializando bases de datos locales...")
init_admin_db()
init_query_db()

app = _create_admin_app()
mcp_app = mcp.http_app()

# Vincular el ciclo de vida (lifespan) del MCP a la app principal
# Esto es CRÍTICO para que FastMCP inicialice sus tareas asíncronas internas
app.router.lifespan_context = mcp_app.lifespan

# Montar la app MCP en una sub-ruta
app.mount("/mcp_server", mcp_app)

# Exponemos `admin_app` por retrocompatibilidad por si se usa en otros sitios
admin_app = app

if __name__ == "__main__":
    import uvicorn
    import os

    print("\n  [UNIFICADO] Configurando servidor MCP y Panel de Administración en el mismo puerto...")
    
    # El host debe ser 0.0.0.0 para que Azure pueda enrutar el tráfico correctamente
    # En local, settings.SERVER_HOST podría seguir siendo 127.0.0.99 o 0.0.0.0
    host = "0.0.0.0" if settings.SERVER_HOST == "127.0.0.99" else settings.SERVER_HOST
    # En Azure, el puerto a menudo viene por variable de entorno PORT
    port_env = os.environ.get("PORT")
    if port_env:
        port = int(port_env)
    else:
        port = settings.ADMIN_PORT if settings.ADMIN_PORT != 8001 else 8000

    print(f"  [>] Panel Admin disponible en: http://{host}:{port}/admin/")
    print(f"      Login: http://{host}:{port}/admin/login")
    print(f"  [>] MCP SSE URL disponible en: http://{host}:{port}/mcp_server/mcp\n")

    # Ejecutar la aplicación unificada en un único servidor Uvicorn
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")