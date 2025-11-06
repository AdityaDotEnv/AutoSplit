import stripe
from config import Config
from urllib.parse import urlencode

stripe.api_key = Config.STRIPE_SECRET_KEY

def create_stripe_payment_intent(amount, currency='inr', description='AutoSplit payment'):
    # amount in smallest currency unit
    amt = int(round(amount * 100))
    intent = stripe.PaymentIntent.create(
        amount=amt,
        currency=currency,
        payment_method_types=["card"],
        description=description
    )
    return intent

def venmo_deeplink(username, amount, note='AutoSplit'):
    # venmo web/pay link
    params = {'txn': 'pay', 'recipients': username, 'amount': str(amount), 'note': note}
    return f"https://venmo.com/?{urlencode(params)}"

def upi_deeplink(payee_upi, payee_name, amount, note='AutoSplit'):
    # UPI deep link for mobile apps
    params = {
        'pa': payee_upi,
        'pn': payee_name,
        'am': ("%.2f" % amount),
        'cu': 'INR',
        'tn': note
    }
    q = urlencode(params)
    return f"upi://pay?{q}"
