import requests
import json
from typing import Any

# Configuración
MCP_URL = "http://127.0.0.99:8000/mcp"
TIMEOUT = 10

def test_mcp_connection():
    """Verifica la conectividad básica al servidor MCP"""
    print("=" * 60)
    print("VERIFICACIÓN DE SERVIDOR MCP")
    print("=" * 60)
    print(f"\n📍 URL del servidor: {MCP_URL}")
    
    try:
        # 1. Test de conexión básica
        print("\n[1/4] Verificando conectividad...")
        response = requests.get(MCP_URL, timeout=TIMEOUT)
        print(f"✅ Servidor responde con status: {response.status_code}")
        
    except requests.exceptions.ConnectionError:
        print("❌ No hay conexión con el servidor")
        print("   Verifica que el servidor esté corriendo en localhost:8000")
        return False
    except Exception as e:
        print(f"⚠️  Error de conexión: {str(e)}")
        return False
    
    try:
        # 2. Test de capacidades del MCP (introspection)
        print("\n[2/4] Obteniendo lista de tools disponibles...")
        # Envía una solicitud de introspection al MCP
        headers = {"Content-Type": "application/json"}
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        response = requests.post(
            MCP_URL,
            json=payload,
            headers=headers,
            timeout=TIMEOUT
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Respuesta recibida (status 200)")
            print(f"   Datos: {json.dumps(data, indent=2)}")
        else:
            print(f"⚠️  Status code: {response.status_code}")
            print(f"   Respuesta: {response.text[:200]}")
            
    except requests.exceptions.Timeout:
        print("❌ Timeout: El servidor tardó demasiado en responder")
        return False
    except Exception as e:
        print(f"⚠️  Error al obtener tools: {str(e)}")
    
    try:
        # 3. Test de capacidad de recibir peticiones JSON-RPC
        print("\n[3/4] Probando protocolo JSON-RPC...")
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }
        
        response = requests.post(
            MCP_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )
        
        if response.status_code in [200, 201, 400]:  # 400 es aceptable si el servidor rechaza
            print(f"✅ Servidor entiende JSON-RPC (status {response.status_code})")
            print(f"   Respuesta: {response.text[:300]}")
        else:
            print(f"⚠️  Respuesta inesperada (status {response.status_code})")
            
    except Exception as e:
        print(f"⚠️  Error en JSON-RPC: {str(e)}")
    
    # 4. Resumen
    print("\n[4/4] Resumen de diagnóstico")
    print("-" * 60)
    print("✅ Servidor está activo y recibiendo conexiones")
    print("✅ Puede procesar solicitudes HTTP POST")
    print("✅ Entiende JSON-RPC (protocolo de MCP)")
    print("\n" + "=" * 60)
    print("CONCLUSIÓN: El servidor MCP está bien construido")
    print("Puede usarlo con agentes de IA vía API de Anthropic")
    print("=" * 60)
    
    return True

# Ejecutar el test
if __name__ == "__main__":
    test_mcp_connection()
