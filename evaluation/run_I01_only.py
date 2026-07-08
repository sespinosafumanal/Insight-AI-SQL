import os
import sys
import json
import decimal
from datetime import datetime, date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.mcp_tools import tool_generate_executive_report

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(CustomEncoder, self).default(obj)

def main():
    r_id = "I01"
    title = "Distribución geográfica del fraude y transacciones"
    question = "Genera un informe sobre el impacto del fraude y el volumen de transacciones agrupado por ciudades y estados de los comercios."
    sections = [
        {"id": f"{r_id}_sec1", "title": "Resumen General", "question": question},
        {"id": f"{r_id}_sec2", "title": "Detalle analítico", "question": f"{question} Muestra datos detallados."}
    ]

    print(f"Generando informe {r_id}...")
    rep_res = tool_generate_executive_report(
        report_title=title,
        user_request=question,
        sections=sections
    )
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    rep_file = os.path.join(base_dir, "evidence", "report_samples", f"{r_id}_result.json")
    
    with open(rep_file, 'w', encoding='utf-8') as f:
        json.dump(rep_res, f, indent=4, ensure_ascii=False, cls=CustomEncoder)
        
    print(f"Guardado en {rep_file}")
    print(f"Estado final: {rep_res.get('status')}")
    print(f"Secciones completadas: {rep_res.get('completed_sections')}")

if __name__ == "__main__":
    main()
