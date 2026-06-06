import random
import string
from datetime import datetime

def generate_promo_code(prefix="MAR"):
    chars = string.ascii_uppercase + string.digits
    code = "".join(random.choices(chars, k=8))
    return f"{prefix}-{code}"

def format_date(dt):
    if not dt:
        return "—"
    return dt.strftime("%d.%m.%Y %H:%M")
