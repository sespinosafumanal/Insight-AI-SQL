# Documentación Técnica y de Arquitectura: Insight AI-SQL

## 1. Capacidad y Alcance de la Herramienta

### 1.1 Funcionalidades Principales (Core Features)
**Insight AI-SQL** es un servidor basado en el protocolo **MCP (Model Context Protocol)** diseñado para actuar como un puente inteligente entre modelos de lenguaje (LLMs) y bases de datos relacionales, específicamente enfocado en entornos analíticos y de explotación de datos. Sus capacidades principales incluyen:
*   **Generación y Ejecución de SQL mediante IA (Text-to-SQL):** Traducción de lenguaje natural a consultas SQL estructuradas y de solo lectura (`tool_generate_sql`, `tool_ask_database`), utilizando agentes especializados.
*   **Recuperación de Contexto Inteligente (RAG):** Integración con sistemas de búsqueda vectorial para enriquecer las peticiones del usuario con metadatos técnicos (DDL, esquemas, diccionarios de datos) antes de la generación del código SQL.
*   **Generación de Informes Ejecutivos:** Capacidad orquestada para ejecutar múltiples consultas analíticas y ensamblar respuestas basadas en datos duros (`tool_generate_executive_report`), soportado por plantillas arquitectónicas de informes (`tool_get_report_blueprint`).
*   **Panel de Administración Integral:** Interfaz web autónoma para la monitorización del sistema, que incluye visualización de historial de consultas, analíticas de uso y gestión de usuarios administradores.
*   **Mecanismo de Resiliencia:** Sistema interno de reintentos automatizados para asegurar la tolerancia a fallos transitorios en las conexiones con servicios externos y APIs de inferencia.

### 1.2 Casos de Uso y Valor de Negocio
El sistema aporta un valor crítico al negocio al democratizar el acceso a la información compleja. Los principales casos de uso son:
*   **Autoservicio Analítico:** Permite a perfiles de negocio y analistas de datos obtener respuestas fundamentadas sin depender del equipo de ingeniería para la extracción ad-hoc de información.
*   **Diagnóstico y Exploración Acelerada:** Al integrar el esquema de la base de datos y metadatos del negocio, el sistema puede identificar patrones y segmentaciones estructurales en tiempos de respuesta drásticamente reducidos.
*   **Automatización de Reportes:** Transformación de preguntas de alto nivel en informes ejecutivos multicapa, basados exclusivamente en evidencias y datos extraídos en tiempo real.

### 1.3 Requisitos No Funcionales
*   **Escalabilidad:** Procesamiento concurrente de peticiones asegurado mediante la naturaleza asíncrona de FastAPI y Uvicorn, permitiendo manejar múltiples conexiones simultáneamente.
*   **Seguridad:** Restricción estricta de consultas generadas a operaciones de "solo lectura" (Read-Only) mediante validaciones sintácticas. Además, el panel de administración cuenta con autenticación cifrada mediante `Bcrypt`.
*   **Rendimiento:** Tiempos de latencia minimizados mediante la recuperación semántica previa a la inferencia, acotando el contexto de entrada y maximizando la precisión del modelo fundacional en el primer intento.

---

## 2. Arquitectura del Sistema

### 2.1 Tipo de Arquitectura
El sistema adopta una arquitectura de **Monolito Modular** orientado a servicios, exponiéndose externamente bajo la especificación **MCP**. 
*   **Justificación:** Esta arquitectura centraliza la lógica de negocio (RAG, Text-to-SQL, ejecución en BD) y la capa de administración en un único artefacto, facilitando el despliegue en entornos Cloud. Mantiene una separación lógica estricta mediante enrutadores independientes, evitando que la carga operativa de la administración interfiera con la disponibilidad de las interfaces de IA.

### 2.2 Stack Tecnológico
El ecosistema tecnológico ha sido seleccionado por su madurez y robustez:
*   **Lenguaje Core:** Python 3.11+.
*   **Frameworks y APIs:**
    *   **FastMCP:** Implementación del Model Context Protocol para la exposición de capacidades (*tools*).
    *   **FastAPI & Uvicorn:** Base para el panel de administración web y servidor HTTP asíncrono.
    *   **Jinja2 & HTML/JS:** Renderizado interactivo y lógica de presentación del frontend analítico.
*   **Bases de Datos:**
    *   **PostgreSQL (`psycopg2-binary`):** Motor de base de datos objetivo donde residen los datos corporativos.
    *   **SQLite:** Almacenamiento local ultraligero y transaccional (`admin/user_store.py`, `query_store.py`) para persistencia de telemetría y perfiles.
*   **IA y Procesamiento de Datos:**
    *   **Azure OpenAI:** Orquestación de agentes Text-to-SQL y generación cognitiva.
    *   **Azure AI Search (`azure-search-documents`):** Motor de búsqueda vectorial para el paradigma RAG (Retrieval-Augmented Generation).
    *   **Pandas & SQLParse:** Estructuración de datos tabulares, sanitización y validación estricta de sentencias SQL.

### 2.3 Flujo de Datos y Comunicación
1.  **Interacción del Cliente (LLM):** El agente cliente invoca una herramienta MCP (ej. `generate_sql` o `generate_executive_report`).
2.  **Enriquecimiento de Contexto (RAG):** El servidor MCP intercepta la petición y consulta el índice vectorial para recuperar esquemas DDL y reglas de negocio relevantes.
3.  **Inferencia y Validación:** El contexto semántico y la instrucción se envían al modelo fundacional para generar el código SQL. El servidor realiza un análisis de seguridad profundo.
4.  **Ejecución y Retorno:** Las consultas se lanzan contra la base de datos analítica, los resultados crudos se procesan, estructuran y se devuelven al cliente MCP listos para el consumo.
5.  **Telemetría y Administración:** Paralelamente, la actividad de generación se indexa en bases de datos locales para su auditoría y revisión asíncrona mediante el panel web.

---

## 3. Detalles Técnicos y de Implementación

### 3.1 Estrategia de Despliegue
La solución está proyectada para un despliegue nativo y resiliente en plataformas Cloud:
*   **Contenedorización Estratégica:** El sistema está preparado para ser paquetizado en contenedores y operado en plataformas Platform-as-a-Service (PaaS) o Kubernetes.
*   **Conectividad Híbrida Segura:** Para despliegues donde la base de datos resida en redes privadas u *On-Premise*, se soporta el enrutamiento a través de túneles salientes (ej. Azure Relay / Hybrid Connections), eliminando la necesidad de abrir puertos expuestos al internet público.
    *   **Nota Arquitectónica (App Service Linux):** Debido al diseño del interceptor de red interno, las Hybrid Connections en contenedores Linux de Azure **no enrutan tráfico dirigido a direcciones IP puras**. El Endpoint configurado en el túnel y en la variable `POSTGRES_HOST` debe ser siempre un nombre de dominio ficticio o DNS (ej. `fraud-db.local`). La traducción final a IP se delega al servidor local receptor (Hybrid Connection Manager) a través de su archivo `hosts` nativo.

### 3.2 Gestión de Configuración (Dual-State)
Para maximizar la seguridad y la flexibilidad operativa sin requerir redespliegues constantes, el sistema divide su configuración en dos capas lógicas:
1.  **Secretos y Credenciales (`.env`):** Almacena tokens de API, contraseñas de bases de datos y claves criptográficas de sesión. Excluido estrictamente del control de versiones.
2.  **Parámetros de Negocio (`settings.yaml`):** Archivo versionable que dictamina el comportamiento funcional (umbrales de recuperación RAG, límites de paginación de SQL, estrategias de reintento). Permite a los equipos afinar el comportamiento cognitivo del servidor sin tocar código.

### 3.3 Consideraciones de Seguridad
El rigor analítico y de infraestructura es imperativo:
*   **Seguridad de Acceso al Panel:** El entorno de validación administrativa está sellado mediante autenticación de sesión. Las contraseñas están salteadas y cifradas mediante el algoritmo **Bcrypt**.
*   **Protección de Ejecución SQL:** El servidor actúa como un *firewall* lógico de datos. Realiza un análisis estático del *Abstract Syntax Tree (AST)* de las consultas generadas, bloqueando intrínsecamente operaciones destructivas o de mutación (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `EXECUTE`, etc.).
*   **Gestión de Secretos:** La inyección de dependencias críticas se realiza exclusivamente a través del entorno de ejecución, adhiriéndose a normativas de seguridad empresarial (ej. 12-Factor App).

### 3.4 Resiliencia y Tolerancia a Fallos
Dada la dependencia de APIs cognitivas externas (LLMs, motores vectoriales) y bases de datos transaccionales, el sistema implementa un motor de reintentos avanzado. Este módulo intercepta excepciones transitorias (latencia impredecible, límites de concurrencia de APIs) y ejecuta estrategias de retroceso exponencial (*Exponential Backoff*). Esto blinda el servidor y garantiza que la inestabilidad temporal de un servicio subyacente no interrumpa el flujo del usuario final.
