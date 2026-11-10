"""Privacy policy names Cloudflare Turnstile (Cloudflare's condition for the Invisible widget mode)."""


def test_privacy_page_mentions_turnstile_with_addendum_link(client):
    html = client.get('/privacy').get_data(as_text=True)
    assert 'Cloudflare Turnstile' in html
    assert 'https://www.cloudflare.com/turnstile-privacy-policy/' in html
