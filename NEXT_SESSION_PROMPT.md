# Продължение на работа по maritime-tests — Промпт за нов чат

## КАК ДА ПОЛЗВАШ ТОЗИ ФАЙЛ


**Проект:** maritime-tests — Flask/SQLAlchemy/PostgreSQL/Tailwind SaaS за морски изпити (maradtest.com)
**Repo:** https://github.com/iamyordanbg/maritime-tests
**Production (main, merge-нат код):** https://web-production-ca6b6.up.railway.app
**Текущ работен PR (не е merge-нат):** #16 → preview: https://web-maritime-tests-pr-16.up.railway.app

---

## АРХИТЕКТУРНИ ПРАВИЛА (задължителни, без изключения)

1. **JS → `app/static/js/`**, зареден с `<script src>`. Никога inline логика в `.html`.
2. **CSS → `app/static/css/`**, зареден с `<link rel="stylesheet">`. Никога нов `<style>` блок в `.html`. HTML файловете само **викат** JS/CSS, никога не ги **съдържат** — изключение само малки Jinja data-инжекции (`window.X = {{...}}`) и наистина еднократни (1 файл) inline стилове.
3. **Anti-duplication:** щом блок код/стил се появи на 2-ри файл → спри, extract-вай в общ модул. Не чакай 3-ти дублат. (Урок от сесия: 3 копия на Reading Settings логика + дублирани CSS теми доведоха до едни и същи бъгове, поправяни поотделно.)
4. **Бизнес логика → `app/services/`**, **DB → `app/models/`**, **Routing → `app/routes/`** (само HTTP handling), **Права → `app/permissions/`**.
5. **Макс 500-800 реда/файл** — сигнал за смесени отговорности.
6. **Винаги реален тест** (Jinja parse + `node --check` + функционален end-to-end), не само syntax проверка, преди "готово".
7. **Директорията на файла винаги се изписва** преди промяна която се прелага..
8. **Никакви hardcode-нати fallback стойности** (`|| 30`, `'No restriction'`, `|| 1` и т.н.) без изрично одобрение от потребителя. Ако поле няма стойност/не е приложимо — показва се честно `"N/A"` или подобно, никога измислена стойност по подразбиране, която може да заблуди (напр. Plan details попъп показваше `"30 days"`/`"No restriction"` за Basic/Plus планове, за които тези концепции изобщо не важат — създаваше грешно впечатление, че настройката реално се прилага). Единствен източник на истина за конфигурационни стойности на стандартни планове е `app/services/plans.py: PLANS` — никога hardcode другаде.

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
│   │   │   ├── dashboard.js         (dashboard.html: greeting, news widget, quota modal)
│   │   │   ├── settings.js          (settings.html: парола, профил, delete-account)
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

**Скелети без реален код** да се ориверят и да не се държат, ако има такива да се предупреди!

---

## CI/CD WORKFLOW

```
1. Claude създава branch → прави промени → тества локално (pytest + syntax)
2. Push → PR (GitHub API) → CI (.github/workflows/ci.yml, 55+ pytest теста)
3. Railway PR Environment автоматично прави live preview
4. Claude СПИРА тук — казва "PR готов, CI зелено, preview линк"
5. ПОТРЕБИТЕЛЯТ решава кога да merge-не , а не claude!!!!
```

**КРИТИЧНО:** Claude **никога** не merge-ва сам, без изрична команда. GitHub token има `repo` scope, **няма** `workflow` scope — промени в `.github/workflows/*.yml` изискват ръчно качване от потребителя.

**Railway PR gotcha:** редактиране на variable в СЪЩЕСТВУВАЩА PR среда не се прилага надеждно (референции "замръзват") — единствен фикс: затвори+преотвори PR-а.

---

## ТЕКУЩ СТАТУС

 **PR #16** 

**Известни архитектурни нарушения (все още непоправени):**

**PromoGrant е отделен от GoldGrant** 



**⚠️ Tailwind CSS е предварително компилиран** (`output.css`), не runtime JIT — нов utility клас без прецедент в кода **тихо не работи** визуално, без грешка. Провери преди употреба: `grep -o '\.CLASS-NAME{[^}]*}' app/static/css/output.css` (escape-вай `/` като `\/`). Ако няма резултат → ползвай inline `style="..."` вместо Tailwind клас.



**TESTING_MODE = True** в `app/services/plans.py` — нарочно съкращава план продължителности за тестване. Не променяй без потвърждение.

**Тестови credentials:** `test@maritime.bg`/`test123`, `admin@maritime.bg`/`admin123`.

---

## MARADTEST AUDIT CHECKLIST — категории

**Група А (директно изпълними):** Грешки в кода, Мъртъв код, Jinja архитектура, Конзистентност, Database Audit, Auth/Authorization, API Audit, SaaS Logic, Exam Engine, Production Readiness

**Група Б (частично):** Сигурност (код-ниво да, penetration test не), Производителност, Mobile/Responsive, Lighthouse

**Група В (извън обхват):** SEO (архитектурата да е SEO-friendly by design — Е изпълнимо), Accessibility, Browser Compatibility, Logging/Monitoring, GDPR, Business/UX



---

## ТОН И РАБОТЕН СТИЛ
- Потребителят е технически, но не е разработчик — обяснявай просто, стъпка по стъпка.
- Винаги реален тест преди "готово".
- При фрустрация — признавай грешки директно, продължавай напред без излишни извинения.
- При неяснота — задавай конкретни, затворени въпроси.
