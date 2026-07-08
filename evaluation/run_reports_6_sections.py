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
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    reports = [
        {
            "id": "I01",
            "title": "Distribución geográfica del fraude y transacciones",
            "question": "Genera un informe sobre el impacto del fraude y el volumen de transacciones agrupado por ciudades y estados de los comercios.",
            "sections": [
                {"id": "I01_sec1", "title": "Volumen por ciudad y estado", "question": "Extrae el total de transacciones y tasa de fraude agrupado por ciudad y estado del comercio."},
                {"id": "I01_sec2", "title": "Top ciudades con mayor fraude", "question": "Extrae las 10 ciudades con mayor cantidad absoluta de transacciones fraudulentas."},
                {"id": "I01_sec3", "title": "Top ciudades por volumen económico", "question": "Extrae las 10 ciudades que mueven mayor importe económico total (sum_amount) en transacciones."},
                {"id": "I01_sec4", "title": "Ciudades más seguras", "question": "Extrae las 10 ciudades con mayor número de transacciones que tienen exactamente cero transacciones fraudulentas."},
                {"id": "I01_sec5", "title": "Uso de chip por ciudad", "question": "Muestra la distribución de transacciones según el método de uso (use_chip) agrupado por la ciudad del comercio."},
                {"id": "I01_sec6", "title": "Errores por ciudad", "question": "Enumera los errores más comunes en las transacciones (columna errors) excluyendo los nulos, agrupados por ciudad."}
            ]
        },
        {
            "id": "I02",
            "title": "Comportamiento general de las transacciones",
            "question": "Genera un informe sobre el comportamiento general de las transacciones.",
            "sections": [
                {"id": "I02_sec1", "title": "Métricas globales históricas", "question": "Extrae conteo total, promedio de importe, suma de importe y tasa de fraude global de todas las transacciones."},
                {"id": "I02_sec2", "title": "Transacciones por año", "question": "Agrupa las transacciones por el año de la fecha (date) mostrando volumen y tasa de fraude."},
                {"id": "I02_sec3", "title": "Volumen por tipo de tarjeta", "question": "Cruza transactions con cards y agrupa el volumen y suma de importe por el tipo de tarjeta (card_type)."},
                {"id": "I02_sec4", "title": "Desglose por método de pago", "question": "Agrupa el volumen de transacciones por método de uso (use_chip)."},
                {"id": "I02_sec5", "title": "Top 10 transacciones más altas", "question": "Extrae el detalle de las 10 transacciones individuales con mayor importe (amount)."},
                {"id": "I02_sec6", "title": "Errores técnicos comunes", "question": "Agrupa y cuenta las transacciones por tipo de error (errors) excluyendo los registros sin error."}
            ]
        },
        {
            "id": "I03",
            "title": "Clientes y tarjetas con mayor exposición",
            "question": "Genera un informe sobre clientes y tarjetas con mayor exposición o riesgo.",
            "sections": [
                {"id": "I03_sec1", "title": "Resumen General", "question": "Agrupa las métricas de transacciones y fraude haciendo un JOIN entre users, cards y transactions para cada usuario y tarjeta."},
                {"id": "I03_sec2", "title": "Clientes con mayor límite de crédito", "question": "Extrae los perfiles de usuarios cruzados con tarjetas que tengan mayor límite de crédito, ordenados descendentemente."},
                {"id": "I03_sec3", "title": "Tarjetas en Dark Web", "question": "Muestra los detalles de las tarjetas que tienen la marca card_on_dark_web igual a 'YES'."},
                {"id": "I03_sec4", "title": "Distribución por género", "question": "Muestra el conteo de usuarios agrupados por género (gender) desde la tabla users."},
                {"id": "I03_sec5", "title": "Deuda promedio por género", "question": "Agrupa a los usuarios por género y extrae el promedio de su deuda total (total_debt)."},
                {"id": "I03_sec6", "title": "Top marcas vulneradas", "question": "Cruza cards y transactions para ver qué marca de tarjeta (card_brand) tiene mayor cantidad absoluta de transacciones fraudulentas."}
            ]
        }
    ]

    for r in reports:
        print(f"Generando informe {r['id']} ({r['title']}) con {len(r['sections'])} secciones...")
        rep_res = tool_generate_executive_report(
            report_title=r["title"],
            user_request=r["question"],
            sections=r["sections"]
        )
        
        rep_file = os.path.join(base_dir, "evidence", "report_samples", f"{r['id']}_result.json")
        with open(rep_file, 'w', encoding='utf-8') as f:
            json.dump(rep_res, f, indent=4, ensure_ascii=False, cls=CustomEncoder)
            
        print(f"Guardado en {rep_file}")
        print(f"Estado final: {rep_res.get('status')}")
        print(f"Secciones completadas: {rep_res.get('completed_sections')}\n")

if __name__ == "__main__":
    main()
