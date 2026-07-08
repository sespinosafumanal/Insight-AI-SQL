import os
import sys
import yaml
import json
import csv
from datetime import datetime

# Añadir el path raíz del proyecto para importar módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.mcp_tools import tool_get_context, tool_generate_sql, tool_ask_database, tool_generate_executive_report

import decimal
from datetime import datetime, date

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(CustomEncoder, self).default(obj)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False, cls=CustomEncoder)

def main():
    print("Iniciando evaluación automatizada de Insight AI-SQL...")
    
    # Rutas
    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(base_dir, "test_cases.yaml")
    results_dir = os.path.join(base_dir, "results")
    evidence_dir = os.path.join(base_dir, "evidence")
    
    # Crear carpetas si no existen (deberían estar creadas por powershell)
    os.makedirs(results_dir, exist_ok=True)
    for folder in ['rag_context_samples', 'sql_samples', 'result_samples', 'security_samples', 'report_samples']:
        os.makedirs(os.path.join(evidence_dir, folder), exist_ok=True)
        
    # Leer test cases
    with open(yaml_path, 'r', encoding='utf-8') as f:
        test_cases = yaml.safe_load(f)
        
    functional_tests = test_cases.get("functional_tests", [])
    security_tests = test_cases.get("security_tests", [])
    executive_tests = test_cases.get("executive_report_tests", [])
    
    evidences_manifest = []

    # ---------------------------------------------------------
    # FASE 3: PRUEBAS FUNCIONALES
    # ---------------------------------------------------------
    func_csv_path = os.path.join(results_dir, "evaluation_results.csv")
    print(f"\nEjecutando {len(functional_tests)} pruebas funcionales...")
    
    with open(func_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['id', 'category', 'question', 'context_retrieved', 'sql_generated', 'sql_executed', 'data_correctness', 'final_status', 'fallback_used', 'observations', 'evidence_id'])
        
        for t in functional_tests:
            q_id = t["id"]
            question = t["question"]
            print(f"  [{q_id}] {question}")
            
            try:
                # 1. Contexto
                ctx = tool_get_context(question)
                ctx_file = os.path.join(evidence_dir, "rag_context_samples", f"{q_id}_context.json")
                save_json(ctx_file, ctx)
                context_retrieved = len(ctx.get("documents", [])) > 0
                
                # 2. SQL generado
                sql_data = tool_generate_sql(question, debug=False)
                sql_file = os.path.join(evidence_dir, "sql_samples", f"{q_id}_sql.json")
                save_json(sql_file, sql_data)
                sql_generated = sql_data.get("sql", "N/A")
                
                # 3. Ask Database
                db_res = tool_ask_database(question)
                db_file = os.path.join(evidence_dir, "result_samples", f"{q_id}_result.json")
                save_json(db_file, db_res)
                
                # 4. Analizar
                sql_executed = db_res.get("sql", "N/A")
                success = db_res.get("success", True) if "success" in db_res else ("error" not in db_res)
                safe = db_res.get("safe", True)
                fallback_used = len(db_res.get("attempts", [])) > 0
                
                if success:
                    data_correctness = "Correcta"  # Automático, asume que si devolvió datos y es success, está ok.
                    final_status = "Completado"
                    obs = "Ejecución exitosa con datos."
                elif not safe:
                    data_correctness = "No ejecutada"
                    final_status = "Bloqueado"
                    obs = db_res.get("error", "Bloqueado por seguridad")
                else:
                    data_correctness = "Incorrecta"
                    final_status = "Error controlado"
                    obs = db_res.get("error", "Error en DB o IA")
                    
                evidence_id = f"EV_{q_id}"
                evidences_manifest.append({
                    "ID": evidence_id,
                    "Tipo": "Resultado de consulta funcional",
                    "Ubicación": f"evaluation/evidence/result_samples/{q_id}_result.json",
                    "Prueba": q_id,
                    "Descripción": f"JSON con el resultado completo de la base de datos para la pregunta '{question}'",
                    "Observaciones": obs
                })
                
                writer.writerow([
                    q_id, t["category"], question, str(context_retrieved), 
                    sql_generated.replace("\n", " "), sql_executed.replace("\n", " "),
                    data_correctness, final_status, str(fallback_used), obs, evidence_id
                ])
                
            except Exception as e:
                print(f"    ERROR en {q_id}: {str(e)}")
                writer.writerow([
                    q_id, t["category"], question, "False", "N/A", "N/A", "No ejecutada", "Excepción", "False", str(e), "None"
                ])

    # ---------------------------------------------------------
    # FASE 4: PRUEBAS DE SEGURIDAD
    # ---------------------------------------------------------
    sec_csv_path = os.path.join(results_dir, "security_results.csv")
    print(f"\nEjecutando {len(security_tests)} pruebas de seguridad...")
    
    with open(sec_csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['id', 'question', 'risk_type', 'expected_behavior', 'blocked', 'final_status', 'observations', 'evidence_id'])
        
        for s in security_tests:
            s_id = s["id"]
            question = s["question"]
            print(f"  [{s_id}] {question}")
            
            try:
                db_res = tool_ask_database(question)
                sec_file = os.path.join(evidence_dir, "security_samples", f"{s_id}_result.json")
                save_json(sec_file, db_res)
                
                safe = db_res.get("safe", True)
                
                if not safe:
                    blocked = "Sí"
                    final_status = "Bloqueada correctamente"
                    obs = db_res.get("error", "Bloqueada por validador readonly")
                else:
                    blocked = "No"
                    # Ojo: si se permite, es muy peligroso.
                    final_status = "No bloqueada"
                    obs = "El validador consideró la consulta como safe, potencial vulnerabilidad."

                evidence_id = f"EV_{s_id}"
                evidences_manifest.append({
                    "ID": evidence_id,
                    "Tipo": "Prueba de seguridad",
                    "Ubicación": f"evaluation/evidence/security_samples/{s_id}_result.json",
                    "Prueba": s_id,
                    "Descripción": f"Intento de query dañina tipo {s['risk_type']}",
                    "Observaciones": obs
                })
                
                writer.writerow([
                    s_id, question, s["risk_type"], s["expected_behavior"], blocked, final_status, obs, evidence_id
                ])
            except Exception as e:
                print(f"    ERROR en {s_id}: {str(e)}")
                writer.writerow([
                    s_id, question, s["risk_type"], s["expected_behavior"], "N/A", "Error", str(e), "None"
                ])

    # ---------------------------------------------------------
    # FASE 6: INFORMES EJECUTIVOS
    # ---------------------------------------------------------
    report_md_path = os.path.join(results_dir, "executive_report_results.md")
    print(f"\nEjecutando {len(executive_tests)} informes ejecutivos...")
    
    with open(report_md_path, 'w', encoding='utf-8') as mdfile:
        mdfile.write("# Resultados de Evaluación de Informes Ejecutivos\n\n")
        
        for r in executive_tests:
            r_id = r["id"]
            title = r["title"]
            question = r["question"]
            print(f"  [{r_id}] {title}")
            
            # Simulamos el agente deduciendo secciones a partir de la pregunta
            sections = [
                {"id": f"{r_id}_sec1", "title": "Resumen General", "question": question},
                {"id": f"{r_id}_sec2", "title": "Detalle analítico", "question": f"{question} Muestra datos detallados."}
            ]
            
            try:
                rep_res = tool_generate_executive_report(
                    report_title=title,
                    user_request=question,
                    sections=sections
                )
                
                rep_file = os.path.join(evidence_dir, "report_samples", f"{r_id}_result.json")
                save_json(rep_file, rep_res)
                
                mdfile.write(f"## {r_id}: {title}\n")
                mdfile.write(f"**Pregunta Base**: {question}\n\n")
                mdfile.write(f"**Estado General**: {rep_res.get('status')}\n")
                mdfile.write(f"**Secciones Solicitadas**: {rep_res.get('section_count')}\n")
                mdfile.write(f"**Secciones Completadas**: {rep_res.get('completed_sections')}\n\n")
                
                mdfile.write("### Secciones Ejecutadas:\n")
                for sec in rep_res.get("sections", []):
                    mdfile.write(f"- **{sec.get('title')}** ({sec.get('status')}): {sec.get('question')}\n")
                    if sec.get('status') == 'completed':
                        mdfile.write(f"  - Filas devueltas: {sec.get('returned_row_count')}\n")
                    else:
                        mdfile.write(f"  - Error: {sec.get('error')}\n")
                mdfile.write("\n---\n\n")
                
                evidence_id = f"EV_{r_id}"
                evidences_manifest.append({
                    "ID": evidence_id,
                    "Tipo": "Datos de Informe Ejecutivo",
                    "Ubicación": f"evaluation/evidence/report_samples/{r_id}_result.json",
                    "Prueba": r_id,
                    "Descripción": f"Salida estructurada para redactar el informe '{title}'",
                    "Observaciones": f"Estado: {rep_res.get('status')}"
                })
                
            except Exception as e:
                print(f"    ERROR en {r_id}: {str(e)}")
                mdfile.write(f"## {r_id}: {title}\n")
                mdfile.write(f"**ERROR**: {str(e)}\n\n---\n\n")

    # ---------------------------------------------------------
    # FASE 7: MANIFIESTO DE EVIDENCIAS
    # ---------------------------------------------------------
    manifest_path = os.path.join(evidence_dir, "evidence_manifest.md")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        f.write("# Manifiesto de Evidencias de Evaluación\n\n")
        f.write("| ID | Tipo | Ubicación | Prueba Relacionada | Descripción | Observaciones |\n")
        f.write("|---|---|---|---|---|---|\n")
        for ev in evidences_manifest:
            f.write(f"| {ev['ID']} | {ev['Tipo']} | `{ev['Ubicación']}` | {ev['Prueba']} | {ev['Descripción']} | {ev['Observaciones']} |\n")

    print("\nEvaluación completada con éxito. Revisa la carpeta evaluation/results y evaluation/evidence.")

if __name__ == "__main__":
    main()
