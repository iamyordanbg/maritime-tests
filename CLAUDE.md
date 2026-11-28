# Продължение на работа по maritime-tests — Промпт за нов чат

## КАК ДА ПОЛЗВАШ ТОЗИ ФАЙЛ


**Проект:** maritime-tests — Flask/SQLAlchemy/PostgreSQL/Tailwind SaaS за морски изпити (maradtest.com)
**Repo:** https://github.com/iamyordanbg/maritime-tests
**Production (main, merge-нат код):** https://web-production-ca6b6.up.railway.app
**Текущ работен PR (не е merge-нат):** #16 → preview: https://web-maritime-tests-pr-16.up.railway.app

---

## АРХИТЕКТУРНИ ПРАВИЛА (задължителни, без изключения)

1. **JS → `app/static/js/`**, зареден с `<script src>`. Никога inline логика в `.html`.
   - **Събития:** никакви `onclick=`/`oninput=`/… атрибути. Ползва се `data-on-<event>='[["fn","arg"]]'`, изпълнявано от `app/static/js/ui-actions.js` (формат и токени — в коментара на файла). Jinja стойности се подават през `data-*` атрибути и токените `$data:key` / `$num:key`. Smoke тестът пада при inline `on*=`, `<style>` блок или inline скрипт, който не е чисто `window.X = …` инжекция.
2. **CSS → `app/static/css/`**, зареден с `<link rel="stylesheet">`. Никога нов `<style>` блок в `.html`. HTML файловете само **викат** JS/CSS, никога не ги **съдържат** — изключение само малки Jinja data-инжекции (`window.X = {{...}}`) и наистина еднократни (1 файл) inline стилове.
3. **Anti-duplication:** щом блок код/стил се появи на 2-ри файл → спри, extract-вай в общ модул. Не чакай 3-ти дублат. (Урок от сесия: 3 копия на Reading Settings логика + дублирани CSS теми доведоха до едни и същи бъгове, поправяни поотделно.)
4. **Бизнес логика → `app/services/`**, **DB → `app/models/`**, **Routing → `app/routes/`** (само HTTP handling), **Права → `app/permissions/`**.
5. **Макс 500-800 реда/файл** — сигнал за смесени отговорности.
6. **Винаги реален тест** (Jinja parse + `node --check` + функционален end-to-end), не само syntax проверка, преди "готово".
7. **Директорията на файла винаги се изписва** преди промяна която се прелага..
8. **Никакви hardcode-нати fallback стойности** (`|| 30`, `'No restriction'`, `|| 1` и т.н.) без изрично одобрение от потребителя. Ако поле няма стойност/не е приложимо — показва се честно `"N/A"` или подобно, никога измислена стойност по подразбиране, която може да заблуди (напр. Plan details попъп показваше `"30 days"`/`"No restriction"` за Basic/Plus планове, за които тези концепции изобщо не важат — създаваше грешно впечатление, че настройката реално се прилага). Единствен източник на истина за конфигурационни стойности на стандартни планове е `app/services/plans.py: PLANS` — никога hardcode другаде.
9. **Responsive layout за всички устройства** — всяка промяна (UI, текст, имейл, админ, landing) трябва да работи и да изглежда добре еднакво на телефон, таблет, лаптоп и десктоп, независимо от приемника. Позиционирането е интелигентно спрямо размера на екрана (flex/grid, `max-width`, медия заявки в CSS файловете — не фиксирани размери). Преди "готово" — функционален браузърен тест най-малко на 390px (телефон) и 1280px (десктоп); при промяна в оформлението и на 320px и 768px. Без хоризонтален скрол, без излизане на елементи извън контейнера им, тап цели поне ~36px.

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

---

## ЗАДАЧИ ЗА СЛЕД ПРЕХВЪРЛЯНЕТО НА САЙТА НА СОБСТВЕН ДОМЕЙН (maradtest.com)

**Оптимизация на зареждането на снимките към тестовете (R2)**

Проблем: снимките се зареждат със забавяне дори да са малки (само 3 снимки). Причина: сега се сервират от публичния адрес `pub-….r2.dev`, който Cloudflare дава само за тестване — няма кеширане през мрежата им и има ограничения за скорост.

Какво да се направи, когато `maradtest.com` е регистриран и добавен в Cloudflare (статус Active):
1. Cloudflare → R2 → bucket → Settings → **Custom Domains** → добави поддомейн, напр. `images.maradtest.com`.
2. В Railway (production, услуга `web`) смени само `R2_PUBLIC_URL` на `https://images.maradtest.com` и Deploy. Кодът не се пипа; в базата се пази само пътят (`tests/<id>/questions/<qid>.<fmt>`), затова вече качените снимки започват да се показват през новия адрес без ново качване.
3. Малка промяна в кода (по искане): `<link rel="preconnect">` към адреса на R2 в `test.html` / `simulator.html` / `result_review.html` и предварително зареждане на снимките в `test.js` (там е `loading="lazy"`; в `simulator.js` вече има `preloadImage`). Домейнът да не се hardcode-ва — взима се от конфигурацията (`R2_PUBLIC_URL`).
4. Провери: DevTools → Network → колоната Time на снимка (първо и второ зареждане), на телефон и десктоп.

**Снимки на новини/отзиви** (`app/utils/image_upload.py`) още се пишат на диска на сървъра (изчезват при нов деплой) — да се прехвърлят в R2 със същия домейн.

**Ключове и адреси при преместване на maradtest.com (напомняй при домейн миграцията)**

Тайните ключове НЕ се сменят само заради домейна — добавят се новите адреси там, където ключовете са вързани за адрес:
1. **Google OAuth** (Google Cloud → APIs & Services → Credentials → клиент „Maritime Tests Web“): добави `https://maradtest.com` в Authorised JavaScript origins и `https://maradtest.com/<callback пътя>` в Authorised redirect URIs. Старите адреси остават, докато сайтът работи и на двата.
2. **Cloudflare Turnstile** (widget `maritime-tests`, Invisible, site key започва с `0x4AAAAAADdfH`): добави `maradtest.com` в списъка с hostnames, иначе защитата от ботове ще дава грешка на новия адрес.
3. **Stripe**: смени webhook endpoint адреса на новия домейн (и в live режим, когато превключим от sandbox).
4. **Railway** (production, услуга `web`): `BASE_URL` → `https://maradtest.com`.
5. **Brevo**: ако изпращачът става `@maradtest.com`, добави и валидирай домейна (SPF/DKIM записи в Cloudflare DNS).
6. Провери на телефон и десктоп: вход с Google (инкогнито), регистрация с Turnstile и OTP имейл, плащане (sandbox).

---

## ОСТАВАЩА РАБОТА

**Фейсбук новини → сайта (автоматично от бизнес страницата)**

Решение, което чака потребителя: новината от Facebook да излиза в сайта **веднага**, или **с одобрение** от админа в админ панела? След отговора започва реализацията.

- Работи само с **Facebook страница (Page)**, не с личен профил (Meta не дава достъп до постове от личен профил).
- Потребителят прави приложението в Meta for Developers (тип Business), добавя разрешенията `pages_read_engagement` и `pages_read_user_content`, свързва страницата и генерира ключ за страницата. Claude му казва точните стъпки и точните имена на променливите за Railway (напр. `FB_PAGE_ID`, `FB_PAGE_TOKEN`). **Ключът никога не се пише в чата** — само в Railway.
- Не е потвърдено дали Meta изисква App Review / проверка на фирмата за собствена страница — проверява се при първата настройка. Преди кода — пак да се провери официалната документация на Meta (изискванията се променят).
- Какво прави кодът: периодично чете новите публикувани постове (филтрира `is_published`), създава новини с автор админа (аватар), копира снимките в R2 (адресите на снимките на Facebook изтичат; `full_picture` е най-много 720px — взима се по-голямата версия от `attachments`), не дублира (пази Facebook id на поста), не пипа вече съществуващите новини.
- Ще се тества реално едва когато има production среда и домейн; на PR 16 — само с тестови данни.
