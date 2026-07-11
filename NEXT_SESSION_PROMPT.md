# Продължение на работа по maritime-tests — Промпт за нов чат

## КАК ДА ПОЛЗВАШ ТОЗИ ФАЙЛ (прочети първо)

Този файл живее в repo-то тук: `NEXT_SESSION_PROMPT.md` (корен на проекта).

**За да стартираш нова сесия правилно:**
1. Отвори нов чат с Claude
2. Копирай **целия текст** на този файл и го постави като първо съобщение
   (или дай линк към суровия файл на GitHub: `https://raw.githubusercontent.com/iamyordanbg/maritime-tests/main/NEXT_SESSION_PROMPT.md` — Claude може да го прочете с `web_fetch`, ако линкът вече се е появявал в разговора)
3. **Дай свеж GitHub Personal Access Token** в съобщението си (виж по-долу защо не е записан тук)

**Защо GitHub token-ът НЕ е записан в този файл:** Token-ът е чувствителна тайна (API ключ) — да се запише в git repo файл е точно нарушението, описано в audit checklist точка #2 ("Sensitive Data Exposure — Токени, ENV променливи, Пароли в кода"). Ако бъде компрометиран някога записан token, всеки с достъп до repo-то (дори readonly) би имал пълен контрол над GitHub акаунта. Затова: **при всяка нова сесия, дай token-а устно/в съобщението**, никога в файл, който се комитва.

Работим върху **maritime-tests** — Flask/Python SaaS платформа за морски изпити (maradtest.com).

**Репо:** https://github.com/iamyordanbg/maritime-tests
**Stack:** Flask, SQLAlchemy, PostgreSQL, Tailwind CSS, деплой на Railway
**Production URL:** https://web-production-ca6b6.up.railway.app

---

## АРХИТЕКТУРНИ ПРАВИЛА (задължителни, без изключения)

1. **Нова JS логика → `app/static/js/`** като отделен файл, зареден с `<script src="...">`. **Никога** нова JS логика inline в `.html` файл.
2. **Бизнес логика → `app/services/`** — route функциите само приемат заявка, викат services/, връщат отговор.
3. **DB логика → `app/models/`** — структура на данните + прости методи, работещи с точно тези данни.
4. **Routing → `app/routes/`** — само HTTP handling, не сложна бизнес логика вътре.
5. **Права/роли → `app/permissions/`** — единствен източник на истина за "има ли право потребителят X".
6. **Максимум 500-800 реда на файл** — сигнал за смесени отговорности, не произволно число.
7. **Преди да дадеш код — тествай за syntax errors** (Jinja parse + `node --check` за JS). Винаги реален end-to-end тест, не само syntax проверка, преди да твърдиш "готово".
8. **Директорията на файла винаги се изписва** преди промяна.

## ПЪЛНОТО ЦЕЛЕВО ДЪРВО НА ПРОЕКТА

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
│   │   ├── signal.py
│   │   └── snapshot.py
│   │
│   ├── routes/
│   │   ├── auth.py
│   │   ├── dashboard.py
│   │   ├── admin.py
│   │   ├── tests.py
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
│   ├── repositories/
│   │   ├── user_repo.py
│   │   ├── test_repo.py
│   │   ├── result_repo.py
│   │   ├── ticket_repo.py
│   │   └── billing_repo.py
│   │
│   ├── middleware/
│   │   ├── auth.py
│   │   ├── rate_limit.py
│   │   ├── logging.py
│   │   └── security.py
│   │
│   ├── tasks/
│   │   ├── email_tasks.py
│   │   ├── billing_tasks.py
│   │   └── cleanup.py
│   │
│   ├── permissions/
│   │   ├── roles.py
│   │   ├── permissions.py
│   │   └── decorators.py
│   │
│   ├── auth/
│   │   ├── users.py
│   │   ├── login.py
│   │   ├── register.py
│   │   ├── reset.py
│   │   └── tokens.py
│   │
│   ├── notifications/
│   │   ├── email.py
│   │   ├── sms.py
│   │   └── push.py
│   │
│   ├── audit/
│   │   ├── logger.py
│   │   ├── events.py
│   │   └── admin_log.py
│   │
│   ├── api/
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── routes.py
│   │       └── schemas.py
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── output.css
│   │   ├── js/
│   │   │   ├── admin_users.js
│   │   │   ├── dashboard.js
│   │   │   ├── sidebar.js
│   │   │   ├── library.js
│   │   │   └── billing.js
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
│       │   └── simulator.html
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
│   │   ├── test_models.py
│   │   └── test_services.py
│   ├── integration/
│   │   ├── test_auth.py
│   │   └── test_billing.py
│   └── conftest.py
│
├── migrations/
│   ├── versions/
│   ├── env.py
│   └── alembic.ini
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── config.py
├── run.py
├── requirements.txt
├── .env.example
├── Procfile
└── railway.toml
```

**Забележка:** повечето от изброените директории (`repositories/`, `middleware/`, `tasks/`, `auth/`, `notifications/`, `audit/`, `api/`) вече съществуват физически в repo-то, но само като **скелети** — по един празен `__init__.py` всеки, никога населени с реален код. `deploy.yml` вече е **изтрит** (беше празен, никога нужен — Railway деплойва отделно). Активно използваните в момента: `routes/`, `services/`, `models/`, `permissions/`, `static/js/`, `templates/`.

---

## CI/CD workflow — СТРИКТНО СПАЗВАНЕ

```
1. Claude създава branch (git checkout -b тип/описание)
2. Claude прави промените, тества локално (pytest + syntax checks)
3. Claude push-ва branch-а
4. Claude отваря Pull Request (през GitHub API, token е наличен в git remote)
5. CI (GitHub Actions, .github/workflows/ci.yml) автоматично пуска 59 pytest теста + Jinja/JS syntax проверки
6. Railway PR Environments автоматично прави live preview (URL: web-<branch-name>.up.railway.app)
7. Claude СПИРА тук — казва "PR #X готов, CI зелено, preview линк: ..."
8. ПОТРЕБИТЕЛЯТ преглежда, и ТОЙ/ТЯ решава кога да merge-не
```

**КРИТИЧНО ПРАВИЛО:** Claude **НИКОГА** не мерджва PR сам, без изрична команда от потребителя ("мерджвай", "качвай на продакшан" и подобни). CD (реалният деплой) е **изцяло** решение на потребителя. Ако потребителят каже "тествай прехвърлянето" — това НЕ Е разрешение за merge, само за отваряне на PR + preview.

**Branch protection на `main`:** В момента `enforce_admins: false`, `required_pull_request_reviews: null` — облекчено съзнателно, за да не пречи на дребни housekeeping промени. За СЕРИОЗНИ промени (бизнес логика), Claude доброволно следва branch→PR→CI дисциплината, дори без технически required protection.

**Известен bug/gotcha:** ако PR е бил отворен ПРЕДИ Railway PR Environments да е бил включен, Railway няма да го "хване" дори с нов push — трябва да се затвори и преотвори PR-а.

**GitHub token:** има `repo` scope, НЯМА `workflow` scope — промени в `.github/workflows/*.yml` изискват или нов token, или потребителят ги качва ръчно през GitHub уеб интерфейса.

---

## ТЕКУЩ ПРОГРЕС (към края на предната сесия)

### JS Extraction — Фаза 1 (механично местене, нисък риск)
- ✅ `library.html`: 897 → 285 реда (`app/static/js/library.js`, 615 реда)
- ✅ `user_sidebar.html`: 1822 → 849 реда (`app/static/js/sidebar.js`, 975 реда) — **merge-нато в production**
- ✅ `base.html`: 1248 → 576 реда (`app/static/js/base.js`, 652 реда) — **merge-нато в production**
- ⏳ ОСТАВАТ: `simulator.html` (~727 реда JS), `test.html` (~553 реда), `landing.html`, `admin/tests.html`, `admin_sidebar.html` (~490 реда), и по-малките темплейти

### CI/CD инфраструктура
- ✅ `.github/workflows/ci.yml` — реален, работещ (59 pytest теста + Jinja/JS syntax проверки)
- ✅ `.github/workflows/deploy.yml` — изтрит (беше празен placeholder, Railway деплойва отделно, никога не е бил нужен)
- ✅ Railway PR Environments — активирани и потвърдено работещи (base environment: production)
- ✅ `DATABASE_URL` поправен да е динамична референция (`${{Postgres.DATABASE_URL}}`) вместо фиксиран текст — важно за PR среди

### Тестове (pytest, tests/)
- 55 passed, 4 skipped (TESTING_MODE-свързани, легитимно)
- Поправени 8 остарели/бъгови теста тази сесия (виж git history за детайли)

### Известни, все още НЕ поправени архитектурни нарушения
- `app/routes/dashboard.py`: **2151 реда** (2.7x над лимита) — съдържа бизнес логика (напр. директно `GoldGrant()` създаване), която трябва да е в `services/`
- `app/routes/admin.py`: **1368 реда** (1.7x над лимита)
- `user_can_access_test()` дефинирана НА ДВЕ места (`dashboard.py` И `permissions/roles.py`) — route-ът ползва локалната версия, `permissions/roles.py` версията е практически неизползвана — трябва консолидация

### Отворени PR-ове (проверявай текущия статус при започване на нова сесия!)
Провери през: `curl -s -H "Authorization: token <TOKEN>" "https://api.github.com/repos/iamyordanbg/maritime-tests/pulls?state=open"`

---

## MARADTEST AUDIT CHECKLIST — стратегическа категоризация

Пълният чеклист от потребителя има 20 категории. Категоризирани по реална изпълнимост:

**Група А (директно изпълними от Claude, код-ниво):** #1 Грешки в кода, #3 Мъртъв код, #7 Jinja архитектура, #8 Конзистентност, #11 Database Audit, #12 Auth/Authorization, #13 API Audit, #15 SaaS Logic, #16 Exam Engine, #18 Production Readiness

**Група Б (частично, изисква browser tooling който Claude няма директно):** #2 Сигурност (код-ниво да, penetration test не), #5 Производителност (код анализ да, реални Lighthouse метрики не), #9 Mobile/Responsive (CSS преглед да, реални устройства не), #19 Lighthouse Audit

**Група В (извън обхват, изисква други хора/инструменти):** #4 SEO (**ВАЖНО УТОЧНЕНИЕ**: не буквална Google indexing проверка — искаме **архитектурата да е SEO-friendly by design**: semantic HTML, мета тагове инфраструктура, sitemap.xml готовност, structured data skeleton — това Е изпълнимо от Claude като код-ниво архитектурна работа), #6 Accessibility (ARIA код преглед да, реален screen reader тест не), #10 Browser Compatibility, #14 Logging/Monitoring (логика да, реален Sentry/Datadog setup изисква потребителски акаунти), #17 GDPR (правен преглед, не технически), #20 Business/UX (код-ниво "работят ли линковете" да, реално UX тестване не)

### Предложен ред напред (от предната сесия, за потвърждение)
1. Довърши JS extraction (Фаза 1, остатъка от файловете)
2. Систематичен Group A audit — точка по точка
3. SEO архитектурна работа (Група В, #4, преформулирано като изпълнимо)
4. Консолидация на дублирана permissions логика
5. Най-рисково последно: местене на бизнес логика от routes/ → services/ (спирай за потвърждение на ВСЯКА отделна функция, не генерално)

---

## ОБНОВЛЕНИЕ (края на предходната сесия) — прочети преди да продължиш

### Отворени PR-ове, чакащи потребителя (провери актуалния статус при старт)
- **PR #7** — handoff документ (този файл) — чака merge
- **PR #8** — премахване на излишен "Mark as Custom Promo" бутон — чака merge
- **PR #10** — **СЪДЪРЖА И ЗАМЕСТВА #9** — 2 бъг фикса накуп (Excel image mapping + Delete test FK order) — чака merge. **#9 е технически излишен** (съдържанието му е включено в #10), можеш да го затвориш при merge на #10.

### Нови критични уроци за Railway PR Environments
1. **Ако редактираш variable в СЪЩЕСТВУВАЩА PR среда, промяната не се прилага надеждно** — референции (`${{Postgres.DATABASE_URL}}`) "замръзват" към стойността от момента на клониране. **Единственият надежден фикс**: затвори PR-а и го отвори наново (нов номер, ново чисто клониране). Направено успешно 3 пъти тази сесия (PR1→4, PR6→7, PR5→8).
2. **`DATABASE_URL` в production `web` услугата трябва да е `${{Postgres.DATABASE_URL}}`** (референция), не фиксиран текст — вече поправено. Всяка **нова** PR среда, отворена ОТТУК НАТАТЪК, наследява това правилно автоматично.
3. **Всяка PR среда си има собствена, ИЗОЛИРАНА, ПРАЗНА база данни** — тестови данни, качени в една PR среда (напр. тестове с Excel/снимки), НЕ се пренасят в друга PR среда. Потребителят намери това за силно неудобно за дебъгване.
4. **ЧАКАЩА ЗАДАЧА от потребителя**: иска **обща, постоянна тестова Postgres база**, споделена между ВСИЧКИ PR среди (не production, не изолирани клонинги) — за да не се качват тестови данни наново всеки път. Изисква: (а) потребителят да създаде отделна "Postgres-Testing" услуга в Railway ръчно + Shared Variable `TESTING_DATABASE_URL`, (б) Claude да промени `config.py` да ползва тази стойност за PR/dev среди вместо auto-clone-натата. **Стъпка (а) НЕ Е направена от потребителя още** — провери в началото на сесията дали е готова, преди да пишеш код за (б).

### Нови бъгове, намерени и поправени тази сесия
- **Excel image mapping off-by-one** (`app/routes/admin.py`, `parse_xls_colors()`) — снимките при `.xlsx` импорт се закачаха към ПРЕДИШНИЯ въпрос заради двойно изместване в изчислението на реда (`+1` после `-1`). Поправено (PR #9/#10).
- **Delete test 500 грешка** (`app/routes/admin.py`, `delete_test()`) — гърмеше за всеки тест с прикачени снимки (`TestImage` записи), защото родителският `Test` ред се трие ПРЕДИ децата (`TestImage`) — нарушава foreign key на production Postgres (SQLite dev среда не налага FK по подразбиране, маскирайки бъга). Поправено (PR #10) — децата се трият първи.
- **`.xls` (стар бинарен формат) НЯМА поддръжка за извличане на снимки изобщо** — само `.xlsx` (нов формат, `openpyxl`) има тази логика. `xlrd` (за `.xls`) няма надежден API за това. Потребителят трябва да конвертира `.xls` → `.xlsx` през Excel (**File → Save As**, не просто преименуване на разширението - преименуването САМО не конвертира съдържанието).

### GitHub token — ВАЖНО, прочети преди да питаш потребителя
Token-ът **никога** не се записва в git-проследяван файл (виж обяснението в горната секция "КАК ДА ПОЛЗВАШ ТОЗИ ФАЙЛ"). При началото на всяка сесия, **директно попитай потребителя** за свеж token, ако ти трябва GitHub API достъп — не приемай, че вече го имаш от контекста, освен ако не е буквално в текущото съобщение.



- **TESTING_MODE = True** в `app/services/plans.py` (~ред 25-30) — НАРОЧНО, съкращава всички план продължителности за бързо тестване. НЕ променяй без изрично потвърждение.
- **Кодова формула** (`app/utils/codes.py`, `subscription_code()`): BG + alternating_code(id × 3 + type_residue), с 3-way disambiguation (`plan`=0, `gold`=1, `promo`=2) — гарантирано без колизии между PlanGrant/GoldGrant/PromoCode.
- **PromoCode.is_custom** флаг разграничава ръчно генерирани "Custom/Promo" кодове от автоматичния 10-пакет "Gold" — показва се различно в UI.
- **GoldGrant.promo_code** пази РЕАЛНИЯ активиран код — никога не преизчислявай нов код от `GoldGrant.id`, винаги чети `grant.promo_code` директно.
- Тестови credentials в PR/dev среди: `test@maritime.bg` / `test123` (обикновен), `admin@maritime.bg` / `admin123` (admin) — автоматично създадени при database seed.

---

## ТОН И РАБОТЕН СТИЛ (по изричен ред на потребителя)

- Потребителят е технически, но не е разработчик — обяснявай **максимално просто**, стъпка по стъпка, без излишен жаргон.
- **Винаги** реален тест (не само твърдение "готово") преди да кажеш "готово" — потребителят е хващал многократно случаи на неверни твърдения тази сесия.
- Ако потребителят звучи фрустриран/груб — не се отбранявай, признавай грешки директно, продължавай напред без излишни извинения.
- Когато нещо не е ясно (напр. "кое точно реагира") — задавай **конкретни**, затворени въпроси (ask_user_input_v0), не отваряй нови несигурности.


