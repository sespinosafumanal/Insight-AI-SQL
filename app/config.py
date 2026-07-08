import os
import secrets
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Carga variables de entorno desde un archivo .env si existe.
load_dotenv()

# Cargar configuraciones de negocio desde settings.yaml
root_dir = Path(__file__).parent.parent
settings_yaml_path = root_dir / "settings.yaml"

business_settings = {}
if settings_yaml_path.exists():
    with open(settings_yaml_path, "r", encoding="utf-8") as f:
        business_settings = yaml.safe_load(f) or {}

def get_yaml_val(keys: list, default):
    """Obtiene un valor anidado del YAML, o un valor por defecto si no existe."""
    d = business_settings
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return default
    return d


def _normalize_azure_openai_endpoint(raw_endpoint: str | None) -> str | None:
    # Normaliza el endpoint de Azure OpenAI eliminando sufijos y rutas de proyecto.
    if not raw_endpoint:
        return None

    endpoint = raw_endpoint.rstrip("/")
    project_prefix = "/api/projects/"

    if project_prefix in endpoint:
        endpoint = endpoint.split(project_prefix, 1)[0]

    return endpoint or None


def _parse_bool(raw_value: str | None, default: bool = False) -> bool:
    # Convierte una cadena en booleano con valores comunes.
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}

class Settings:
    # Configuracion de Azure AI Search.
    AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
    AZURE_SEARCH_INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME")
    AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")

    # Configuracion de Azure OpenAI.
    AZURE_OPENAI_ENDPOINT = _normalize_azure_openai_endpoint(os.getenv("AZURE_OPENAI_ENDPOINT"))
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
    AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")

    # Configuracion de PostgreSQL.
    POSTGRES_HOST = os.getenv("POSTGRES_HOST")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "fraud_db")
    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

    # Parametros generales para ejecucion y depuracion SQL.
    SQL_MAX_ROWS = int(get_yaml_val(["sql", "max_rows"], 100))
    SQL_DEBUG_CONTEXT = _parse_bool(os.getenv("SQL_DEBUG_CONTEXT"), default=False)

    # Host del servidor (MCP y Panel Admin).
    SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.99")

    # Panel de administracion.
    ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY") or secrets.token_hex(32)
    ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8001"))

    # Query Store (captura de consultas satisfactorias).
    QUERY_STORE_PATH = os.getenv("QUERY_STORE_PATH", "data/query_candidates.db")
    QUERY_STORE_SAMPLE_ROWS = int(get_yaml_val(["query_store", "sample_rows"], 5))

    # Almacenamiento de usuarios administradores.
    ADMIN_STORE_PATH = os.getenv("ADMIN_STORE_PATH", "data/admin_store.db")

    # Configuración de reintentos en caso de fallos de la consulta SQL generada.
    SQL_MAX_RETRIES = int(get_yaml_val(["sql", "max_retries"], 3))
    
    # Porcentaje máximo de query_examples en los resultados de AI Search.
    MAX_QUERY_EXAMPLE_PCT = float(get_yaml_val(["rag", "max_query_example_pct"], 0.3))

    # Número de documentos a recuperar en RAG
    SEARCH_TOP_DOCS = int(get_yaml_val(["rag", "search_top_docs"], 8))

    # Número máximo de filas por sección en reportes ejecutivos
    REPORT_MAX_ROWS_PER_SECTION = int(get_yaml_val(["reports", "max_rows_per_section"], 50))

# Instancia global de configuracion para uso en el resto del codigo.
settings = Settings()

