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


def free_code(id_value: int) -> str:
    """
    Вариант за Free план: 3 Букви + 3 Цифри ГРУПИРАНИ (напр. ABC123), не
    редувани както при alternating_code (D7A0M8). Използва СЪЩАТА
    PRIME/modulus математика (същия общ капацитет 26×26×26×10×10×10 =
    17,576,000 - идентична 0%-колизия гаранция), само редиците на буквите
    и цифрите са различно подредени/групирани.
    """
    radices = [26, 26, 26, 10, 10, 10]  # ляво-надясно: Б,Б,Б,Ц,Ц,Ц
    modulus = 1
    for rad in radices:
        modulus *= rad
    PRIME = 104729
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

    ПОПРАВКА НА БЪГ (race condition): при ДВЕ едновременни заявки за СЪЩИЯ
    (grant_type, grant_id) - напр. потребител с мобилен телефон презарежда
    страницата бързо два пъти, или два gunicorn worker-а обработват
    паралелно - и двете могат да видят "няма съществуващ ред" ПРЕДИ първата
    да е commit-нала, и двете да опитат INSERT на СЪЩИЯ детерминиран код ->
    UniqueViolation на втората -> необработено изключение -> 500 грешка на
    потребителя (реален инцидент, засечен в production логовете). Сега
    хващаме точно тази колизия, rollback-ваме и просто препрочитаме реда,
    който другата заявка вече е записала.
    """
    from ..extensions import db
    from ..models.subscription_history import SubscriptionHistory
    from sqlalchemy.exc import IntegrityError

    existing = SubscriptionHistory.query.filter_by(grant_type=grant_type, grant_id=grant_id).first()
    if existing:
        return existing.subscription_code

    # До 20 опита: обикновено 1-вият стига (race за СЪЩИЯ grant - re-query го
    # намира). Ако кодът е ЗАЕТ от ДРУГ (grant_type, grant_id) чифт (рядка,
    # но реална колизия между различни грантове), пробваме disambiguated
    # вариант (grant_id + N * голямо просто число) вместо да гърмим - това
    # НИКОГА не бива да чупи dashboard-а на потребител (реален production
    # инцидент, засечен многократно в логовете).
    last_error = None
    for attempt in range(20):
        salt = grant_id if attempt == 0 else grant_id + attempt * 9176317
        code = subscription_code(salt, country, grant_type=grant_type)
        row = SubscriptionHistory(grant_type=grant_type, grant_id=grant_id, subscription_code=code)
        db.session.add(row)
        try:
            db.session.commit()
            return code
        except IntegrityError as e:
            db.session.rollback()
            last_error = e
            # Или другата заявка вече е записала СЪЩИЯ (grant_type, grant_id)
            # ред (най-честият случай - обикновен race) - тогава просто го
            # връщаме, без да пробваме нов вариант.
            existing = SubscriptionHistory.query.filter_by(grant_type=grant_type, grant_id=grant_id).first()
            if existing:
                return existing.subscription_code
            # Иначе кодът е зает от ДРУГ чифт - пробваме следващия disambiguated
            # вариант в следващата итерация на цикъла.
            continue

    raise last_error


def subscription_code(grant_id: int, country='BG', grant_type: str = 'plan') -> str:
    """
    Код на самия абонамент/grant — създава се ВЕДНЪЖ, при активацията, и остава
    същият за целия му живот. BG + Буква-Цифра×3 (от grant.id).
    Пример: BGZ2N3O4

    ВАЖНО: PlanGrant.id, GoldGrant.id и PromoCode.id са ТРИ отделни
    auto-increment последователности - без разграничение по тип, еднакво ID
    в различни таблици би дало ИДЕНТИЧЕН код (реален риск - PromoCode.id=5
    и GoldGrant.id=5 биха се сблъскали, тъй като и двете предишно ползваха
    grant_type='gold'). Затова входното число се умножава по 3 (броя
    типове) и се добавя уникален остатък по тип - гарантирано РАЗЛИЧНИ
    входове за всяка комбинация (тип, id), при 1/3 капацитет на тип
    (~5.85М вместо 17.576М), пак огромен запас.
    """
    _type_residue = {'plan': 0, 'gold': 1, 'promo': 2}.get(grant_type, 0)
    offset_id = grant_id * 3 + _type_residue
    return f"{country}{alternating_code(offset_id)}"


def result_public_code(grant_id: int, taken_at, seq_in_grant: int, country='BG', grant_type: str = 'plan') -> str:
    """
    Пълен четим уникален код на РЕЗУЛТАТ: кодът на абонамента (subscription_code)
    + дата(ДДММГГ) + '-' + пореден номер на теста в рамките на този абонамент
    (Gold максимум 150, започва от 001).
    Пример: BGZ2N3O4040726-001
    """
    return f"{subscription_code(grant_id, country, grant_type=grant_type)}{taken_at.strftime('%d%m%y')}-{seq_in_grant:03d}"
