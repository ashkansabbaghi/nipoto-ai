# پلن اجرایی MVP سرویس `nipoto-ai`

> بر پایه‌ی سند طراحی [AI-SERVICE.fa.md](AI-SERVICE.fa.md) (پیش‌نویس ۲). هر جا این پلن چیزی نگفته، حرف سند معتبر است.
> مجری: یک نفر با کمک Claude/Cursor. هر تسک خودکفاست و مستقیم قابل دادن به agent است.
> تاریخ: ۱۴۰۵/۰۶/۲۰ (2026-09-11). وضعیت هر تسک در جدول §۴ به‌روز می‌شود.

---

## ۰. زمینه

سند طراحی درست و کامل است، ولی محدوده‌اش در عمل «محصول کامل» است: ۱۰ تا ۱۴ هفته توسعه، ۴ تا ۵ ماه تقویمی، و مسیر بحرانی‌اش به تیم بک‌اند، تیم ویجت، فرانت staff و کارشناس‌ها گره خورده است.

هدف این پلن: **یک MVP قابل دمو و قابل اندازه‌گیری**، که بدون انتظار برای تیم‌های دیگر ساخته شود و برای تیم فنی و مدیرعامل ارائه شود. خروجی‌ها:

1. سرویس `nipoto-ai` با جستجو، حالت `draft`، و حالت `auto` در **سایه‌ی آفلاین**
2. صفحه‌ی دموی داخلی `/demo`
3. گزارش ارزیابی با عدد واقعی
4. اسلاید فنی HTML برای ارائه

---

## ۱. تغییرها نسبت به سند طراحی (تأییدشده)

| # | موضوع | در سند | در MVP |
|---|---|---|---|
| D1 | محدوده | فاز ۰ تا ۶ | فاز ۰ تا ۴، به‌علاوه‌ی سایه‌ی **آفلاین**. `auto` زنده (فاز ۵) و داده‌ی حساب و سفارش (فاز ۶) بعد از MVP |
| D2 | دوره‌ی سایه | ۳ تا ۴ هفته روی ترافیک زنده | اجرای batch خط لوله‌ی `auto` روی مکالمه‌های تستی، و امتیازدهی در `/demo` |
| D3 | داده‌ی تست | golden set از تیکت‌های واقعی | تولید نیمه‌خودکار با LLM از روی FAQ، به‌علاوه‌ی بازبینی دستی و ۳۰ مورد سخت دست‌نویس |
| D4 | embedding | `sentence-transformers` داخل اپ | **sidecar** (TEI، Infinity یا Ollama با `bge-m3`) با endpoint سازگار با OpenAI. اپ بدون torch می‌ماند. fallback: پیاده‌سازی درون‌اپ پشت همان interface |
| D5 | لغو در `draft` | `POST /cancel` | تولید به اتصال SSE گره می‌خورد و قطع اتصال یعنی لغو. `cancel` و reattach فقط برای `auto` زنده، یعنی بعد از MVP |
| D6 | UI | پنل staff (تیم فرانت) | صفحه‌ی `/demo` در خود سرویس (فقط dev). مرجع پیاده‌سازی برای تیم staff هم هست |
| D7 | قرارداد بک‌اند | جدول §۷.۲ | فایل `contracts/main-backend.openapi.yaml` در هفته‌ی اول به تیم بک‌اند تحویل می‌شود |
| D8 | عقب افتاده | — | rerank، جستجوی ترکیبی، `kb/sync` و cron، endpoint `kb/gaps` (جدول ثبت می‌شود)، circuit breaker، Redis، webhook |
| D9 | `auto_mode` | `off` / `shadow` / `live` | فقط `off` و `shadow`. مقدار `live` خطای `not_implemented` می‌دهد |
| D10 | نرمال‌سازی | پایه‌ی `hazm` | پیاده‌سازی مستقل با جدول §۹.۳، چون `hazm` وابستگی‌های سنگین دارد. `hazm` فقط اگر نیم‌فاصله کافی نبود |

---

## ۲. نقاط عطف

| هفته (تقریبی) | خروجی قابل نمایش |
|---|---|
| ۱ | اسکلت، auth، DB، `FakeMainBackend`؛ قرارداد به تیم بک‌اند رسیده |
| ۳ | جستجو کار می‌کند؛ عدد hit@5 و MRR در دست است |
| ۴ تا ۵ | پیش‌نویس جریانی در `/demo`: **اولین ارزش واقعی.** ارائه‌ی میانی به تیم فنی ممکن است |
| ۶ تا ۷ | `auto` در سایه‌ی آفلاین، گزارش ارزیابی و اسلاید. **ارائه به مدیرعامل** |

برآورد محافظه‌کارانه برای یک نفر است. با agent احتمالاً تسک‌های M1 و M4 سریع‌تر پیش می‌روند.

---

## ۳. نحوه‌ی کار با agent

برای هر تسک، این prompt را به Claude یا Cursor بدهید:

```
CLAUDE.md و بخش‌های ذکرشده از AI-SERVICE.fa.md را بخوان.
فقط تسک <ID> از MVP-PLAN.fa.md را پیاده کن؛ به ماژول‌های خارج از «فایل‌ها» دست نزن.
تست بنویس. make lint test باید سبز شود. در پایان، معیار پذیرش را یکی‌یکی بررسی کن.
```

**قواعد:**
- هر تسک یک branch و یک MR جدا دارد.
- تیک وضعیت در جدول §۴ زده می‌شود.
- تسکی که معیار پذیرشش پاس نشده، تمام‌شده حساب نمی‌شود.

---

## ۴. جدول تسک‌ها

| ID | تسک | روز | پیش‌نیاز | وضعیت |
|---|---|---|---|---|
| **M0** | **آماده‌سازی** | | | |
| T0.1 | ریپو، ابزارها، `CLAUDE.md` | 0.5 | — | ☐ |
| T0.2 | خروجی دانش در قالب import | 0.5 | — | ☐ |
| T0.3 | اعتبارسنجی provider و انتخاب مدل | 0.5 | — | ☐ |
| T0.4 | قرارداد OpenAPI بک‌اند | 0.5 | — | ☐ |
| T0.5 | sidecar embedding | 0.5 | — | ☐ |
| **M1** | **اسکلت** | | | |
| T1.1 | FastAPI، کانفیگ، لاگ، خطا، health | 1 | T0.1 | ☐ |
| T1.2 | احراز هویت JWT و مجوزدهی | 1 | T1.1 | ☐ |
| T1.3 | docker-compose، Postgres + pgvector، Alembic | 1 | T1.1 | ☐ |
| T1.4 | `policy.yaml`، `routes.yaml`، جدول `settings` | 0.5 | T1.3 | ☐ |
| T1.5 | لایه‌ی connector (fake و http) | 1 | T1.1، T0.4 | ☐ |
| T1.6 | CI در GitLab | 0.5 | T1.3 | ☐ |
| **M2** | **دانش و جستجو** | | | |
| T2.1 | نرمال‌سازی فارسی | 0.5 | T0.1 | ☐ |
| T2.2 | پاک‌سازی و chunking | 1 | T2.1 | ☐ |
| T2.3 | Embedder | 0.5 | T0.5 | ☐ |
| T2.4 | ingest و `admin/kb/import` | 1 | T1.3، T2.2، T2.3 | ☐ |
| T2.5 | جستجو و `POST /v1/search` | 1 | T2.4، T1.2 | ☐ |
| T2.6 | تولید مکالمه‌های تستی و golden set | 1.5 | T0.2، T0.3 | ☐ |
| T2.7 | ارزیابی بازیابی و آستانه‌ها | 1 | T2.5، T2.6 | ☐ |
| **M3** | **مدل و `draft`** | | | |
| T3.1 | لایه‌ی LLM و ثبت مصرف | 1 | T1.4 | ☐ |
| T3.2 | router | 1 | T3.1 | ☐ |
| T3.3 | ساخت prompt | 1 | T2.5 | ☐ |
| T3.4 | پردازش خروجی `draft` | 0.5 | T3.3 | ☐ |
| T3.5 | endpoint `drafts` با SSE | 1.5 | T3.2، T3.4، T1.5 | ☐ |
| T3.6 | audit، مصرف، feedback، `kb_gaps` | 1 | T3.5 | ☐ |
| T3.7 | rate limit و بودجه | 0.5 | T3.6 | ☐ |
| **M4** | **دمو** | | | |
| T4.1 | endpointهای dev برای دمو | 0.5 | T1.5، T1.2 | ☐ |
| T4.2 | UI دمو: تب کارشناس و جستجو | 2 | T3.6، T4.1 | ☐ |
| **M5** | **ارزیابی پاسخ** | | | |
| T5.1 | harness ارزیابی پاسخ و LLM داور | 1.5 | T3.6، T2.6 | ☐ |
| **M6** | **`auto` در سایه** | | | |
| T6.1 | guardrailها | 1 | T3.4 | ☐ |
| T6.2 | دروازه‌ی جمله‌ای | 1 | T6.1 | ☐ |
| T6.3 | خط لوله‌ی `auto` و `replies` | 1.5 | T6.2، T3.6 | ☐ |
| T6.4 | اجرای سایه‌ی آفلاین و تب امتیازدهی | 1.5 | T6.3، T4.2 | ☐ |
| T6.5 | تب شبیه‌ساز مشتری | 0.5 | T6.3، T4.2 | ☐ |
| **M7** | **ارائه** | | | |
| T7.1 | اندازه‌گیری نهایی و برآورد هزینه | 0.5 | T5.1، T6.4 | ☐ |
| T7.2 | اسلاید فنی HTML | 1 | T7.1 | ☐ |
| T7.3 | سناریوی دمو و تمرین | 0.5 | T7.2 | ☐ |

**مسیرهای موازی:** M0 کاملاً موازی است. T2.6 (داده) و T3.1 تا T3.2 (مدل) مستقل از M2 جلو می‌روند.

---

## ۵. ساختار ریپو

`service-ai-support/` همان ریپوی `nipoto-ai` است (§۱۴ سند). تنها تفاوت‌ها با سند: پوشه‌های `contracts/`، `data/`، `scripts/`، `app/demo/` و فایل `config/routes.yaml`.

```
service-ai-support/
├── AI-SERVICE.fa.md  MVP-PLAN.fa.md  CLAUDE.md
├── pyproject.toml  uv.lock  Makefile  Dockerfile  docker-compose.yml  .gitlab-ci.yml
├── app/
│   ├── main.py
│   ├── api/          health, search, drafts, replies, feedback, requests, admin_kb, demo
│   ├── core/         config, auth, actor, errors, logging
│   ├── pipeline/     orchestrator, router, prompt_builder, postprocess, sentence_gate, prompts/*.md
│   ├── retrieval/    normalize, clean, chunk, embed, ingest, search
│   ├── llm/          base, openai_compat, routes, usage, fake
│   ├── guardrails/   pii, links, language, citations, policy
│   ├── connectors/   base, fake, http
│   ├── db/           models, session, repositories
│   └── demo/static/  index.html, demo.js, sse-client.js     (فقط dev)
├── config/           policy.yaml, routes.yaml
├── contracts/        main-backend.openapi.yaml
├── data/             kb/*.json, fixtures/conversations/*.json
├── scripts/          gen_dev_keys.py, mint_token.py, check_provider.py, gen_fixtures.py
├── jobs/             shadow_run.py
├── evals/            golden.jsonl, run_retrieval.py, run_answers.py, reports/
├── migrations/
└── tests/
```

---

## ۶. شرح تسک‌ها

قالب هر تسک: **هدف**، **فایل‌ها**، **کار**، **پذیرش**، و **سند** (بخش‌های مرتبط در سند طراحی).

### M0 — آماده‌سازی

#### T0.1 ریپو، ابزارها، `CLAUDE.md`
- **فایل‌ها:** `pyproject.toml` (با `uv`)، `Makefile`، `.gitignore`، `CLAUDE.md`، `.cursor/rules/nipoto-ai.mdc`، و پوشه‌های خالی §۵
- **کار:**
  - `git init`
  - نصب وابستگی‌های §۱۴ سند، به‌جز `sentence-transformers` و `hazm`
  - `ruff` و `pytest`
  - هدف‌های Makefile: `lint`، `test`، `up`، `token`، `kb-import`، `eval-retrieval`، `eval-answers`، `shadow-run`
  - در `CLAUDE.md`:
    - اصول AI-1 تا AI-7 به‌صورت قاعده‌ی الزامی
    - مرز ماژول‌ها:
      - فقط `connectors/` بک‌اند را صدا می‌زند.
      - `pipeline/` نام provider را نمی‌شناسد.
      - فیلتر visibility در `search()` اجباری است.
      - `user_id` فقط از `Actor` می‌آید.
    - قاعده‌ی تست: بدون شبکه در unit test؛ با `FakeLLM`، `FakeEmbedder` و `FakeMainBackend`
    - نرمال‌سازی دوطرفه (ingest و جستجو)
    - هر تغییر prompt یک فایل با نسخه‌ی جدید است.
    - دستورها
- **پذیرش:** `make lint test` روی ریپوی خالی سبز است. `CLAUDE.md` به سند و پلن لینک دارد.

#### T0.2 خروجی دانش در قالب import
- **فایل‌ها:** `data/kb/nipoto_kb.json`، و `scripts/convert_kb.py` اگر فرمت خروجی فرق دارد
- **کار:**
  - FAQ و مستندات فعلی به قالب §۹.۲ تبدیل شوند: `id`، `type`، `visibility`، `title`، `body`، `url`، `updated_at`.
  - `id`ها پایدار و کوتاه باشند (مثلاً `faq_42`).
- **پذیرش:** همه‌ی آیتم‌ها `visibility` دارند و idها یکتا هستند. تعداد آیتم‌ها و موضوع‌ها یادداشت می‌شود.
- **سند:** §۹.۱، §۹.۲

#### T0.3 اعتبارسنجی provider و انتخاب مدل
- **فایل‌ها:** `scripts/check_provider.py`
- **کار:**
  - با SDK `openai` و `base_url` یک stream فارسی و یک فراخوانی JSON mode تست شود.
  - پشتیبانی از `stream_options.include_usage` بررسی شود.
  - TTFT و قیمت هر مدل ثبت شود.
  - `CHAT_MODEL` و `SMALL_MODEL` انتخاب شوند.
  - سیاست داده‌ی provider یادداشت شود (§۱۰.۵، §۱۷ سؤال ۴).
- **پذیرش:** اسکریپت هر دو حالت را موفق اجرا می‌کند. یک جدول کوتاه با مدل، TTFT، قیمت و سیاست داده در `evals/reports/provider.md` هست.

#### T0.4 قرارداد OpenAPI بک‌اند
- **فایل‌ها:** `contracts/main-backend.openapi.yaml`
- **کار:**
  - B-AI-2 و B-AI-3 کامل و قطعی نوشته شوند: فیلدها، کدهای خطا، و هدر «به نمایندگی از» (§۶.۳).
  - B-AI-1، ۵، ۶ و ۷ با علامت `x-phase: post-mvp` بیایند.
  - فایل به تیم بک‌اند داده شود و ستون «موجود است؟» جدول §۷.۲ با آن‌ها پر شود.
- **پذیرش:** فایل با `openapi-spec-validator` معتبر است. جلسه با بک‌اند برگزار و نتیجه در همین فایل کامنت شده.

#### T0.5 sidecar embedding
- **فایل‌ها:** سرویس `embeddings` در `docker-compose.yml` (پیش‌نویس)
- **کار:**
  - TEI نسخه‌ی CPU (یا Infinity یا Ollama) با `BAAI/bge-m3` از سرورهای خودتان اجرا شود.
  - دسترسی به image و وزن‌های مدل بررسی شود؛ اگر HuggingFace یا ghcr مسدود یا کند است، در registry داخلی mirror شود.
  - تأخیر embedding یک پرسش اندازه‌گیری شود.
- **پذیرش:**
  - `POST /v1/embeddings` بردار ۱۰۲۴ بعدی برمی‌گرداند.
  - p50 تأخیر پرسش کمتر از ۲۰۰ms است.
  - اگر نه: تصمیم fallback (درون‌اپ یا سرور دیگر) ثبت شود.
- **سند:** §۹.۵

### M1 — اسکلت

#### T1.1 FastAPI، کانفیگ، لاگ، خطا، health
- **فایل‌ها:** `app/main.py`، `app/core/{config,errors,logging}.py`، `app/api/health.py`
- **کار:**
  - `pydantic-settings`
  - `structlog` با خروجی JSON و `request_id` در هر لاگ
  - خطای `application/problem+json` با فیلد `code` پایدار
  - `GET /v1/health` و `GET /v1/ready`
  - CORS با allowlist از env
- **پذیرش:** تست: health برابر 200؛ مسیر ناموجود `404` با `problem+json`؛ `/openapi.json` ساخته می‌شود.
- **سند:** §۵.۱

#### T1.2 احراز هویت JWT و مجوزدهی
- **فایل‌ها:** `app/core/{auth,actor}.py`، `scripts/{gen_dev_keys,mint_token}.py`
- **کار:**
  - RS256 با کلید عمومی dev از env، یا `JWKS_URL` با کش (از `PyJWKClient`).
  - بررسی `aud=nipoto-ai`، `exp`، `sub` و `role`.
  - dataclass `Actor`.
  - dependency `require_roles(...)` طبق ماتریس §۶.۳.
  - `make token ROLE=staff SUB=u1`.
- **پذیرش:**
  - تست برای: بدون توکن، امضای غلط، منقضی، و `aud` غلط، همه `401`؛ نقش غلط `403`.
  - `user_id` در هیچ کجای کد از body خوانده نمی‌شود (بررسی در review).
- **سند:** §۶

#### T1.3 docker-compose، Postgres + pgvector، Alembic
- **فایل‌ها:** `docker-compose.yml` (app، `pgvector/pgvector:pg16`، embeddings)، `Dockerfile`، `app/db/{models,session}.py`، `migrations/`
- **کار:**
  - SQLAlchemy 2 async.
  - migration اول با همه‌ی جداول §۱۳ سند: `kb_documents`، `kb_chunks` (ستون `vector(1024)`)، `kb_gaps`، `ai_requests` (به‌علاوه‌ی ستون `shadow bool`)، `reply_keys` با unique روی (`conversation_id`، `trigger_message_id`)، `ai_feedback`، `settings`، `usage_daily`.
- **پذیرش:** `make up` و بعد `alembic upgrade head` جداول را می‌سازد، و `/v1/ready` برابر 200 است.
- **سند:** §۱۳

#### T1.4 `policy.yaml`، `routes.yaml`، جدول `settings`
- **فایل‌ها:** `config/policy.yaml`، `config/routes.yaml`، `app/core/config.py`، `app/db/repositories/settings.py`
- **کار:**
  - مدل pydantic برای policy (§۱۳) و routes (§۱۰.۳)؛ `routes.yaml` قیمت هر مدل را هم دارد.
  - اعتبارسنجی هنگام startup.
  - `settings.get("auto_mode")` با کش کوتاه؛ پیش‌فرض `shadow`.
- **پذیرش:** policy نامعتبر، startup را با پیام روشن متوقف می‌کند. تغییر `auto_mode` در DB بدون ری‌استارت اعمال می‌شود.

#### T1.5 لایه‌ی connector
- **فایل‌ها:** `app/connectors/{base,fake,http}.py`، `data/fixtures/conversations/_sample.json`
- **کار:**
  - `MainBackend` Protocol دقیقاً طبق §۷.۳ سند.
  - مدل‌های دامنه: `Conversation` با `owner_id` و `handled_by`، و `Message` با `author_kind`.
  - **`FakeMainBackend`:**
    - از JSON می‌خواند.
    - پیام‌ها در حافظه append می‌شوند.
    - قانون مالکیت را مثل بک‌اند اعمال می‌کند: user فقط مکالمه‌ی خودش؛ staff همه.
  - **`HttpMainBackend`:**
    - طبق `contracts/` و با `httpx`.
    - timeout ۲ ثانیه؛ retry فقط برای GET.
  - انتخاب با env: `MAIN_BACKEND=fake|http`.
- **پذیرش:**
  - تست: user به مکالمه‌ی دیگری دسترسی ندارد (`conversation_not_found`).
  - `HttpMainBackend` با `respx` تست شده.
- **سند:** §۷

#### T1.6 CI در GitLab
- **فایل‌ها:** `.gitlab-ci.yml`
- **کار:**
  - مرحله‌های lint، test (با سرویس Postgres) و build image.
  - الگوی registry از `../staff/.gitlab-ci.yml` گرفته شود.
  - job دستی `eval` (هزینه دارد) با `rules: changes` روی `app/pipeline/prompts/**`، `config/routes.yaml` و `app/retrieval/**`.
- **پذیرش:** pipeline روی MR سبز است.

### M2 — دانش و جستجو

#### T2.1 نرمال‌سازی فارسی
- **فایل‌ها:** `app/retrieval/normalize.py`، `tests/test_normalize.py`
- **کار:**
  - تابع `normalize()` طبق جدول §۹.۳ سند: ی و ک عربی، ارقام فارسی و عربی به لاتین، نیم‌فاصله‌ی «می/نمی» و «ها/های/تر/ترین»، حذف کشیده و اعراب، و یکی کردن فاصله‌ها و کاراکترهای کنترلی.
  - ingest و جستجو هر دو **همین** تابع را صدا می‌زنند.
- **پذیرش:** تست جدول‌محور با همه‌ی ردیف‌های §۹.۳ و حداقل ۲۰ جفت «قبل / بعد».

#### T2.2 پاک‌سازی و chunking
- **فایل‌ها:** `app/retrieval/{clean,chunk}.py`
- **کار:**
  - HTML به متن تبدیل شود و تیتر و لیست به‌صورت markdown بمانند.
  - **FAQ:** یک chunk به شکل `پرسش: … / پاسخ: …`؛ بیش از ۸۰۰ توکن بر اساس پاراگراف شکسته می‌شود و پرسش در همه‌ی تکه‌ها تکرار می‌شود.
  - **مستندات:** بر اساس h2 و h3؛ بیش از ۵۰۰ توکن بر اساس پاراگراف، با ۵۰ توکن هم‌پوشانی.
  - هر chunk با «عنوان › بخش» شروع می‌شود و metadata کامل دارد.
  - شمارش توکن تقریبی و قابل تنظیم است.
- **پذیرش:** تست: FAQ کوتاه شکسته نمی‌شود؛ هیچ chunkی بدون پیشوند عنوان نیست.
- **سند:** §۹.۴

#### T2.3 Embedder
- **فایل‌ها:** `app/retrieval/embed.py`
- **کار:**
  - `Embedder` Protocol (§۱۰.۱).
  - `OpenAICompatEmbedder` روی sidecar، با batch و بردار normalize‌شده.
  - `FakeEmbedder` قطعی (مبتنی بر hash) برای تست.
  - نام مدل برای ستون `embedding_model`.
- **پذیرش:** طول بردار ۱۰۲۴ است و norm آن ۱.

#### T2.4 ingest و `admin/kb/import`
- **فایل‌ها:** `app/retrieval/ingest.py`، `app/api/admin_kb.py`
- **کار:**
  - اعتبارسنجی؛ موارد رد شده با دلیل در لیست `rejected` برمی‌گردند.
  - پاک‌سازی، نرمال‌سازی، chunk، embed.
  - upsert با `content_hash`.
  - جایگزینی chunkهای هر سند در **یک تراکنش**.
  - پاسخ: `{added, updated, unchanged, rejected}`.
  - نقش `admin` لازم است.
  - `make kb-import FILE=data/kb/nipoto_kb.json`.
- **پذیرش:** import دوباره‌ی همان فایل یعنی `unchanged == total` و **صفر** فراخوانی embed (تست با FakeEmbedder شمارنده).
- **سند:** §۹.۲

#### T2.5 جستجو و `POST /v1/search`
- **فایل‌ها:** `app/retrieval/search.py`، `app/api/search.py`
- **کار:**
  - یک تابع `search(query, actor) -> list[Hit]`.
  - visibility از نقش actor مشتق می‌شود و **پارامتر نیست**.
  - SQL طبق §۹.۷ سند: ۲۰ نامزد، حداکثر ۲ chunk از هر سند، ۵ نتیجه‌ی نهایی.
  - endpoint برای `staff` و `admin`.
- **پذیرش:**
  - تست: `user` و `guest` هرگز `internal` نمی‌گیرند.
  - پرسش با «ي» و «ی»، و با ارقام فارسی و لاتین، نتیجه‌ی یکسان می‌دهد.

#### T2.6 تولید مکالمه‌های تستی و golden set
- **فایل‌ها:** `scripts/gen_fixtures.py`، `evals/golden.jsonl`، `data/fixtures/conversations/*.json`
- **کار (با LLM، از روی `data/kb`):**
  - برای هر FAQ، ۲ پرسش محاوره‌ای که **از کلمات عنوان استفاده نکنند**، همراه با `expected_ids`.
  - حدود ۲۰ پرسش «بی‌جواب» مرتبط با نیپوتو.
  - حدود ۱۵ پرسش موضوع ممنوع، حدود ۱۰ `wants_human` و حدود ۱۰ prompt injection.
  - حداقل ۳۰ مکالمه‌ی چندنوبتی با پرسش ادامه‌دار («اون یکی چی؟»).
  - ۳۰ مورد سخت دست‌نویس.
  - بازبینی دستی کل فایل.
  - فیلدها طبق §۱۲: `question`، `expected_ids`، `should_handoff`، `is_deny_topic`، `topic`، `synthetic`.
- **پذیرش:** حداقل ۱۵۰ ردیف و ۳۰ مکالمه، همه بازبینی‌شده.
- **هشدار:** پرسش مصنوعی ساخته‌شده از روی FAQ، hit@5 را خوش‌بینانه نشان می‌دهد. در گزارش جدا شمرده شود (فیلد `synthetic`).

#### T2.7 ارزیابی بازیابی و آستانه‌ها
- **فایل‌ها:** `evals/run_retrieval.py`، `evals/reports/`
- **کار:**
  - hit@5 و MRR، به تفکیک نوع سند، موضوع و مصنوعی/دستی.
  - دقت تشخیص «بی‌منبع».
  - sweep روی `T_low` و `T_high` برای هر دو نوع خطای §۹.۹ و انتخاب آستانه‌ها.
  - ثبت در `routes.yaml`.
  - خروجی JSON و markdown.
- **پذیرش:** hit@5 حداقل ۸۰٪، یا دلیل مکتوب. آستانه‌ها در کانفیگ‌اند.
- **سند:** §۹.۹، §۹.۱۲

### M3 — مدل و `draft`

#### T3.1 لایه‌ی LLM و ثبت مصرف
- **فایل‌ها:** `app/llm/{base,openai_compat,routes,usage,fake}.py`
- **کار:**
  - `LLMProvider` با `stream` و `complete_json` (§۱۰.۱).
  - adapter سازگار با OpenAI: `response_format=json_object`، و اگر پشتیبانی نشد parse دستی.
  - مسیرها از `routes.yaml`.
  - retry فقط قبل از اولین توکن؛ timeout سمت سرور.
  - مصرف: توکن ورودی و خروجی (`include_usage`، و اگر نبود تخمین)، TTFT، زمان کل، هزینه از جدول قیمت.
  - `FakeLLM` با خروجی اسکریپتی برای تست.
- **پذیرش:** تست: retry بعد از اولین توکن رخ نمی‌دهد؛ usage همیشه پر است.
- **سند:** §۱۰

#### T3.2 router
- **فایل‌ها:** `app/pipeline/router.py`، `app/pipeline/prompts/router.v1.md`
- **کار:**
  - لایه‌ی کلمه‌ای قطعی.
  - `complete_json` با قالب پیوست الف.۳ به‌همراه یک نمونه‌ی few-shot.
  - مدل pydantic `RouterResult`.
  - fallback طبق §۹.۶: intent برابر `other` و `search_query` برابر آخرین پیام.
- **پذیرش:** تست با FakeLLM برای JSON نامعتبر، intent ناشناخته و timeout.

#### T3.3 ساخت prompt
- **فایل‌ها:** `app/pipeline/prompt_builder.py`، `app/pipeline/prompts/{draft,auto}.v1.md`
- **کار:**
  - قالب‌های پیوست الف با جای‌گذاری از policy.
  - بلوک `<sources>` طبق §۹.۸: escape متن، بودجه‌ی ۲۰۰۰ توکن، و حذف کامل کم‌امتیازترین منبع.
  - تاریخچه حدود ۸۰۰ توکن، با پیشوند «(کارشناس)» برای پیام کارشناس.
  - ترتیب پیام‌ها طبق الف.۱.
  - flag ادغام پیام‌های system.
  - نسخه‌ی prompt برگردانده می‌شود تا در audit ثبت شود.
- **پذیرش:** تست: یک `</source>` جعلی ساختار را نمی‌شکند؛ بودجه منبع کامل حذف می‌کند.

#### T3.4 پردازش خروجی `draft`
- **فایل‌ها:** `app/pipeline/postprocess.py`، `app/guardrails/citations.py`
- **کار:**
  - `[HANDOFF]` و `[NO_ANSWER]` در `draft` به `warning` تبدیل می‌شوند.
  - ارجاع‌ها با idهای بازیابی‌شده اعتبارسنجی می‌شوند.
  - `text` بدون نشانه و `annotated_text` با نشانه.
  - «یادداشت برای کارشناس:» به `notes` منتقل می‌شود.
  - هشدار «منبع ضعیف» و «منبعی پیدا نشد» طبق آستانه‌ها.
- **پذیرش:** تست جدول‌محور طبق پیوست الف.۵.

#### T3.5 endpoint `drafts` با SSE
- **فایل‌ها:** `app/pipeline/orchestrator.py`، `app/api/drafts.py`
- **کار:**
  - `POST /v1/conversations/{id}/drafts` (نقش staff).
  - مراحل §۸.۱ برای `draft`.
  - `sse-starlette` با رویدادهای `created`، `delta`، `completed` و `failed`.
  - delta روی مرز کلمه، با flush حداکثر هر ۵۰ms.
  - `: ping` هر ۱۵ ثانیه و `X-Accel-Buffering: no`.
  - **قطع اتصال یعنی لغو task تولید** و ثبت وضعیت `cancelled` (D5).
- **پذیرش:**
  - تست یکپارچه با FakeLLM: ترتیب رویدادها درست است و هیچ deltaای کلمه را نمی‌شکند.
  - `completed` متن کامل را دارد.
  - قطع اتصال، تولید را متوقف می‌کند.
- **سند:** §۴.۱، §۵.۳

#### T3.6 audit، مصرف، feedback، `kb_gaps`
- **فایل‌ها:** `app/db/repositories/*`، `app/api/{feedback,requests}.py`
- **کار:**
  - رکورد `ai_requests` طبق §۱۱.۳، یک بار در شروع و یک بار در پایان.
  - upsert در `usage_daily`.
  - `POST /v1/feedback`: `verdict` یکی از `accepted|edited|rejected`، و برای سایه `correct|wrong|dangerous`.
  - `GET /v1/requests/{id}` برای وضعیت، متن و متریک‌ها.
  - upsert در `kb_gaps` وقتی امتیاز زیر `T_low` است.
- **پذیرش:** هر درخواست یک رکورد audit کامل دارد و feedback به `request_id` وصل است.

#### T3.7 rate limit و بودجه
- **فایل‌ها:** `app/core/limits.py`
- **کار:**
  - شمارنده‌ی درون‌حافظه برای هر actor و IP.
  - بررسی بودجه‌ی روزانه از `usage_daily` در برابر `policy.limits.daily_budget_usd`.
  - خطاهای `rate_limited` و `budget_exhausted`.
- **پذیرش:** تست هر دو خطا.
- **سند:** §۱۱.۲

### M4 — دمو

#### T4.1 endpointهای dev برای دمو
- **فایل‌ها:** `app/api/demo.py`
- **کار:**
  - فقط وقتی `DEMO_ENABLED=true` و `ENV!=production` mount می‌شوند.
  - `POST /demo/token` برای ساخت توکن dev با نقش دلخواه.
  - `GET /demo/conversations`، `GET /demo/conversations/{id}` و `POST /demo/conversations/{id}/messages` روی FakeMainBackend.
- **پذیرش:** تست: در production این مسیرها `404` برمی‌گردانند.

#### T4.2 UI دمو: تب کارشناس و جستجو
- **فایل‌ها:** `app/demo/static/{index.html,demo.js,sse-client.js}`
- **کار:**
  - بدون build: vanilla JS، یا Vue 3 که فایلش در `static` کپی شده (بدون CDN). RTL با فونت Vazirmatn محلی.
  - **`sse-client.js`:** SSE با `fetch` و `ReadableStream`، چون `EventSource` از POST و هدر پشتیبانی نمی‌کند. به‌عنوان نمونه‌ی مرجع برای تیم staff نوشته شود.
  - **تب کارشناس:** لیست مکالمه‌ها؛ دکمه‌ی «پیش‌نویس» با stream زنده؛ `annotated_text` با ارجاع‌هایی که با hover عنوان و لینک منبع را نشان می‌دهند؛ `notes` و `warnings`؛ باکس قابل ویرایش؛ دکمه‌های پذیرش، ویرایش و رد که `feedback` را صدا می‌زنند.
  - **تب جستجو:** نمایش امتیازها.
  - **نوار متریک هر درخواست:** TTFT، زمان کل، توکن، هزینه، مدل و نسخه‌ی prompt.
- **پذیرش:** سناریوی کامل پیش‌نویس، ویرایش و feedback از مرورگر انجام می‌شود و در DB ثبت است.

### M5 — ارزیابی پاسخ

#### T5.1 harness ارزیابی پاسخ و LLM داور
- **فایل‌ها:** `evals/run_answers.py`، `app/pipeline/prompts/judge.v1.md`
- **کار:**
  - اجرای خط لوله روی golden set با FakeMainBackend و provider واقعی.
  - معیارها:
    - دقت intent
    - precision و recall انتقال
    - موضوع ممنوع (**۱۰۰٪ الزامی**؛ تست fail)
    - زبان
    - اعتبار ارجاع
    - TTFT p50 و p95
    - هزینه‌ی هر پاسخ
  - LLM داور برای «درست و مستند»، کالیبره با ۳۰ برچسب دستی خودتان.
  - گزارش در `evals/reports/`.
  - `make eval-answers`، و job دستی در CI.
- **پذیرش:** گزارش تولید می‌شود، و میزان توافق داور با برچسب دستی گزارش شده.
- **سند:** §۱۲

### M6 — `auto` در سایه

#### T6.1 guardrailها
- **فایل‌ها:** `app/guardrails/{pii,links,language,policy}.py`
- **کار:**
  - **PII:** نرمال‌سازی ارقام قبل از regex؛ کارت ۱۶ رقمی با Luhn؛ شبا (`IR` + ۲۴ رقم)؛ موبایل `09…`؛ استثنای `policy.contact`.
  - **لینک:** فقط `https` با host در allowlist؛ بقیه به host متنی تبدیل می‌شوند؛ جمع‌آوری `links`.
  - **زبان:** نسبت حروف فارسی.
  - **تصمیم موضوع ممنوع:** در سرور، از intent router و policy.
- **پذیرش:** تست جدول‌محور برای هر کنترل، با ارقام فارسی.
- **سند:** §۸.۳

#### T6.2 دروازه‌ی جمله‌ای
- **فایل‌ها:** `app/pipeline/sentence_gate.py`
- **کار:**
  - بافر تا `.`، `؟`، `!` یا خط جدید.
  - کنترل‌های ارزان روی هر جمله و بعد آزاد کردن آن.
  - `[HANDOFF]` یا `[NO_ANSWER]`: در ابتدا یعنی انتقال؛ وسط متن یعنی قطع، با نگه داشتن جمله‌های آزادشده.
  - اگر زبان جمله‌ی اول فارسی نبود: یک بار تولید مجدد، و بعد انتقال.
- **پذیرش:** تست با streamهای اسکریپتی: نشانه هرگز در خروجی نمی‌آید، حتی وقتی بین دو delta شکسته شده باشد.
- **سند:** §۸.۳، پیوست الف.۵

#### T6.3 خط لوله‌ی `auto` و `replies`
- **فایل‌ها:** `app/api/replies.py`، و گسترش `orchestrator.py`
- **کار:**
  - `POST /v1/conversations/{id}/replies` برای نقش `user` و `guest`.
  - بررسی‌ها:
    - مالکیت (از connector)
    - `handled_by == assistant`
    - M آخرین پیام کاربر است
    - idempotency با `reply_keys`؛ تکراری یعنی `409 already_replied` همراه `request_id`
    - سقف نوبت
  - نیت `wants_human`، `deny_topic`، یا امتیاز کمتر از `T_high`: رویداد `handoff` بدون تولید.
  - مهمان: فقط `public` و بدون `customer_data`.
  - `auto_mode`:
    - `off`: انتقال
    - `shadow`: تولید و ذخیره با `shadow=true`، **بدون نوشتن در بک‌اند**
    - `live`: خطای `not_implemented`
  - در MVP تولید به اتصال گره خورده است (D5).
- **پذیرش:**
  - تست: دو درخواست با یک `trigger_message_id` فقط یک پاسخ می‌سازند.
  - موضوع ممنوع بدون فراخوانی LLM تولید منتقل می‌شود.
  - در `shadow`، `post_assistant_message` صدا زده نمی‌شود.
- **سند:** §۴.۲، §۸

#### T6.4 اجرای سایه‌ی آفلاین و تب امتیازدهی
- **فایل‌ها:** `jobs/shadow_run.py`، و تب «سایه» در `app/demo/static`
- **کار:**
  - batch روی همه‌ی مکالمه‌های تستی؛ هر پیام کاربر یک trigger است.
  - خروجی‌ها در `ai_requests` با `shadow=true` ذخیره می‌شوند.
  - **تب سایه:**
    - context مکالمه، پاسخ یا دلیل انتقال، و منابع
    - دکمه‌های درست، غلط و خطرناک، به‌علاوه‌ی توضیح؛ ثبت در `ai_feedback`
    - آمار: درستی، نرخ انتقال، تعداد خطرناک
  - `make shadow-run`.
- **پذیرش:** batch کامل اجرا می‌شود؛ آمار از روی امتیازها محاسبه و نمایش داده می‌شود.

#### T6.5 تب شبیه‌ساز مشتری
- **فایل‌ها:** `app/demo/static`
- **کار:**
  - UI شبیه ویجت.
  - پیام مشتری append می‌شود، سپس `replies` صدا زده می‌شود.
  - stream جمله‌ای نمایش داده می‌شود و در صورت انتقال، بنر «انتقال به کارشناس» با دلیل.
- **پذیرش:** سه سناریو از مرورگر کار می‌کنند: پاسخ عادی، موضوع ممنوع، و درخواست کارشناس.

### M7 — ارائه

#### T7.1 اندازه‌گیری نهایی و برآورد هزینه
- **کار:**
  - اجرای کامل `eval-retrieval`، `eval-answers` و `shadow-run`.
  - جمع‌آوری عددها.
  - هزینه‌ی ماهانه با توکن **اندازه‌گیری‌شده** و فرمول §۱۵ سند، برای دو رده‌ی مدل.
- **پذیرش:** `evals/reports/summary.md` با همه‌ی اعداد اسلاید.

#### T7.2 اسلاید فنی HTML
- **کار:** Artifact فارسی RTL (ساخت با Claude) با این بخش‌ها:
  1. مسئله و هدف
  2. معماری و مرزها (AI-1 تا AI-7)
  3. دو حالت و خط لوله
  4. RAG فارسی
  5. مدل امنیتی
  6. **عددهای ارزیابی**، با تفکیک مصنوعی و دستی
  7. TTFT و هزینه
  8. نقشه‌ی راه تا `auto` زنده (فاز ۵ و ۶، self-hosted)
  9. **تصمیم‌های لازم از مدیرعامل** (§۱۷: سؤال ۴ درباره‌ی ارسال داده به API خارجی، آستانه‌های ورود به حالت زنده، مدت نگهداری audit)
  10. ریسک‌ها، از جمله «سایه روی داده‌ی مصنوعی جای ترافیک واقعی را نمی‌گیرد»
  11. نیازها از تیم‌ها
- **پذیرش:** اسلاید منتشر شده و همه‌ی عددها از `summary.md` آمده‌اند.

#### T7.3 سناریوی دمو و تمرین
- **کار:** سناریوی ۱۰ دقیقه‌ای:
  1. جستجو با «ي/ی» و ارقام فارسی
  2. پیش‌نویس با پرسش ادامه‌دار و ارجاع
  3. پیش‌نویس بی‌منبع، همراه با هشدار
  4. مشتری: پاسخ جریانی
  5. موضوع ممنوع و انتقال
  6. تلاش injection
  7. نوار متریک و هزینه
  8. آمار سایه
- **fallback:** ویدیو یا اسکرین‌شات آماده، برای وقتی که provider قطع است.
- **پذیرش:** یک بار تمرین کامل، بدون خطا.

---

## ۷. بعد از MVP (طبق سند)

- **فاز ۵، `auto` زنده:**
  - B-AI-1، ۵، ۶ و ۷
  - جدا کردن تولید از اتصال (task پس‌زمینه)، reattach، `cancel`
  - circuit breaker
  - توکن مهمان با محدودیت origin
  - سایه روی ترافیک واقعی قبل از live
  - تحویل `sse-client.js` به تیم ویجت
- **فاز ۶:** حساب و سفارش (B-AI-8)، بعد از تصمیم سؤال ۴
- **دانش:** `kb/sync` با tombstone، endpoint `kb/gaps`
- **کیفیت:** rerank و جستجوی ترکیبی، فقط با بهبود اندازه‌گیری‌شده
- **self-hosted:** vLLM، فقط با تغییر `base_url`، به شرط پاس شدن ارزیابی
- **فرانت staff:** اتصال واقعی (`insertText`) با تیم staff و `HttpMainBackend` روی B-AI-2 و B-AI-3

---

## ۸. ریسک‌ها

| ریسک | اثر | کاهش |
|---|---|---|
| داده‌ی مصنوعی عدد را خوش‌بینانه نشان می‌دهد | تصمیم اشتباه درباره‌ی آمادگی | فیلد `synthetic` و گزارش جدا؛ ۳۰ مورد دست‌نویس سخت؛ سایه‌ی زنده قبل از live |
| مسدود بودن HuggingFace یا ghcr | M2 متوقف می‌شود | T0.5 در هفته‌ی اول؛ mirror در registry داخلی |
| provider از `include_usage` یا JSON mode پشتیبانی نمی‌کند | متریک هزینه یا router ناقص | تشخیص در T0.3؛ fallback تخمین توکن و parse دستی |
| سیاست داده‌ی provider (§۱۷ سؤال ۴) | عدم اجازه‌ی ارسال مکالمه | در MVP فقط داده‌ی مصنوعی؛ تصمیم در اسلاید از مدیرعامل گرفته می‌شود |
| دیر رسیدن B-AI-2 و B-AI-3 | اتصال واقعی نیست | MVP کاملاً روی `FakeMainBackend` است؛ قرارداد از هفته‌ی اول دست بک‌اند است |

---

## ۹. راستی‌آزمایی end-to-end

1. `make up` و بعد `alembic upgrade head`؛ `/v1/health` و `/v1/ready` برابر 200.
2. `make kb-import FILE=data/kb/nipoto_kb.json` دو بار؛ بار دوم `unchanged == total`.
3. `make eval-retrieval`: hit@5 و MRR و آستانه‌ها در `evals/reports/`.
4. `make token ROLE=staff` و بعد `curl -N` روی `/v1/conversations/<id>/drafts`؛ رویدادهای SSE به ترتیب.
5. باز کردن `/demo`: سناریوی کامل پیش‌نویس، feedback، جستجو، و شبیه‌ساز مشتری.
6. `make shadow-run` و امتیازدهی در تب سایه؛ آمار نمایش داده می‌شود.
7. `make eval-answers`: موضوع ممنوع ۱۰۰٪ و گزارش کامل.
8. CI روی MR سبز است: lint، test، build.

---

## ۱۰. شروع

پیاده‌سازی از T0.1 شروع می‌شود و تسک‌به‌تسک با Claude/Cursor جلو می‌رود. تسک‌های M0 را می‌شود هم‌زمان شروع کرد. اسلاید (T7.2) در پایان با عددهای واقعی ساخته می‌شود.
