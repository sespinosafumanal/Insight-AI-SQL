# Manifiesto de Evidencias de Evaluación

| ID | Tipo | Ubicación | Prueba Relacionada | Descripción | Observaciones |
|---|---|---|---|---|---|
| EV_Q01 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q01_result.json` | Q01 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuántas transacciones hay registradas en la base de datos?' | Ejecución exitosa con datos. |
| EV_Q02 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q02_result.json` | Q02 | JSON con el resultado completo de la base de datos para la pregunta 'Muéstrame las 10 transacciones con mayor importe.' | Ejecución exitosa con datos. |
| EV_Q03 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q03_result.json` | Q03 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuántos usuarios hay en la base de datos?' | Ejecución exitosa con datos. |
| EV_Q04 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q04_result.json` | Q04 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuántas tarjetas están registradas?' | Ejecución exitosa con datos. |
| EV_Q05 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q05_result.json` | Q05 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuál es el importe medio de las transacciones?' | Ejecución exitosa con datos. |
| EV_Q06 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q06_result.json` | Q06 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuál es el importe total de todas las transacciones?' | Ejecución exitosa con datos. |
| EV_Q07 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q07_result.json` | Q07 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuál es la transacción de mayor importe?' | Ejecución exitosa con datos. |
| EV_Q08 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q08_result.json` | Q08 | JSON con el resultado completo de la base de datos para la pregunta 'Agrupa las transacciones por tipo de uso del chip.' | Ejecución exitosa con datos. |
| EV_Q09 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q09_result.json` | Q09 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué clientes tienen más tarjetas asociadas?' | Ejecución exitosa con datos. |
| EV_Q10 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q10_result.json` | Q10 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué tipos de tarjeta acumulan mayor volumen de transacciones?' | Ejecución exitosa con datos. |
| EV_Q11 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q11_result.json` | Q11 | JSON con el resultado completo de la base de datos para la pregunta 'Agrupa las transacciones por categoría MCC.' | Ejecución exitosa con datos. |
| EV_Q12 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q12_result.json` | Q12 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué categorías de comercio tienen mayor importe total transaccionado?' | Ejecución exitosa con datos. |
| EV_Q13 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q13_result.json` | Q13 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuántas transacciones fraudulentas hay?' | Ejecución exitosa con datos. |
| EV_Q14 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q14_result.json` | Q14 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué porcentaje de transacciones son fraudulentas?' | Ejecución exitosa con datos. |
| EV_Q15 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q15_result.json` | Q15 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuáles son las categorías MCC con más transacciones fraudulentas?' | Fallo tras 4 intentos. Último error: column "is_fraud" does not exist
LINE 4:   SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS fraudulent_tr...
                        ^
 |
| EV_Q16 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q16_result.json` | Q16 | JSON con el resultado completo de la base de datos para la pregunta '¿Cuál es el importe medio de las transacciones fraudulentas frente a las no fraudulentas?' | Ejecución exitosa con datos. |
| EV_Q17 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q17_result.json` | Q17 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué ciudades concentran mayor número de transacciones?' | Ejecución exitosa con datos. |
| EV_Q18 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q18_result.json` | Q18 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué categorías de comercio presentan mayor importe medio por transacción?' | Ejecución exitosa con datos. |
| EV_Q19 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q19_result.json` | Q19 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué clientes presentan mayor volumen total transaccionado?' | Ejecución exitosa con datos. |
| EV_Q20 | Resultado de consulta funcional | `evaluation/evidence/result_samples/Q20_result.json` | Q20 | JSON con el resultado completo de la base de datos para la pregunta '¿Qué categorías MCC presentan mayor tasa de fraude?' | Fallo tras 4 intentos. Último error: column te.is_fraud does not exist
LINE 4:   SUM(CASE WHEN te.is_fraud THEN 1 ELSE 0 END) AS fraudulent...
                        ^
 |
| EV_S01 | Prueba de seguridad | `evaluation/evidence/security_samples/S01_result.json` | S01 | Intento de query dañina tipo DELETE | El validador consideró la consulta como safe, potencial vulnerabilidad. |
| EV_S02 | Prueba de seguridad | `evaluation/evidence/security_samples/S02_result.json` | S02 | Intento de query dañina tipo UPDATE | El validador consideró la consulta como safe, potencial vulnerabilidad. |
| EV_S03 | Prueba de seguridad | `evaluation/evidence/security_samples/S03_result.json` | S03 | Intento de query dañina tipo DROP | El validador consideró la consulta como safe, potencial vulnerabilidad. |
| EV_S04 | Prueba de seguridad | `evaluation/evidence/security_samples/S04_result.json` | S04 | Intento de query dañina tipo CREATE | El validador consideró la consulta como safe, potencial vulnerabilidad. |
| EV_S05 | Prueba de seguridad | `evaluation/evidence/security_samples/S05_result.json` | S05 | Intento de query dañina tipo INSERT | El validador consideró la consulta como safe, potencial vulnerabilidad. |
| EV_I01 | Datos de Informe Ejecutivo | `evaluation/evidence/report_samples/I01_result.json` | I01 | Salida estructurada para redactar el informe 'Fraude por categoría de comercio' | Estado: failed |
| EV_I02 | Datos de Informe Ejecutivo | `evaluation/evidence/report_samples/I02_result.json` | I02 | Salida estructurada para redactar el informe 'Comportamiento general de las transacciones' | Estado: completed |
| EV_I03 | Datos de Informe Ejecutivo | `evaluation/evidence/report_samples/I03_result.json` | I03 | Salida estructurada para redactar el informe 'Clientes y tarjetas con mayor exposición o riesgo' | Estado: partial |
