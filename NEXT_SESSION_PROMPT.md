# Продължение на работа по maritime-tests — Промпт за нов чат

## КАК ДА ПОЛЗВАШ ТОЗИ ФАЙЛ
Копирай целия текст в ново съобщение до Claude + дай **свеж GitHub token** (никога не се пази в repo — чувствителна тайна).

**Проект:** maritime-tests — Flask/SQLAlchemy/PostgreSQL/Tailwind SaaS за морски изпити (maradtest.com)
**Repo:** https://github.com/iamyordanbg/maritime-tests
**Production:** https://web-production-ca6b6.up.railway.app

---

## АРХИТЕКТУРНИ ПРАВИЛА (задължителни, без изключения)

1. **JS → `app/static/js/`**, зареден с `<script src>`. Никога inline логика в `.html`.
2. **CSS → `app/static/css/`**, зареден с `<link rel="stylesheet">`. Никога нов `<style>` блок в `.html`. HTML файловете само **викат** JS/CSS, никога не ги **съдържат** — изключение само малки Jinja data-инжекции (`window.X = {{...}}`) и наистина еднократни (1 файл) inline стилове.
3. **Anti-duplication:** щом блок код/стил се появи на 2-ри файл → спри, extract-вай в общ модул. Не чакай 3-ти дублат. (Урок от сесия: 3 копия на Reading Settings логика + дублирани CSS теми доведоха до едни и същи бъгове, поправяни поотделно.)
4. **Бизнес логика → `app/services/`**, **DB → `app/models/`**, **Routing → `app/routes/`** (само HTTP handling), **Права → `app/permissions/`**.
5. **Макс 500-800 реда/файл** — сигнал за смесени отговорности.
6. **Винаги реален тест** (Jinja parse + `node --check` + функционален end-to-end), не само syntax проверка, преди "готово".
7. **Директорията на файла винаги се изписва** преди промяна.

---

## ЦЕЛЕВО ДЪРВО НА ПРОЕКТА

```
maritime-tests/
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── test.py
│   │   ├── result.py
│   │   ├── ticket.py
│   │   ├── promo.py
│   │   ├── gold_grant.py
│   │   ├── promo_grant.py
│   │   ├── plan_grant.py
│   │   ├── free_session.py
│   │   ├── signal.py
│   │   └── snapshot.py
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── admin.py
│   │   ├── tests.py
│   │   ├── activate.py
│   │   ├── feed.py
│   │   └── billing.py
│   │
│   ├── services/
│   │   ├── email.py
│   │   ├── billing.py
│   │   ├── plans.py
│   │   ├── cache.py
│   │   ├── stripe.py
│   │   └── notifications.py
│   │
│   ├── utils/
│   │   ├── grants.py
│   │   ├── grant_cache.py
│   │   └── codes.py
│   │
│   ├── permissions/
│   │   ├── roles.py
│   │   ├── permissions.py
│   │   └── decorators.py
│   │
│   ├── static/
│   │   ├── css/
│   │   │   ├── output.css          (компилиран Tailwind, автоматично генериран, не пипай ръчно)
│   │   │   └── reading-theme.css   (Dark/Light/Sepia/Ink теми, споделен)
│   │   ├── js/
│   │   │   ├── sidebar.js
│   │   │   ├── base.js
│   │   │   ├── library.js
│   │   │   ├── simulator.js
│   │   │   ├── test.js
│   │   │   ├── result_review.js
│   │   │   └── reading-prefs.js    (споделена Reading Settings логика)
│   │   └── img/
│   │
│   └── templates/
│       ├── layouts/
│       │   ├── base.html
│       │   ├── user_sidebar.html
│       │   └── admin_sidebar.html
│       ├── user/
│       │   ├── dashboard.html
│       │   ├── library.html
│       │   ├── settings.html
│       │   ├── history.html
│       │   ├── simulator.html
│       │   ├── test.html
│       │   └── result_review.html
│       ├── admin/
│       │   ├── users.html
│       │   ├── tests.html
│       │   ├── dashboard.html
│       │   ├── signals.html
│       │   ├── support.html
│       │   └── promos.html
│       └── auth/
│           ├── login.html
│           ├── register.html
│           └── reset.html
│
├── tests/
│   ├── unit/
│   └── conftest.py
│
├── .github/workflows/ci.yml
├── config.py
├── run.py
└── requirements.txt
```

**Скелети без реален код** (само `__init__.py`, не населени): `repositories/`, `middleware/`, `tasks/`, `auth/`, `notifications/`, `audit/`, `api/`.

---

## CI/CD WORKFLOW

```
1. Claude създава branch → прави промени → тества локално (pytest + syntax)
2. Push → PR (GitHub API) → CI (.github/workflows/ci.yml, 55+ pytest теста)
3. Railway PR Environment автоматично прави live preview
4. Claude СПИРА тук — казва "PR готов, CI зелено, preview линк"
5. ПОТРЕБИТЕЛЯТ решава кога да merge-не
```

**КРИТИЧНО:** Claude **никога** не merge-ва сам, без изрична команда. GitHub token има `repo` scope, **няма** `workflow` scope — промени в `.github/workflows/*.yml` изискват ръчно качване от потребителя.

**Railway PR gotcha:** редактиране на variable в СЪЩЕСТВУВАЩА PR среда не се прилага надеждно (референции "замръзват") — единствен фикс: затвори+преотвори PR-а.

---

## ТЕКУЩ СТАТУС

**Отворени PR-ове:** провери с `curl -s -H "Authorization: token <TOKEN>" "https://api.github.com/repos/iamyordanbg/maritime-tests/pulls?state=open"`. PR #7-12 merge-нати. **PR #13** (`refactor/test-html-js-extraction`) отворен, `mergeable: True`, чака потребителско решение — съдържа целия JS/CSS extraction + PromoGrant рефакторинг по-долу.

**Известни архитектурни нарушения (все още непоправени):**
- `app/routes/dashboard.py`: 2169 реда (лимит 800)
- `app/routes/admin.py`: 1365 реда
- `app/static/js/sidebar.js`: 977 реда
- `user_can_access_test()` дублирана в `dashboard.py` И `permissions/roles.py`

**PromoGrant е отделен от GoldGrant** (по изрично искане) — нов модел `app/models/promo_grant.py`, огледален на `GoldGrant`. 13 файла обновени (routes/dashboard.py, activate.py, permissions/roles.py, utils/grants.py, grant_cache.py, admin.py, models/user.py). **Критичен бъг поправен по пътя:** access-control логиката (`find_active_grant_for_test()`, `has_active_plan()`) проверяваше само GoldGrant — Promo потребители биха били реално заключени от купен тест. Тествано реално end-to-end.

**Reading Settings обединени** — `app/static/js/reading-prefs.js` (споделена логика за Dark/Light/Sepia/Ink теми, font size, highlight intensity, background brightness, font weight) + `app/static/css/reading-theme.css` (теми). Работи навсякъде: Simulator, Test/Mix/Mistakes, `/result/<id>`. Page-specific довършителни действия минават през `window.onPrefsApplied(prefs)` hook — page-specific JS файл се зарежда **преди** `reading-prefs.js` в HTML-а.

**⚠️ Tailwind CSS е предварително компилиран** (`output.css`), не runtime JIT — нов utility клас без прецедент в кода **тихо не работи** визуално, без грешка. Провери преди употреба: `grep -o '\.CLASS-NAME{[^}]*}' app/static/css/output.css` (escape-вай `/` като `\/`). Ако няма резултат → ползвай inline `style="..."` вместо Tailwind клас.

**⚠️ Postgres-Testing базата беше празна** в края на предната сесия (`test_result` таблица 0 записа, необяснена причина — връзката потвърдено правилна, изтриващата функция има твърдо 30-дневно ограничение, PostgreSQL логовете нормални). Провери дали данните са се появили наново.

**TESTING_MODE = True** в `app/services/plans.py` — нарочно съкращава план продължителности за тестване. Не променяй без потвърждение.

**Тестови credentials:** `test@maritime.bg`/`test123`, `admin@maritime.bg`/`admin123`.

---

## MARADTEST AUDIT CHECKLIST — категории

**Група А (директно изпълними):** Грешки в кода, Мъртъв код, Jinja архитектура, Конзистентност, Database Audit, Auth/Authorization, API Audit, SaaS Logic, Exam Engine, Production Readiness

**Група Б (частично):** Сигурност (код-ниво да, penetration test не), Производителност, Mobile/Responsive, Lighthouse

**Група В (извън обхват):** SEO (архитектурата да е SEO-friendly by design — Е изпълнимо), Accessibility, Browser Compatibility, Logging/Monitoring, GDPR, Business/UX

**Ред напред:** довърши JS extraction на остатъка → систематичен Group A audit → SEO архитектура → консолидация на дублирана permissions логика → местене на бизнес логика routes→services (спирай за потвърждение на всяка функция поотделно).

---

## ТОН И РАБОТЕН СТИЛ
- Потребителят е технически, но не е разработчик — обяснявай просто, стъпка по стъпка.
- Винаги реален тест преди "готово".
- При фрустрация — признавай грешки директно, продължавай напред без излишни извинения.
- При неяснота — задавай конкретни, затворени въпроси.
