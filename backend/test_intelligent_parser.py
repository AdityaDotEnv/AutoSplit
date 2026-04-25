import unittest
from unittest.mock import MagicMock, patch
from intelligent_parser import GeminiItem, GeminiReceiptData, FixedTotals, ReconciliationInfo, refine_with_gemini

class TestIntelligentParser(unittest.TestCase):
    def test_pydantic_models(self):
        item = GeminiItem(id="1", name="Test Item", amount=10.5, quantity=1, raw_text="Test Item 10.5", confidence=0.99)
        self.assertEqual(item.name, "Test Item")
        self.assertEqual(item.amount, 10.5)

    @patch('google.genai.Client')
    @patch('os.environ.get')
    def test_refine_with_gemini_fallback_no_key(self, mock_env, mock_client):
        mock_env.return_value = None
        result = refine_with_gemini("dummy text")
        self.assertIsNone(result)

    @patch('google.genai.Client')
    @patch('os.environ.get')
    def test_refine_with_gemini_success(self, mock_env, mock_client):
        mock_env.return_value = "fake_key"
        
        # Mocking the new SDK response structure
        mock_response = MagicMock()
        mock_response.parsed = GeminiReceiptData(
            items=[GeminiItem(id="1", name="Pizza", amount=15.0, raw_text="Pizza 15.0", confidence=0.95)],
            totals=FixedTotals(grand_total=15.0),
            reconciliation=ReconciliationInfo(calculated_total=15.0, stated_total=15.0, difference=0.0, reconciled=True)
        )
        
        mock_instance = mock_client.return_value
        mock_instance.models.generate_content.return_value = mock_response
        
        result = refine_with_gemini("some raw ocr text")
        self.assertIsNotNone(result)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].name, "Pizza")

if __name__ == '__main__':
    unittest.main()
