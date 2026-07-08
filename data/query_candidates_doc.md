# Documentación de la Carpeta `data` y Bases de Datos Locales

Este documento contiene el análisis técnico y funcional de los archivos y bases de datos locales alojados en la carpeta `data` del servidor MCP (`Insight AI-SQL MCP Server`).

---

## 1. Resumen Ejecutivo
La carpeta `data` sirve como el medio de almacenamiento local principal para la persistencia de datos del servidor MCP. Actualmente, está apoyada en el uso de SQLite para gestionar tres dominios de información clave, divididos en **dos archivos independientes por motivos de seguridad y arquitectura**:

*   **Almacén de Consultas Candidatas (Query Store):** Repositorio de tránsito de consultas RAG generadas para revisión humana (`query_candidates`).
*   **Telemetría y Logs:** Registro del éxito o error al ejecutar las consultas SQL contra la base de datos PostgreSQL en producción (`query_logs`).
*   **Gestión de Usuarios (Admin Panel):** Almacenamiento seguro de credenciales cifradas para el acceso autenticado al panel de administración (`admin_users`).

**Archivos en el directorio:**
*   **`query_candidates.db`**: Base de datos SQLite principal para la operativa de IA. Agrupa internamente las tablas de `query_candidates` y `query_logs`.
*   **`admin_store.db`**: Base de datos aislada dedicada exclusivamente al control de acceso de los administradores (`admin_users`).

---

## 2. Diccionarios de Datos

A continuación se detalla la estructura de tablas repartida en los diferentes archivos SQLite.

### 2.1. Archivo: `query_candidates.db` (Modo WAL habilitado)

#### Tabla: `query_candidates`
*   **Propósito:** Almacenar el registro histórico de consultas SQL candidatas generadas por el sistema, sus metadatos de ejecución y el estado de la revisión.

| Columna | Tipo de Datos | ¿Nulo? | Valor por Defecto | Tipo de Clave | Descripción |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`id`** | `TEXT` | No | - | **PK** | Identificador único del registro (UUID). |
| **`question`** | `TEXT` | No | - | - | Pregunta en lenguaje natural introducida por el usuario. |
| **`sql`** | `TEXT` | No | - | - | Sentencia SQL (PostgreSQL) generada para la base de datos externa (`fraud_db`). |
| **`columns`** | `TEXT` | Sí | `NULL` | - | Formato JSON (Array). Nombres de las columnas devueltas por la consulta. |
| **`row_count`** | `INTEGER` | Sí | `NULL` | - | Número total de registros devueltos al ejecutar la SQL. |
| **`sample_rows`** | `TEXT` | Sí | `NULL` | - | Formato JSON (Matriz). Muestra representativa de los datos. |
| **`context_doc_ids`** | `TEXT` | Sí | `NULL` | - | Formato JSON (Array). Identificadores de documentos de contexto de Azure AI Search. |
| **`status`** | `TEXT` | No | `'pending'` | - | Estado de la revisión. Protegido por una restricción de integridad (`CHECK (status IN ('pending', 'approved', 'rejected'))`). |
| **`created_at`** | `TEXT` | No | - | - | Fecha y hora en formato ISO 8601 (UTC) en la que se registró la candidata. |
| **`reviewed_at`** | `TEXT` | Sí | `NULL` | - | Fecha y hora (ISO 8601) de la revisión. |
| **`reviewer_notes`** | `TEXT` | Sí | `NULL` | - | Comentarios escritos por el administrador durante la revisión. |

**Índices de Rendimiento:**
*   `idx_query_candidates_status_date`: Índice compuesto sobre `(status, created_at DESC)` para acelerar las lecturas en el dashboard de administrador.

#### Tabla: `query_logs`
*   **Propósito:** Almacenar de forma simplificada eventos del éxito o fracaso de las ejecuciones SQL, permitiendo nutrir los gráficos y estadísticas del dashboard.

| Columna | Tipo de Datos | ¿Nulo? | Valor por Defecto | Tipo de Clave | Descripción |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`id`** | `TEXT` | No | - | **PK** | Identificador único del registro de log (UUID). |
| **`success`** | `INTEGER`| No | - | - | Valor booleano (1 = Éxito, 0 = Fallo) que indica si la consulta SQL se ejecutó sin errores. |
| **`created_at`** | `TEXT` | No | - | - | Fecha y hora de ejecución de la consulta (formato ISO 8601). |

**Índices de Rendimiento:**
*   `idx_query_logs_date`: Índice sobre `(created_at DESC)` para las consultas cronológicas.

---

### 2.2. Archivo: `admin_store.db` (Aislado por seguridad)

#### Tabla: `admin_users`
*   **Propósito:** Gestionar el control de acceso de los administradores. Desacoplado de los datos operativos para que si los logs de consultas saturan el sistema de archivos, el administrador siga pudiendo autenticarse.

| Columna | Tipo de Datos | ¿Nulo? | Valor por Defecto | Tipo de Clave | Descripción |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **`id`** | `TEXT` | No | - | **PK** | Identificador único del usuario administrador (UUID). |
| **`username`** | `TEXT` | No | - | **UNIQUE**| Nombre de usuario (normalizado en minúsculas). |
| **`password`** | `TEXT` | No | - | - | Contraseña cifrada (`bcrypt`). |
| **`created_at`** | `TEXT` | No | - | - | Fecha de registro del usuario (ISO 8601). |

---

## 3. Relaciones Conceptuales (Arquitectura Desnormalizada)

Al estar pensado para el almacenamiento de logs y estados transaccionales aislados de la lógica de un RAG externo, el esquema SQLite prescinde de validación de referencias foráneas (`FOREIGN KEY`). Las relaciones principales son conceptuales:

1.  **JSON Embebido:** La tabla `query_candidates` agrupa atributos multivaluados internamente mediante arrays serializados a texto JSON (`context_doc_ids` y `columns`). Esto simplifica las escrituras pero impide validación estricta relacional.
2.  **Relación Hacia el Ecosistema Externo:**
    *   Los strings en `context_doc_ids` corresponden uno a uno con los identificadores de chunks del **Índice de Azure AI Search**.
    *   La columna `sql` está indisolublemente vinculada al esquema de la base de datos externa **PostgreSQL** en producción (`fraud_db`).

---

## 4. Consultas de Diagnóstico y Análisis Recomendadas

### Consulta 1: Resumen de Estado de Candidatas
```sql
SELECT 
    status AS Estado,
    COUNT(*) AS [Total de Consultas],
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM query_candidates), 2) AS [Porcentaje (%)]
FROM query_candidates
GROUP BY status;
```

### Consulta 2: Tasa de Éxito Histórica (Telemetría)
```sql
SELECT 
    COUNT(*) AS [Total Consultas Ejecutadas],
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS [Exitosas],
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS [Fallidas],
    ROUND(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS [Tasa de Éxito Global (%)]
FROM query_logs;
```

### Consulta 3: Actividad Diaria Combinada
Muestra el volumen de consultas fallidas frente a las exitosas, agrupadas día por día.
```sql
SELECT 
    date(created_at) AS log_date,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
    SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
FROM query_logs
GROUP BY log_date
ORDER BY log_date DESC;
```

### Consulta 4: Uso de Documentos (Aplanamiento JSON)
Descubre qué documentos recuperados del RAG son los más frecuentemente usados por la IA:
```sql
SELECT 
    je.value AS [ID Documento Contexto],
    COUNT(*) as [Veces Utilizado]
FROM query_candidates qc, json_each(qc.context_doc_ids) je
WHERE json_valid(qc.context_doc_ids) = 1
GROUP BY je.value
ORDER BY [Veces Utilizado] DESC;
```

---

## 5. Observaciones Finales

*   **Entorno Saneado:** Se ha añadido un `.gitignore` para excluir todos los archivos `*.db` y se ha eliminado cualquier archivo legado vacío, manteniendo la carpeta `data` exclusivamente como origen de repositorios locales autogenerados.
*   **Retención de Logs (Pendiente):** Actualmente no hay un proceso cron para limpiar `query_logs`. A medida que el servidor ejecute peticiones, esta tabla crecerá indefinidamente. A futuro, se recomienda añadir un proceso que ejecute un borrado cíclico (e.g. conservar solo 30 días).
*   **Migraciones:** En el esquema actual, SQLite no admite migraciones fáciles (`ALTER TABLE` para restricciones) de modo dinámico, de ahí que los esquemas se inyecten solo en la primera creación.
