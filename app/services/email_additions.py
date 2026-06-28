# ---------------------------------------------------------------------------
# ДОБАВИ ТЕЗИ ФУНКЦИИ В КРАЯ НА app/services/email.py
# ---------------------------------------------------------------------------

ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@maritimetests.bg')

PLAN_LABELS = {
    'basic': 'Basic — 7 дни достъп',
    'plus':  'Plus — 30 дни достъп',
    'gold':  'Gold — 10 промокода',
}


def send_plan_activated(to_email: str, user_name: str, plan_name: str) -> bool:
    """
    Изпраща потвърждение до клиента след активиран Basic/Plus план.
    Извиква се от app/services/stripe.py → _handle_checkout_completed()
    """
    plan_label = PLAN_LABELS.get(plan_name, plan_name.capitalize())

    html_content = (
        '<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;'
        'padding:32px;background:#071a2e;border-radius:16px">'
        '<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Морски Тестове</h2>'
        f'<h3 style="color:#fff;margin-bottom:16px">Планът ти е активиран! 🎉</h3>'
        f'<p style="color:rgba(232,237,242,0.8);margin-bottom:8px">Здравей, <strong style="color:#fff">{user_name}</strong>!</p>'
        f'<p style="color:rgba(232,237,242,0.8);margin-bottom:24px">'
        f'Успешно активира план <strong style="color:#e8a020">{plan_label}</strong>. '
        f'Вече имаш пълен достъп до всички тестове.</p>'
        '<a href="https://web-production-ca6b6.up.railway.app/dashboard" '
        'style="display:inline-block;background:#635BFF;color:#fff;padding:14px 32px;'
        'border-radius:10px;text-decoration:none;font-weight:600;font-size:15px">'
        'Към платформата →</a>'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">'
        'Морски Тестове · maritimetests.bg</p>'
        '</div>'
    )
    text_content = (
        f'Здравей, {user_name}!\n\n'
        f'Планът ти {plan_label} е активиран успешно.\n\n'
        f'Влез в платформата:\nhttps://web-production-ca6b6.up.railway.app/dashboard\n\n'
        f'Морски Тестове'
    )

    return send_email(to_email, f'Планът ти е активиран — {plan_label} | Морски Тестове',
                      text_content, html_content)


def send_gold_promo_codes(to_email: str, user_name: str, codes: list[str]) -> bool:
    """
    Изпраща 10 Gold промокода до клиента след успешно плащане.
    Извиква се от app/services/stripe.py → _handle_checkout_completed()
    """
    codes_html = ''.join(
        f'<div style="background:#1a2f4a;border-radius:8px;padding:12px 16px;margin-bottom:8px;'
        f'font-family:monospace;font-size:18px;color:#e8a020;letter-spacing:2px">{code}</div>'
        for code in codes
    )
    codes_text = '\n'.join(f'  {i+1}. {code}' for i, code in enumerate(codes))

    html_content = (
        '<div style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto;'
        'padding:32px;background:#071a2e;border-radius:16px">'
        '<h2 style="color:#e8a020;font-size:22px;margin-bottom:12px">⚓ Морски Тестове</h2>'
        '<h3 style="color:#fff;margin-bottom:16px">Твоите Gold промокода 🥇</h3>'
        f'<p style="color:rgba(232,237,242,0.8);margin-bottom:8px">Здравей, <strong style="color:#fff">{user_name}</strong>!</p>'
        '<p style="color:rgba(232,237,242,0.8);margin-bottom:24px">'
        'Получаваш 10 промокода. Всеки дава <strong style="color:#e8a020">30 дни пълен достъп</strong> '
        'и е валиден 12 месеца.</p>'
        f'{codes_html}'
        '<p style="color:rgba(232,237,242,0.6);font-size:13px;margin-top:20px">'
        'Споделяй кодовете с колеги. Всеки код може да се използва еднократно.</p>'
        '<p style="color:rgba(232,237,242,0.4);font-size:12px;margin-top:24px">'
        'Морски Тестове · maritimetests.bg</p>'
        '</div>'
    )
    text_content = (
        f'Здравей, {user_name}!\n\n'
        f'Ето твоите 10 Gold промокода (всеки = 30 дни достъп, валиден 12 месеца):\n\n'
        f'{codes_text}\n\n'
        f'Морски Тестове'
    )

    return send_email(to_email, 'Твоите Gold промокода — Морски Тестове',
                      text_content, html_content)


def send_admin_new_payment(user_name: str, user_email: str, plan_name: str) -> bool:
    """
    Изпраща известие до admin при всяко ново плащане / абонамент.
    Трябва да се извика от stripe.py → _handle_checkout_completed()
    """
    plan_label = PLAN_LABELS.get(plan_name, plan_name.capitalize())
    subject = f'[Плащане] {user_name} — {plan_label}'
    body = (
        f'Ново плащане получено!\n\n'
        f'Потребител: {user_name}\n'
        f'Имейл: {user_email}\n'
        f'План: {plan_label}\n\n'
        f'Виж потребителите:\n'
        f'https://web-production-ca6b6.up.railway.app/admin/users'
    )
    return send_email(ADMIN_EMAIL, subject, body)
