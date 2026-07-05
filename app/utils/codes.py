"""
app/utils/codes.py
====================
Уникални, четими кодове за абонаменти и решени тестове.
Не случайна генерация — детерминирана, обратима формула (умножение по
просто число по модул) от реалното уникално ID в базата. 0% риск от
колизия, докато ID < 17.576 млн, за разлика от случайна генерация,
при която birthday paradox удря много по-рано (~4,200 записа).
"""

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIGITS = "0123456789"


def alternating_code(id_value: int) -> str:
    """
    Буква-Цифра-Буква-Цифра-Буква-Цифра (напр. D7A0M8) —
    26×10×26×10×26×10 = 17,576,000 варианта.
    """
    radices = [26, 10, 26, 10, 26, 10]  # ляво-надясно: Б,Ц,Б,Ц,Б,Ц
    modulus = 1
    for rad in radices:
        modulus *= rad
    PRIME = 104729  # просто число, coprime с 26 и 10 (не се дели на 2, 5, 13)
    scrambled = (int(id_value) * PRIME) % modulus

    digits = []
    n = scrambled
    for rad in reversed(radices):
        n, rem = divmod(n, rad)
        digits.append(rem)
    digits.reverse()

    chars = []
    for rad, val in zip(radices, digits):
        chars.append(LETTERS[val] if rad == 26 else DIGITS[val])
    return ''.join(chars)


def get_or_create_subscription_code(grant_type: str, grant_id: int, country='BG') -> str:
    """
    Постоянно съхранен subscription код — първо проверява таблицата
    subscription_history; ако липсва (стар grant отпреди тази промяна),
    изчислява ГО ЕДИН ПЪТ и го запазва завинаги, за да не се преизчислява
    повече при следващи зареждания.
    """
    from ..extensions import db
    from ..models.subscription_history import SubscriptionHistory

    existing = SubscriptionHistory.query.filter_by(grant_type=grant_type, grant_id=grant_id).first()
    if existing:
        return existing.subscription_code

    code = subscription_code(grant_id, country)
    row = SubscriptionHistory(grant_type=grant_type, grant_id=grant_id, subscription_code=code)
    db.session.add(row)
    db.session.commit()
    return code


def subscription_code(grant_id: int, country='BG') -> str:
    """
    Код на самия абонамент/grant — създава се ВЕДНЪЖ, при активацията, и остава
    същият за целия му живот. BG + Буква-Цифра×3 (от grant.id).
    Пример: BGZ2N3O4
    """
    return f"{country}{alternating_code(grant_id)}"


def result_public_code(grant_id: int, taken_at, seq_in_grant: int, country='BG') -> str:
    """
    Пълен четим уникален код на РЕЗУЛТАТ: кодът на абонамента (subscription_code)
    + дата(ДДММГГ) + '-' + пореден номер на теста в рамките на този абонамент
    (Gold максимум 150, започва от 001).
    Пример: BGZ2N3O4040726-001
    """
    return f"{subscription_code(grant_id, country)}{taken_at.strftime('%d%m%y')}-{seq_in_grant:03d}"
