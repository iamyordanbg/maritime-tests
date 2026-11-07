"""
tests/unit/test_verification_emails.py
======================================
Верификационните имейли (OTP код + линк): английски, с MARADTEST.COM най-горе,
без "Морски Тестове" и без кирилица (app/services/email.py).
"""

import re

import pytest

from app.services import email as email_service


@pytest.fixture
def sent(monkeypatch):
    box = {}

    def fake(to_email, subject, text_content, html_content=None):
        box.update(to=to_email, subject=subject, text=text_content, html=html_content)
        return True

    monkeypatch.setattr(email_service, '_brevo_send', fake)
    return box


def _assert_english_brand(box):
    for part in (box['subject'], box['text'], box['html']):
        assert 'MARADTEST.COM' in part
        assert not re.search(r'[Ѐ-ӿ]', part), 'има кирилица'
        assert 'Морски' not in part


class TestOtpEmail:

    def test_english_with_site_name_and_code(self, sent):
        assert email_service.send_otp_email('a@b.com', '123456')
        _assert_english_brand(sent)
        assert '123456' in sent['subject'] and '123456' in sent['text'] and '123456' in sent['html']
        assert sent['to'] == 'a@b.com'

    def test_site_name_is_first_thing_in_html(self, sent):
        email_service.send_otp_email('a@b.com', '654321')
        html = sent['html']
        assert html.index('MARADTEST.COM') < html.index('Verify your account')

    def test_mobile_friendly_table_layout(self, sent):
        email_service.send_otp_email('a@b.com', '111111')
        assert 'max-width:500px;width:100%' in sent['html']
        assert '#050d18' not in sent['html']  # без пълноширочинен тъмен фон
        assert 'position:' not in sent['html']  # Gmail го маха


class TestLinkEmail:

    def test_english_with_site_name_and_link(self, sent):
        assert email_service.send_verification_email('a@b.com', 'tok123')
        _assert_english_brand(sent)
        assert '/verify-email/tok123' in sent['html'] and '/verify-email/tok123' in sent['text']


class TestDurationsFromConstants:

    def test_otp_text_uses_constant(self, sent, monkeypatch):
        monkeypatch.setattr(email_service, 'OTP_VALID_MINUTES', 9)
        email_service.send_otp_email('a@b.com', '123456')
        assert 'valid for 9 minutes' in sent['html'] and '9 minutes' in sent['text']
        assert '5 minutes' not in sent['html']

    def test_link_text_uses_constant(self, sent, monkeypatch):
        monkeypatch.setattr(email_service, 'VERIFY_LINK_VALID_HOURS', 48)
        email_service.send_verification_email('a@b.com', 'tok')
        assert '48 hours' in sent['html'] and '24 hours' not in sent['html']
