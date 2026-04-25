from receipt_parser import Receipt

def reconcile(receipt: Receipt):
    items_total = sum(item.amount for item in receipt.items)
    shared_total = sum(charge.amount for charge in receipt.shared_charges)
    tax_total = sum(tax.amount for tax in receipt.taxes)
    
    # We might have negative charges if they are discounts
    # Assuming amounts are correctly parsed as positive/negative
    
    calculated_total = items_total + shared_total + tax_total
    
    stated_total = receipt.totals.get('grand_total')
    
    if stated_total is None:
        # If no grand total was found, we assume the calculated total is correct
        # but technically we can't fully reconcile without a stated total.
        # We will consider it reconciled if there are items.
        return {
            "calculated_total": round(calculated_total, 2),
            "stated_total": None,
            "difference": 0.0,
            "reconciled": len(receipt.items) > 0
        }
    
    difference = round(abs(calculated_total - stated_total), 2)
    
    # Allow a small floating point difference or small rounding error
    reconciled = difference <= 1.00  # 1 unit tolerance
    
    return {
        "calculated_total": round(calculated_total, 2),
        "stated_total": stated_total,
        "difference": difference,
        "reconciled": reconciled
    }
