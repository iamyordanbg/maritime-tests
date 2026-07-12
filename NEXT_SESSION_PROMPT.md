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
1а. **ОБЩО ПРАВИЛО ЗА ВСЕКИ ТИП КОД (JS, CSS, Python, Jinja макроси) — без изключения:** щом един и същ блок логика/стил/код се появи на **2-ри** файл (не само 3-ти или повече), това е сигнал СТОП — извади го в споделен файл/модул/функция ПРЕДИ да продължиш, вместо copy-paste "за сега, ще го оправя после". "После" не идва самò - точно така се стигна до 3 почти идентични копия на Reading Settings логиката (JS) и до дублирани theme CSS блокове в 3 темплейта тази сесия, преди изобщо да бъдат забелязани.
   - **Проверка преди да твърдиш "готово" за нова логика, засягаща 2+ страници:** `grep -c "уникален_фрагмент_от_блока" app/templates/*/*.html` (или еквивалент за JS/Python) — ако резултатът показва 2+ файла с почти идентичен блок, спри и extract-вай, не продължавай да пишеш 3-ти дублат.
   - Важи еднакво за: JS логика (`app/static/js/`), споделени CSS theme/компонентни стилове (`app/static/css/`), повтаряща се Python логика (`app/services/`), повтарящи се Jinja блокове (`{% macro %}` / `{% include %}`).
   - Причината не е естетика — дублиран код означава **N поправки** за 1 бъг вместо 1, точно каквото се случи многократно тази сесия (reference-before-declaration грешката, `0 || -1` falsy проблема) преди да бъдат обединени.
   - **ФОРМАЛЕН ПРИНЦИП (изрично поискан от потребителя):** `.html` темплейт файловете трябва да **ВИКАТ** логика (JS чрез `<script src>`, CSS чрез `<link rel="stylesheet">`), никога да не я **СЪДЪРЖАТ** директно. Изключения, позволени да останат inline: (а) малки Jinja data-инжекции (`window.X_DATA = {{ ... }}`) — носят сървърни данни, не логика; (б) уникално, наистина еднократно CSS/JS, което не се повтаря на 2-ри файл. Всичко друго → отделен файл.
   - **Статус:** CSS theme override-ите (Light/Sepia/Ink) бяха extract-нати в `app/static/css/reading-theme.css`, зареден с `<link>` в трите темплейта (`simulator.html`/`test.html`/`result_review.html`) — вижте "Reading Settings" секцията по-долу за пълни детайли. `app/static/css/output.css` (компилиран Tailwind) остава отделно, автоматично генериран, не пипан ръчно.
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
- ✅ `simulator.html`: 1153 → 503 реда (`app/static/js/simulator.js`, 620 реда след обединяването на reading-prefs логиката) — направено в PR #13 (виж бележката за merge conflict по-долу)
- ✅ `test.html`: 846 → 305 реда (`app/static/js/test.js`, 564 реда) — направено в PR #13, **все още НЕ Е merge-нато в main**
- ⏳ ОСТАВАТ: `landing.html`, `admin/tests.html`, `admin_sidebar.html` (~490 реда), и по-малките темплейти
- ✅ Нов файл извлечен допълнително: `app/static/js/result_review.js` (Reading Settings логика за `/result/<id>`), също в PR #13

### CI/CD инфраструктура
- ✅ `.github/workflows/ci.yml` — реален, работещ (59 pytest теста + Jinja/JS syntax проверки)
- ✅ `.github/workflows/deploy.yml` — изтрит (беше празен placeholder, Railway деплойва отделно, никога не е бил нужен)
- ✅ Railway PR Environments — активирани и потвърдено работещи (base environment: production)
- ✅ `DATABASE_URL` поправен да е динамична референция (`${{Postgres.DATABASE_URL}}`) вместо фиксиран текст — важно за PR среди

### Тестове (pytest, tests/)
- 55 passed, 4 skipped (TESTING_MODE-свързани, легитимно)
- Поправени 8 остарели/бъгови теста тази сесия (виж git history за детайли)

### Известни, все още НЕ поправени архитектурни нарушения
- `app/routes/dashboard.py`: **2169 реда** (2.7x над лимита) — съдържа бизнес логика (напр. директно `GoldGrant()` създаване), която трябва да е в `services/`
- `app/routes/admin.py`: **1365 реда** (1.7x над лимита)
- `user_can_access_test()` дефинирана НА ДВЕ места (`dashboard.py` И `permissions/roles.py`) — route-ът ползва локалната версия, `permissions/roles.py` версията е практически неизползвана — трябва консолидация
- `app/static/js/sidebar.js`: **977 реда** (над 800 лимита от правило #6) — от предишна сесия (PR merge-нат отдавна), никога маркирано като нарушение до тази сесия. Не разбит все още.
- `app/static/js/base.js`: **680 реда** — под лимита технически, но близо до горната граница, следи при следваща промяна.

### PromoGrant разделен от GoldGrant — МАЩАБЕН рефакторинг (по изрично, многократно искане на потребителя)
Преди: активиране на Custom Promo код (`PromoCode.is_custom=True`, ръчно генериран от admin) създаваше `GoldGrant` ред — **същата** таблица като стандартните Gold 10-пакет кодове (Stripe покупка). Технически работеше (`is_custom` флагът разграничаваше типа само за DISPLAY label), но потребителят настоя изрично Promo да има **отделна** таблица/инфраструктура от Gold.

**Нов модел:** `app/models/promo_grant.py` (`PromoGrant`) — огледална структура на `GoldGrant` (същите полета/методи `test_id_list()`/`is_active()`/`in_grace()`), напълно отделна таблица `promo_grant`.

**13 файла обновени** (картографирани систематично преди да се започне):
- `app/models/promo_grant.py` (нов), `app/models/__init__.py` (регистрация)
- `app/models/user.py` — нов `active_promo_grants()` метод, `has_active_plan()`/`effective_plan_label()`/`effective_days_left()` включват го
- `app/routes/dashboard.py` — 2 grant creation path-а (`library_select()`), `has_active_gold` проверка, `gold_cards` изграждане (обединява GoldGrant+PromoGrant, сортирани), `needed_test_ids`, `/api/my-usage` route
- `app/routes/activate.py` — 3-тия (отделен) activation flow, `_user_active_department()` helper
- `app/permissions/roles.py` — `user_can_access_test()` (дублираната версия)
- `app/utils/grants.py` — `find_result_grant()` (нов `promo_cache` параметър), `find_active_grant_for_test()` (**критична** — тук се решава реален достъп/квота преди решаване на тест)
- `app/utils/grant_cache.py` — `fetch_all_grants()` вече връща 3-тройка `(gold, promo, plan)`, не 2
- `app/routes/admin.py` — admin dashboard recent_results + search функционалност

**⚠️ КРИТИЧЕН БЪГ, открит и поправен по пътя** (не просто display проблем): `find_active_grant_for_test()` и `User.active_gold_grants()`/`has_active_plan()` проверяваха **само** `GoldGrant` — Promo потребители биха били **реално заключени** от купения си тест (`test_access_lock()` третира "няма намерен grant" като LOCKED), въпреки успешна активация. Открито и поправено чрез реален end-to-end тест: `GET /test/<id>` за Promo потребител → статус `200` (не `302` redirect към library).

**Тествано реално** на всяка стъпка: активиране на Custom Promo → директна DB проверка (`PromoGrant.count()==1`, `GoldGrant.count()==0`); регресионен тест за стандартен Gold (обратното); dashboard картата показва `Promo` label коректно; `/api/my-usage` връща правилен JSON; **критичният** реален достъп тест (`GET /test/<id>` → 200, не redirect).

### ⚠️ Postgres-Testing базата е БИЛА ПРАЗНА (открито в тази сесия, необяснена причина)
Към края на тази сесия, `test_result` таблицата в production `Postgres-Testing` показа **0 записа**, въпреки часове тестова активност (регистрации, решени тестове). Проверих задълбочено: (а) връзката е потвърдена правилна (`tokaido.proxy.rlwy.net:11879` в deployment логовете), (б) единствената функция, трияща резултати (`auto_delete_expired_results()`), има твърдо 30-дневно ограничение — математически не може да е изтрила данни отпреди часове, (в) PostgreSQL checkpoint логовете изглеждат напълно нормални, без следа от срив/рестарт. Причината остава **необяснена** — вероятно инфраструктурен проблем в Railway (volume/service recreate), не код бъг. Следваща сесия: провери отново дали данните са се появили наново, или трябва ръчно пресъздаване на тестови акаунти/резултати.

### Отворени PR-ове (проверявай текущия статус при започване на нова сесия!)
Провери през: `curl -s -H "Authorization: token <TOKEN>" "https://api.github.com/repos/iamyordanbg/maritime-tests/pulls?state=open"`

**Статус към края на тази сесия:**
- ✅ PR #7, #8, #9, #10, #11, #12 — всичките merge-нати в main
- ✅ PR #13 — отворен, merge conflict-ът разрешен (виж подробния раздел "PR #13 MERGE CONFLICT" по-долу), `mergeable: True` в GitHub API, чака CI + потребителско решение за merge

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

## ОБНОВЛЕНИЕ (края на тази сесия) — прочети преди да продължиш

### ✅ PR #13 MERGE CONFLICT — РАЗРЕШЕН
`refactor/test-html-js-extraction` (PR #13) имаше `Merge conflicts` статус в GitHub. Причина: PR #11 (`TESTING_DATABASE_URL`) и PR #12 (оригинален `simulator.js` extraction, гола версия) бяха merge-нати в `main` успоредно, докато PR #13 branch-ът самостоятелно съдържаше същите промени (branch-ът тръгна ПРЕДИ тези merge-и).

**Решение, приложено и потвърдено:** проверено реално (`git diff`), че `main`-ината версия на `simulator.js`/`simulator.html` беше **byte-identical** с общата base точка (commit `cefbbbf`), без нищо допълнително добавено след PR #12 merge-а. Значи PR #13 версията (много по-развита) е строг superset — merge-нат `main` в branch-а, конфликтът разрешен в полза на PR #13 версията (`git checkout --ours`), потвърдено с `mergeable: True` през GitHub API след push. **PR #13 вече е готов за merge**, чака само CI зелена светлина + потребителско решение.

### PR #13 — какво съдържа (обширна UI/UX работа върху test-решаването)
- `test.html` JS extraction (846→305 реда)
- `TESTING_DATABASE_URL` поправка: **буквален connection string** (не `${{Postgres-Testing.DATABASE_URL}}` референция!) — виж следващата секция защо
- Реални бъгове поправени: Gold код с `topics_allowed=1` винаги искаше 2-ри тест; dashboard картите винаги показваха "Gold" дори за Custom Promo; admin delete бутон не работеше за активирани промокодове; `border-red-400`/`bg-red-500/20` изобщо не бяха компилирани в Tailwind CSS (грешен отговор не се виждаше червен реално)
- Ново: "Reading Settings" панел (Question/Answer Font Size, Highlight Intensity, Background theme, Font family+Bold) добавен и в `/result/<id>` (`result_review.js`) и History (link към review) — преди съществуваше само в Test/Simulator
- Нова **4-та тема "Ink"** (книжен режим, без рамки на въпрос/отговор, топъл хартиен фон) — само в симулатора засега, не пренесена в test.html/result_review.html
- Нови слайдери: **Background Brightness** (CSS `filter:brightness()`, 0.7-1.3 range) и **Font Weight** (глобален, 300-900, override-ва Bold бутоните само при реално местене от default 5)
- Симулаторов `#fullReview` (вграден review екран) синхронизиран визуално с решаването — border/background/font-size настройки вече важат и там
- Cache-busting механизъм: нова `static_url()` Jinja global функция (`app/__init__.py`) — добавя `?v=<mtime>` към JS/CSS адреси, за да не сервира браузърът стара кеширана версия след всеки push (30-дневен `SEND_FILE_MAX_AGE_DEFAULT` важеше и за JS/CSS, не само снимки)

### ⚠️ КРИТИЧЕН УРОК: Tailwind CSS е ПРЕДВАРИТЕЛНО компилиран, не runtime JIT
`app/static/css/output.css` съдържа **само** utility класовете, които вече са били използвани някъде в кода **към момента на build-а**. Ако напишеш нов Tailwind клас (напр. `border-emerald-500/15`), който никога не е бил използван преди — той **просто не работи** визуално (браузърът игнорира непознат клас, показва default/безцветен вид), **без грешка, без предупреждение**. Случи се 2 пъти тази сесия (`/15` opacity вариант, после `border-red-400`/`bg-red-500/20` се оказаха изобщо никога компилирани, независимо от този конкретен session).

**Задължителна проверка преди да ползваш НОВ Tailwind utility клас:**
```bash
grep -o '\.CLASS-NAME{[^}]*}' app/static/css/output.css
# escape-вай / като \/ за opacity варианти, напр. border-emerald-500\/20
```
Ако не излезе резултат — класът НЕ Е компилиран. Или (а) намери вече компилиран близък вариант, или (б) ползвай inline `style="border-color:rgba(...)"` вместо Tailwind клас (по-сигурно, нулева зависимост от build-а).

### Railway PR Environments — уроци, все още в сила
1. **Ако редактираш variable в СЪЩЕСТВУВАЩА PR среда, промяната не се прилага надеждно** — референции "замръзват" към стойността от момента на клониране. Единственият надежден фикс: затвори PR-а и го отвори наново (ново чисто клониране).
2. **Всяка PR среда си има собствена, ИЗОЛИРАНА база данни** по подразбиране (auto-clone на production) — освен `TESTING_DATABASE_URL` override-а (виж по-долу), който е точно решението на този проблем.
3. Ако PR е бил отворен ПРЕДИ Railway PR Environments да е бил включен, Railway няма да го "хване" дори с нов push — трябва затваряне+преотваряне.

### TESTING_DATABASE_URL — статус: РЕШЕНО (предната "чакаща задача" вече не важи)
Предната сесия остави тази задача чакаща потребителя. Вече е напълно завършено:
1. `Postgres-Testing` услуга създадена в production Railway environment
2. `TESTING_DATABASE_URL` в production `web` service variables — **важно**: стойността е **буквален connection string** (`postgresql://...@tokaido.proxy.rlwy.net:PORT/railway`), **НЕ** `${{Postgres-Testing.DATABASE_URL}}` референция. Причина: Railway клонира ВСИЧКИ services (включително `Postgres-Testing`) при отваряне на нова PR среда — референция би сочила към ЛОКАЛНИЯ клонинг на всяка PR среда (различна база всеки път), не към реалната споделена. Буквалният текст гарантира всяка PR среда сочи към ЕДНА И СЪЩА физическа база.
3. `config.py` `_resolve_database_url()`: ако `RAILWAY_ENVIRONMENT_NAME != 'production'` И `TESTING_DATABASE_URL` е налична → ползва нея; иначе стар `DATABASE_URL` flow (production непроменено)
4. Ограничение, останало в сила: само **нови** PR среди (отворени СЛЕД тази настройка в production) наследяват автоматично — стари отворени PR-и (напр. pr-7/8/10 preview-та) трябва ръчно update на variable-а или затваряне+преотваряне

### Нови бъгове, намерени и поправени тази сесия (PR #13)
- **Gold код с `topics_allowed=1` винаги искаше избор на 2-ри тест** (`dashboard.py`, `library_select()`) — проверката за "само 1 департамент" идваше СЛЕД избора на 2-ри тест, вместо да спре искането изобщо. Поправено + реален end-to-end тест (Flask test_client).
- **Dashboard картите винаги показваха "Gold"** дори за Custom Promo кодове (`is_custom=True`) — `plan_label` беше твърдо закодиран, вместо да проверява `is_custom` (същата проверка вече съществуваше другаде във файла, липсваше тук).
- **Admin "Delete" бутон изчезваше за активирани промокодове** (показваше "Locked" вместо бутон) — backend-ът вече напълно поддържаше изтриване на активирани кодове, ограничението беше само фронтенд UI.
- **`border-red-400`/`bg-red-500/20` изобщо не бяха компилирани** в Tailwind CSS — грешният избран отговор при Test/Mix/Mistakes вероятно никога не се е виждал реално червен. Заменени с `rose-*` варианти (потвърдено компилирани).
- **`applyPrefs()` в `result_review.js` хвърляше `ReferenceError`** (`rowOpacity` използвана преди дефиницията си, `const` temporal dead zone) — цялата функция гърмеше по средата, инжектираният CSS никога не стигаше до браузъра.
- **`goToFirstMistake()` cursor логика** — `window._reviewMistakeCursor || -1` третираше `0` като falsy (JS gotcha), курсорът никога не напредваше отвъд 1-вата грешка. Explicit `undefined` проверка вместо `||`.
- **CSS селектор `:last-child` чупеше се при икона след текста** — верен/грешен отговор в симулатора изглеждаше "смален" спрямо неутралните редове, защото `.opt-label span:last-child` вече не хващаше текстовия span (иконата ставаше last-child). Поправено с директен `.opt-text` клас.
- **Header ставаше `transparent` в Ink темата** — съдържанието "прозираше" през sticky хедъра при скрол. Поправено с плътен фон, съвпадащ с page background.

### GitHub token — ВАЖНО, прочети преди да питаш потребителя
Token-ът **никога** не се записва в git-проследяван файл (виж обяснението в горната секция "КАК ДА ПОЛЗВАШ ТОЗИ ФАЙЛ"). При началото на всяка сесия, **директно попитай потребителя** за свеж token, ако ти трябва GitHub API достъп — не приемай, че вече го имаш от контекста, освен ако не е буквално в текущото съобщение.

### Reading Settings — обединени в общ модул (задачата от края на сесията е решена)
`app/static/js/reading-prefs.js` — единствен, споделен модул, замести 3-те почти дублирани копия в `simulator.js`/`test.js`/`result_review.js`. Работи и с двата established DOM patern-а в проекта едновременно (simulator: `#simContent`/`#qBox`/`#answersContainer`; list: `#mainContent`/`[id^="qbox_"]`/`.opt-label`) — несъвпадащи CSS селектори са безобидни no-op на страници без съответните елементи.

Page-specific довършителни действия минават през `window.onPrefsApplied(prefs)` hook, дефиниран във всеки page-specific файл **преди** `reading-prefs.js` се зарежда — редът на `<script>` таговете в HTML-а има значение (page-specific файл първи, `reading-prefs.js` последен).

**Резултат:** Ink тема + Background Brightness + Font Weight слайдерите вече съществуват навсякъде (Simulator, Test/Mix/Mistakes, `/result/<id>`), не само в симулатора — предната "известна недовършена задача" е решена.

**Размери след разделянето:** `simulator.js` 620 реда, `test.js` 424 реда, `result_review.js` 33 реда (нарасна с goToFirstMistake()), `reading-prefs.js` 266 реда — всичките под 500-800 лимита (правило #6). Темплейтите след и CSS extraction-а: `simulator.html` 335 реда (от 1153 оригинално), `test.html` 247 (от 846), `result_review.html` 199. Нов `app/static/css/reading-theme.css`: 190 реда.

### Известни, все още НЕ довършени задачи от UI/UX поправките в PR #13
- ✅ **РЕШЕНО**: CSS theme override-ите (Light/Sepia/Ink) бяха дублирани в 3 темплейта — вече extract-нати в `app/static/css/reading-theme.css`. Anti-copy защитата (user-select:none) стана opt-in CSS клас (`.no-copy`), приложен на `simulator.html`/`test.html`, **умишлено НЕ** на `result_review.html` (read-only справка, потребителят трябва да може да копира собствения си резултат) — тази разлика съществуваше и преди extraction-а, пазена изрично.
- `history.html` все още **няма** директен Reading Settings панел (умишлено решение — History е таблица без question/answer съдържание; вместо панел, добавен е "Review" линк към `/result/<id>`, който вече има пълния панел)

### Други бележки (различни, все още валидни)
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


