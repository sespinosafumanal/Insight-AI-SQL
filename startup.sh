#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".env" ]]; then
  echo "No se ha encontrado .env en $ROOT_DIR"
  echo "Crea el archivo .env con las variables descritas en README.md."
  exit 1
fi

IS_WSL=false
if grep -qi microsoft /proc/version 2>/dev/null; then
  IS_WSL=true
fi

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
elif [[ "$IS_WSL" == true ]] && command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif [[ -x ".venv/Scripts/python.exe" ]]; then
  PYTHON_BIN=".venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "No se ha encontrado Python."
  echo "Instala Python o crea un entorno virtual en .venv."
  exit 1
fi

export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

SERVER_HOST="127.0.0.99"
ADMIN_PORT="8001"

if [[ -f ".env" ]]; then
  ENV_HOST=$(grep -E "^SERVER_HOST=" .env | cut -d= -f2 | tr -d '"\r\n ')
  if [[ -n "$ENV_HOST" ]]; then
    SERVER_HOST="$ENV_HOST"
  fi
  ENV_PORT=$(grep -E "^ADMIN_PORT=" .env | cut -d= -f2 | tr -d '"\r\n ')
  if [[ -n "$ENV_PORT" ]]; then
    ADMIN_PORT="$ENV_PORT"
  fi
fi

echo "Iniciando Insight AI-SQL MCP Server..."
echo "Python: $PYTHON_BIN"
echo "URL MCP: http://$SERVER_HOST:8000/mcp"
echo "URL Admin: http://$SERVER_HOST:$ADMIN_PORT/admin/"

"$PYTHON_BIN" -c "import fastmcp" >/dev/null 2>&1 || {
  echo "Faltan dependencias Python para este intérprete."
  echo "Instálalas con:"
  echo "  $PYTHON_BIN -m pip install -r requirements.txt"
  exit 1
}

exec "$PYTHON_BIN" app/main.py
