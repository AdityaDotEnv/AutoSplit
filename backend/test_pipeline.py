import unittest
from receipt_parser import parse_receipt, LineItem, Charge, Receipt, clean_number
from reconcile import reconcile

class TestReceiptParser(unittest.TestCase):
    def test_wrapped_names_merge(self):
        # SHAKARKAND
        # CHAAT 1 300
        # -> Shakarkand Chaat 300
        lines = [
            {
                "text": "SHAKARKAND",
                "tokens": [{"text": "SHAKARKAND", "bbox": [10, 10, 100, 20]}]
            },
            {
                "text": "CHAAT 1 300.00",
                "tokens": [
                    {"text": "CHAAT", "bbox": [10, 30, 60, 40]},
                    {"text": "1", "bbox": [70, 30, 80, 40]},
                    {"text": "300.00", "bbox": [90, 30, 140, 40]}
                ]
            }
        ]
        
        receipt = parse_receipt(lines)
        self.assertEqual(len(receipt.items), 1)
        self.assertEqual(receipt.items[0].name, "SHAKARKAND CHAAT")
        self.assertEqual(receipt.items[0].quantity, 1)
        self.assertEqual(receipt.items[0].amount, 300.0)

    def test_tax_and_header_exclusion(self):
        lines = [
            {
                "text": "INVOICE #12345",
                "tokens": [{"text": "INVOICE", "bbox": [10, 10, 60, 20]}, {"text": "#12345", "bbox": [70, 10, 120, 20]}]
            },
            {
                "text": "Item Qty Amt",
                "tokens": [{"text": "Item", "bbox": [10, 30, 40, 40]}, {"text": "Qty", "bbox": [50, 30, 70, 40]}, {"text": "Amt", "bbox": [80, 30, 110, 40]}]
            },
            {
                "text": "PARATHA 3 240.00",
                "tokens": [
                    {"text": "PARATHA", "bbox": [10, 50, 70, 60]},
                    {"text": "3", "bbox": [80, 50, 90, 60]},
                    {"text": "240.00", "bbox": [100, 50, 150, 60]}
                ]
            },
            {
                "text": "SUBTOTAL 240.00",
                "tokens": [
                    {"text": "SUBTOTAL", "bbox": [10, 70, 80, 80]},
                    {"text": "240.00", "bbox": [100, 70, 150, 80]}
                ]
            },
            {
                "text": "CGST 12.00",
                "tokens": [
                    {"text": "CGST", "bbox": [10, 90, 50, 100]},
                    {"text": "12.00", "bbox": [100, 90, 150, 100]}
                ]
            },
            {
                "text": "SGST 12.00",
                "tokens": [
                    {"text": "SGST", "bbox": [10, 110, 50, 120]},
                    {"text": "12.00", "bbox": [100, 110, 150, 120]}
                ]
            },
            {
                "text": "TOTAL 264.00",
                "tokens": [
                    {"text": "TOTAL", "bbox": [10, 130, 60, 140]},
                    {"text": "264.00", "bbox": [100, 130, 150, 140]}
                ]
            }
        ]
        
        receipt = parse_receipt(lines)
        self.assertEqual(len(receipt.items), 1)
        self.assertEqual(receipt.items[0].name, "PARATHA")
        
        self.assertEqual(len(receipt.taxes), 2)
        self.assertEqual(receipt.taxes[0].label, "CGST")
        self.assertEqual(receipt.taxes[1].label, "SGST")
        
        self.assertEqual(receipt.totals.get('subtotal'), 240.00)
        self.assertEqual(receipt.totals.get('grand_total'), 264.00)

class TestReconciliation(unittest.TestCase):
    def test_reconcile_success(self):
        receipt = Receipt(
            items=[LineItem(name="A", quantity=1, unit_price=10.0, amount=10.0),
                   LineItem(name="B", quantity=1, unit_price=20.0, amount=20.0)],
            shared_charges=[],
            taxes=[Charge(label="Tax", amount=3.0, category="tax")],
            totals={"grand_total": 33.0}
        )
        recon = reconcile(receipt)
        self.assertTrue(recon['reconciled'])
        self.assertEqual(recon['calculated_total'], 33.0)
        
    def test_reconcile_failure(self):
        receipt = Receipt(
            items=[LineItem(name="A", quantity=1, unit_price=10.0, amount=10.0)],
            shared_charges=[],
            taxes=[],
            totals={"grand_total": 50.0}
        )
        recon = reconcile(receipt)
        self.assertFalse(recon['reconciled'])
        self.assertEqual(recon['calculated_total'], 10.0)

if __name__ == '__main__':
    unittest.main()
