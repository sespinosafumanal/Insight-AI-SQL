# Diseño del Panel de Administración y Validación de Consultas

## Introducción
Una de las funcionalidades diferenciales de Insight AI-SQL es la incorporación de un panel de administración que permite revisar las consultas generadas y ejecutadas correctamente. Este panel introduce una supervisión humana (*Human-in-the-loop*) antes de que una consulta pase a formar parte del conocimiento reutilizable del sistema, garantizando así la calidad y fiabilidad de las respuestas almacenadas.

## Arquitectura y Almacenamiento
El flujo de validación captura automáticamente las consultas que el modelo ha generado con éxito. Esta información se almacena de forma estructurada en una base de datos local SQLite denominada `query_candidates.db`. 

Los datos capturados para cada consulta candidata incluyen:
- **Pregunta original**: La petición formulada por el usuario en lenguaje natural.
- **SQL generado**: La traducción a código SQL generada por el agente.
- **Resultados de la ejecución**: Número de filas devueltas, nombres de las columnas y una muestra representativa de los datos (*sample rows*).
- **Contexto RAG**: Los identificadores de los documentos recuperados que el modelo utilizó como contexto para formular el SQL.
- **Metadatos adicionales**: Fecha de creación, estado (`pending`, `approved`, `rejected`), fecha de revisión y notas del revisor.

Adicionalmente, el sistema registra el éxito o fracaso de todas las ejecuciones de consultas en una tabla independiente (`query_logs`) para la generación de estadísticas y analíticas de uso.

## Pantallas y Funcionalidades Disponibles
El panel de administración, desarrollado con el framework FastAPI y renderizado en servidor mediante plantillas Jinja2, se compone de varias vistas especializadas:

### 1. Pantalla de Autenticación
El acceso al panel está protegido mediante un formulario de inicio de sesión (`/admin/login`). La sesión de los administradores se gestiona de forma segura a través de una cookie firmada criptográficamente (HMAC con SHA-256) con una validez temporal predefinida (8 horas), asegurando que solo los usuarios autorizados puedan validar consultas.

### 2. Dashboard de Pendientes
Es la pantalla de entrada principal (`/admin/`). Presenta el listado de las consultas pendientes de revisión. Además, la cabecera muestra métricas globales de salud del sistema, incluyendo el total de consultas procesadas, la cantidad de éxitos y fallos, y la tasa de éxito general (*Success Rate*).

### 3. Detalle de Consulta y Consola Interactiva
Al acceder a una consulta específica, el administrador dispone de un entorno de evaluación completo que muestra todos los datos almacenados de la candidata. Esta vista integra una **Consola Interactiva** que permite:
- **Ejecutar pruebas dinámicas**: El revisor puede editar la consulta SQL generada por el agente y ejecutarla en tiempo real contra la base de datos de destino para verificar y refinar los resultados.
- **Validación de seguridad**: Para prevenir incidentes, las consultas enviadas desde la consola pasan por un validador estricto (`validate_readonly_sql`) que asegura que solo se ejecuten instrucciones de solo lectura (como los comandos `SELECT`).

### 4. Explorador de Esquema (*Schema Explorer*)
Para facilitar la revisión, el panel incluye una herramienta dinámica (`/admin/schema`) que consulta las vistas del sistema (`information_schema`) y extrae el esquema en vivo de la base de datos PostgreSQL conectada. Muestra de forma jerárquica las tablas, columnas, tipos de datos y restricciones (como nulabilidad). Esto permite al revisor corroborar rápidamente si las relaciones (*JOINs*) y filtros aplicados por el agente son estructuralmente correctos sin salir del entorno.

### 5. Historial
Ubicada en `/admin/history`, esta pantalla actúa como registro de auditoría, listando todas las consultas que ya han sido evaluadas. Permite filtrar y revisar las decisiones tomadas en el pasado sobre las consultas "Aprobadas" y "Rechazadas".

### 6. Analíticas y Rendimiento RAG
Una vista dedicada al rendimiento del sistema (`/admin/analytics`). Presenta gráficas temporales del volumen de consultas y un componente interactivo (*Treemap*) diseñado para analizar el impacto de los documentos inyectados en el contexto (RAG). Ofrece métricas como la frecuencia de uso de cada documento y su tasa de aprobación, lo que resulta fundamental para identificar qué partes de la base de conocimiento mejoran o empeoran la calidad del SQL generado.

## Flujo de Acción y Validación
Desde la vista de detalle de cualquier consulta candidata, el revisor humano es responsable de evaluar su calidad, pudiendo tomar dos decisiones clave (ambas permiten adjuntar notas explicativas):

1. **Aprobar**: Si la consulta SQL responde de manera precisa y eficiente a la pregunta original del usuario. En caso de que haya margen de mejora, el revisor puede guardar una **consulta SQL modificada**. Tras la aprobación, la consulta final se envía a **Azure AI Search** para ser indexada. A partir de ese momento, la pareja *Pregunta-SQL* pasa a la memoria a largo plazo del sistema para ser utilizada como ejemplo (Few-Shot Prompting) en futuras consultas similares.
2. **Rechazar**: Si la consulta incurre en alucinaciones, ineficiencias o errores semánticos, se descarta para evitar que el sistema aprenda de respuestas deficientes, archivándose en el historial para futuros diagnósticos.

Este diseño asegura una mejora continua y controlada de la "inteligencia" del modelo, manteniendo un sólido equilibrio entre la automatización basada en Inteligencia Artificial y la precisión requerida en entornos corporativos de explotación de datos.
