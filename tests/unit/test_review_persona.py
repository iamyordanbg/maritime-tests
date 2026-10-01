"""
tests/unit/test_review_persona.py
=================================
Име + морски аватар за отзиви без снимка (app/services/review_persona.py)
и /api/reviews/public.
"""

import re
from pathlib import Path

from app.models.review import Review
from app.services.review_persona import (
    ACCESSORIES, AVATAR_COUNT, BACKGROUNDS, CREATURES, VARIANTS,
    avatar_spec, persona_name, public_identity,
)

AVATARS_JS = Path(__file__).resolve().parents[2] / 'app' / 'static' / 'js' / 'avatars.js'


class TestAvatarSpec:

    def test_166_distinct_avatars(self):
        specs = {tuple(sorted(avatar_spec(i).items())) for i in range(AVATAR_COUNT)}
        assert len(specs) == AVATAR_COUNT == 166

    def test_deterministic(self):
        assert avatar_spec(42) == avatar_spec(42)
        assert persona_name(42) == persona_name(42)

    def test_neighbouring_reviews_look_different(self):
        assert avatar_spec(1)['creature'] != avatar_spec(2)['creature']

    def test_values_in_range(self):
        keys = {k for k, _ in CREATURES}
        for i in range(1, 400):
            s = avatar_spec(i)
            assert s['creature'] in keys
            assert s['accessory'] in ACCESSORIES
            assert 0 <= s['variant'] < VARIANTS
            assert 0 <= s['bg'] < BACKGROUNDS


class TestPersonaName:

    def test_name_has_adjective_creature_and_number(self):
        for i in range(1, 300):
            name = persona_name(i)
            assert re.fullmatch(r'[A-Z][a-z]+[A-Z][a-z]+\d{4}', name), name

    def test_creature_in_name_matches_avatar(self):
        labels = dict(CREATURES)
        for i in range(1, 100):
            assert labels[avatar_spec(i)['creature']] in persona_name(i)


class TestFrontendCatalogInSync:
    """Ключовете в Python каталога трябва да ги има в avatars.js."""

    def test_creatures_and_accessories_exist_in_js(self):
        js = AVATARS_JS.read_text(encoding='utf-8')
        for key, _ in CREATURES:
            assert re.search(r'\b' + key + r':\s*\{', js), f'героят {key} липсва в avatars.js'
        for key in ACCESSORIES:
            assert re.search(r'\b' + key + r':\s*function', js), f'аксесоарът {key} липсва в avatars.js'

    def test_backgrounds_and_variants_match_js(self):
        js = AVATARS_JS.read_text(encoding='utf-8')
        bg_block = re.search(r'var BG = \[(.*?)\];', js, re.S).group(1)
        assert len(re.findall(r"'#[0-9a-fA-F]{6}'", bg_block)) == BACKGROUNDS
        for m in re.finditer(r'colors:\s*\[(.*?)\]', js):
            assert len(re.findall(r"'#[0-9a-fA-F]{6}'", m.group(1))) == VARIANTS


class TestPublicApi:

    def _review(self, db, user, **kw):
        base = dict(user_id=user.id, stars=5, text='Great', status='approved',
                    visibility='anonymous', display_name='Anonymous Sailor',
                    display_picture_url=None, role='Sailor')
        base.update(kw)
        r = Review(**base)
        db.session.add(r)
        db.session.commit()
        return r

    def test_anonymous_gets_generated_name_and_avatar(self, db, free_user):
        r = self._review(db, free_user)
        name, avatar = public_identity(r)
        assert name == persona_name(r.id) and name != 'Anonymous Sailor'
        assert avatar == avatar_spec(r.id)

    def test_google_with_picture_keeps_real_name_and_photo(self, db, free_user):
        r = self._review(db, free_user, visibility='google', display_name='Ivan Petrov',
                         display_picture_url='https://example.com/p.jpg')
        assert public_identity(r) == ('Ivan Petrov', None)

    def test_google_without_picture_gets_avatar_but_real_name(self, db, free_user):
        r = self._review(db, free_user, visibility='google', display_name='Ivan Petrov')
        name, avatar = public_identity(r)
        assert name == 'Ivan Petrov' and avatar == avatar_spec(r.id)

    def test_endpoint_returns_name_and_avatar(self, db, client, free_user):
        r = self._review(db, free_user)
        data = client.get('/api/reviews/public').get_json()
        item = next(i for i in data if i['text'] == 'Great')
        assert item['name'] == persona_name(r.id)
        assert item['avatar'] == avatar_spec(r.id)
        assert item['picture'] is None
