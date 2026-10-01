"""
app/services/review_persona.py
==============================
"Persona" за отзиви БЕЗ лична снимка: измислено име (напр. 'BraveOctopus6418')
и морски аватар, избрани детерминистично по id-то на отзива - един и същ отзив
винаги получава същото име и същата иконка (не се сменят при презареждане),
а съседни отзиви са визуално различни.

Аватарите се рисуват от app/static/js/avatars.js. Тук се пази каталогът
(ключове на героите, аксесоарите, брой варианти и цветове на фона) - JS
получава готовия spec през /api/reviews/public и само го рисува.
Ключовете в CREATURES / ACCESSORIES ТРЯБВА да съвпадат с тези в avatars.js
(пази ги tests/unit/test_review_persona.py).
"""

# (ключ за рисуване, име за показване в генерираното име)
CREATURES = [
    ('octopus', 'Octopus'),
    ('whale', 'Whale'),
    ('crab', 'Crab'),
    ('pufferfish', 'Pufferfish'),
    ('seagull', 'Seagull'),
    ('starfish', 'Starfish'),
    ('dolphin', 'Dolphin'),
    ('turtle', 'Turtle'),
    ('shark', 'Shark'),
    ('jellyfish', 'Jellyfish'),
    ('seal', 'Seal'),
    ('penguin', 'Penguin'),
]
ACCESSORIES = ['shades', 'cap', 'glasses', 'bandana', 'headphones']
VARIANTS = 3          # цветови варианта на всеки герой
BACKGROUNDS = 10      # пастелни цвята на кръга (в avatars.js)
AVATAR_COUNT = 166    # брой различни аватари, преди да започне повторение

ADJECTIVES = [
    'Brave', 'Cool', 'Happy', 'Lucky', 'Clever', 'Bold', 'Calm', 'Swift',
    'Sunny', 'Jolly', 'Witty', 'Noble', 'Gentle', 'Mighty', 'Cheerful',
    'Handsome', 'Delightful', 'Funny', 'Proud', 'Steady', 'Merry', 'Daring',
    'Kind', 'Bright',
]

_TOTAL = len(CREATURES) * len(ACCESSORIES) * VARIANTS * BACKGROUNDS
_STRIDE = 997  # просто число, взаимно просто с _TOTAL -> различни комбинации


def avatar_spec(review_id):
    """Spec на аватара за дадено review id. За id-та с различен
    (id % AVATAR_COUNT) спецификациите са различни (166 уникални аватара)."""
    k = int(review_id) % AVATAR_COUNT
    idx = (k * _STRIDE) % _TOTAL
    creature = idx % len(CREATURES)
    idx //= len(CREATURES)
    accessory = idx % len(ACCESSORIES)
    idx //= len(ACCESSORIES)
    variant = idx % VARIANTS
    idx //= VARIANTS
    background = idx % BACKGROUNDS
    return {
        'creature': CREATURES[creature][0],
        'accessory': ACCESSORIES[accessory],
        'variant': variant,
        'bg': background,
    }


def persona_name(review_id):
    """Измислено име от вида 'BraveOctopus6418'. Животното в името е
    животното на аватара."""
    rid = int(review_id)
    spec = avatar_spec(rid)
    creature_label = next(label for key, label in CREATURES if key == spec['creature'])
    adjective = ADJECTIVES[(rid * 31) % len(ADJECTIVES)]
    number = 1000 + (rid * 7919) % 9000
    return f'{adjective}{creature_label}{number}'


def public_identity(review):
    """Какво се показва публично за един одобрен отзив:
    (име, аватар spec или None).
    - реална снимка (Google) -> реалното име + снимката, без аватар;
    - Google без снимка -> реалното име + аватар;
    - анонимен -> измислено име + аватар."""
    has_real_name = review.visibility == 'google' and bool(review.display_name)
    name = review.display_name if has_real_name else persona_name(review.id)
    avatar = None if review.display_picture_url else avatar_spec(review.id)
    return name, avatar
