from app.extensions import db
from app.models.promo import PromoCode
import random, string

def generate_promo_code(prefix="MAR"):
    chars = string.ascii_uppercase + string.digits
    code = "".join(random.choices(chars, k=8))
    return f"{prefix}-{code}"

def validate_promo(code):
    return PromoCode.query.filter_by(code=code, is_active=True, is_used=False).first()
