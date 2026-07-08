import unittest
from unittest.mock import patch, MagicMock

# Evitar cargar .env o buscar db reales en los tests
import os
os.environ["SQL_MAX_RETRIES"] = "2"
os.environ["QUERY_STORE_SAMPLE_ROWS"] = "1"

# Hay que mockear algunas dependencias antes de importar mcp_tools
with patch('app.config.settings.SQL_MAX_RETRIES', 2):
    from app.mcp_tools import _execute_query_with_retry

class TestRetryMechanism(unittest.TestCase):

    @patch('app.mcp_tools.search_context')
    @patch('app.mcp_tools.generate_sql_from_context')
    @patch('app.mcp_tools.validate_readonly_sql')
    @patch('app.mcp_tools.run_select')
    @patch('app.mcp_tools.save_candidate')
    @patch('app.mcp_tools.reconstruct_sql_on_error')
    def test_successful_query_no_retry(self, mock_reconstruct, mock_save, mock_run, mock_validate, mock_generate, mock_search):
        """Prueba que una consulta exitosa a la primera no desencadene reintentos."""
        mock_search.return_value = [{"id": "doc1"}]
        mock_generate.return_value = "SELECT * FROM table;"
        mock_validate.return_value = (True, None)
        mock_run.return_value = {"columns": ["a"], "rows": [[1]], "row_count": 1, "row_format": "array"}
        
        result = _execute_query_with_retry("pregunta de prueba")
        
        self.assertTrue(result["success"])
        self.assertEqual(result["attempts"], [])
        self.assertEqual(result["sql"], "SELECT * FROM table;")
        mock_reconstruct.assert_not_called()
        mock_save.assert_called_once()

    @patch('app.mcp_tools.search_context')
    @patch('app.mcp_tools.generate_sql_from_context')
    @patch('app.mcp_tools.validate_readonly_sql')
    @patch('app.mcp_tools.run_select')
    @patch('app.mcp_tools.save_candidate')
    @patch('app.mcp_tools.reconstruct_sql_on_error')
    def test_unsafe_query_aborts_immediately(self, mock_reconstruct, mock_save, mock_run, mock_validate, mock_generate, mock_search):
        """Prueba que si una consulta inicial es insegura, aborta y no reintenta."""
        mock_search.return_value = []
        mock_generate.return_value = "DELETE FROM table;"
        mock_validate.return_value = (False, "Contiene DELETE")
        
        result = _execute_query_with_retry("pregunta de prueba")
        
        self.assertFalse(result["success"])
        self.assertFalse(result["safe"])
        self.assertEqual(result["error"], "Contiene DELETE")
        mock_run.assert_not_called()
        mock_reconstruct.assert_not_called()

    @patch('app.mcp_tools.search_context')
    @patch('app.mcp_tools.generate_sql_from_context')
    @patch('app.mcp_tools.validate_readonly_sql')
    @patch('app.mcp_tools.run_select')
    @patch('app.mcp_tools.save_candidate')
    @patch('app.mcp_tools.reconstruct_sql_on_error')
    def test_retry_on_db_error_and_success(self, mock_reconstruct, mock_save, mock_run, mock_validate, mock_generate, mock_search):
        """Prueba que se reintente y logre éxito si falla la primera vez."""
        mock_search.return_value = []
        mock_generate.return_value = "SELECT * FROM tabla_falsa;"
        
        # Primero y segundo son seguros
        mock_validate.side_effect = [(True, None), (True, None)]
        
        # Falla la primera, acierta la segunda
        mock_run.side_effect = [
            Exception("relation 'tabla_falsa' does not exist"), 
            {"columns": ["a"], "rows": [[1]], "row_count": 1, "row_format": "array"}
        ]
        
        # El LLM la corrige
        mock_reconstruct.return_value = "SELECT * FROM tabla_real;"
        
        result = _execute_query_with_retry("pregunta")
        
        self.assertTrue(result["success"])
        self.assertEqual(result["sql"], "SELECT * FROM tabla_real;")
        self.assertEqual(len(result["attempts"]), 1)
        self.assertEqual(result["attempts"][0]["error"], "relation 'tabla_falsa' does not exist")
        self.assertEqual(result["attempts"][0]["sql"], "SELECT * FROM tabla_falsa;")
        
        # Verificamos que se llamó al LLM con la consulta falsa y el error
        mock_reconstruct.assert_called_once_with(
            "pregunta", [], "SELECT * FROM tabla_falsa;", "relation 'tabla_falsa' does not exist"
        )
        mock_save.assert_called_once()

    @patch('app.mcp_tools.settings.SQL_MAX_RETRIES', 2)
    @patch('app.mcp_tools.search_context')
    @patch('app.mcp_tools.generate_sql_from_context')
    @patch('app.mcp_tools.validate_readonly_sql')
    @patch('app.mcp_tools.run_select')
    @patch('app.mcp_tools.reconstruct_sql_on_error')
    def test_exhaust_retries(self, mock_reconstruct, mock_run, mock_validate, mock_generate, mock_search):
        """Prueba que devuelve error tras agotar todos los reintentos."""
        mock_search.return_value = []
        mock_generate.return_value = "SELECT 1"
        mock_validate.return_value = (True, None)
        
        # Falla siempre
        mock_run.side_effect = Exception("Fatal DB Error")
        mock_reconstruct.return_value = "SELECT 2"
        
        result = _execute_query_with_retry("pregunta")
        
        self.assertFalse(result["success"])
        self.assertTrue(result["safe"])
        # Con MAX_RETRIES=2, se intentará la ejecución original + 2 reintentos = 3 veces.
        self.assertEqual(len(result["attempts"]), 3)
        self.assertEqual(mock_run.call_count, 3)
        self.assertEqual(mock_reconstruct.call_count, 2)
        self.assertIn("Fallo tras 3 intentos", result["error"])

if __name__ == '__main__':
    unittest.main()
