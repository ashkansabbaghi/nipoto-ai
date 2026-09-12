# چگونه به Abr وصل شویم

> مخاطب: یک agent کدنویس که بعداً یک connector Abr **داخل** `nipoto-ai` پیاده می‌کند.
> تاریخ برداشت از کد: ۱۴۰۵/۰۶/۲۱ (2026-09-12).
> منبع حقیقت: کد `@abr/client` در `/home/ashkan/Projects/nipoto/abr/web` و مصرف‌کننده‌های فرانت. حدس نزنید؛ اگر سرور چیزی فرستاد که اینجا نیست، همان فریم روی سیم را ثبت کنید.

این سند **فقط** دستور پخت اتصال است. طراحی محصول، OpenAPI، FAQ و `MAIN_BACKEND=http` این‌جا موضوع نیست. این سند connector را پیاده نمی‌کند.

---

## ۱. Abr چیست

Abr فریم‌ورک CQRS روی **یک WebSocket** است. کلاینت رسمی JS پکیج `@abr/client` است (`/home/ashkan/Projects/nipoto/abr/web`، نسخهٔ `0.0.4`). بعد از handshake، سرور یک پیام `config` می‌فرستد؛ کلاینت یک Proxy به نام `$app` می‌سازد و با سه نوع فریم JSON کار می‌کند: `command` (نوشتن)، `list` (خواندن)، `event` (اشتراک). دامنهٔ محصول (Chat / User / …) داخل SDK hard-code نیست.

---

## ۲. چه چیزی روی دیسک هست (و چه چیزی نیست)

| چیز | وضعیت در این workspace |
|---|---|
| کلاینت JS | فقط همین: `/home/ashkan/Projects/nipoto/abr/web` (`@abr/client`) |
| کلاینت Python / Go / PHP / Rust | **وجود ندارد** |
| سورس سرور Abr | **وجود ندارد.** پوشهٔ `/home/ashkan/Projects/nipoto/abr/` فقط `web/` دارد |
| بک‌اند زنده | remote: `wss://back.*` / `wss://b5-back.nipoto.pro` و مشابه؛ پروتکل را کلاینت تعریف می‌کند، سرور این‌جا دیده نمی‌شود |
| connector Abr در `nipoto-ai` | **وجود ندارد.** امروز فقط `MAIN_BACKEND=fake\|http` (`app/connectors/`) |

`CLAUDE.md` اصل AI-1 هنوز می‌گوید بک‌اند را import نکن و سوکت Abr در سرویس نیست. این سند آن را عوض نمی‌کند؛ فقط دستور پخت اتصال برای کار بعدی است.

فایل‌های JS که یک پورت Python باید از روی آن‌ها نوشته شود:

| فایل | نقش |
|---|---|
| `src/index.js` | ترتیب: connect → `config` → `sendToken` → `Event.enable` |
| `src/socket/Socket.js` | URL، باز کردن WS، `send` / `command` / `event` / `list`، `sendToken`، reconnect |
| `src/socket/receive.js` | parse / ENC1 / dispatch فریم ورودی |
| `src/socket/wsCryptoClient.js` + `wsPayloadCrypto.js` | handshake اختیاری ENC1 |
| `src/auth.js` | خواندن کوکی و شکل `Bearer <jwt>` |
| `src/domains/Command.js` `Event.js` `List.js` | timeout، await، همبستگی `id` |
| `src/domains/generateNamespace.js` | تشخیص UUID به‌عنوان aggregate id |
| `src/domains/config.js` | timeout ۴۰ ثانیه |
| `src/bus/EventBus.js` | routing داخلی؛ سرویس لازم نیست Proxy را پورت کند |

---

## ۳. دستور پخت اتصال (هسته)

ترتیب از `src/index.js` + `Socket.connect` + `Socket.sendToken`. بدون `config` اتصال «آماده» نیست. بدون `sendToken` موفق، commandهای نیازمند هویت `UNAUTHORIZED` می‌شوند.

### گام ۱ — URL را بسازید

`@abr/client` خودش URL نمی‌سازد. ورودی `Abr(url, protocol, options)` است. فرانت‌های نیپوتو فقط `url` می‌دهند؛ `protocol` و `options` معمولاً `undefined` است.

قانون host از `front-end/user-panel/src/utils/resolveBackHost.js` (staff و website همان منطق):

1. اگر hostname لوکال / IP است → host را از env `ABR_URL` بخوان (اجباری؛ وگرنه throw).
2. وگرنه sibling سرویس `back` روی همان دامنه و محیط:
   - `app.nipoto.com` / `staff.nipoto.com` → `back.nipoto.com`
   - `app-stage2.nipoto.pro` → `back-stage2.nipoto.pro`
   - `b5-app.nipoto.pro` → `b5-back.nipoto.pro`
3. استثنا: `m.nipoto.org` → `b.nipoto.org`.
4. پروتکل سوکت: اگر host برابر `localhost` یا با رقم شروع شود → `ws://`؛ وگرنه `wss://`.

`ABR_URL` فقط host است (یا `wss://host` که scheme و path دور انداخته می‌شود). مثال محلی:

```
ABR_URL=b5-back.nipoto.pro
→ wss://b5-back.nipoto.pro
```

`new-support` (`packages/support-sdk/src/env/resolveBackend.ts`) روی localhost پیش‌فرض `b1-back.nipoto.pro` دارد و همیشه `wss://` می‌سازد؛ host باید allowlist باشد. برای سرویس روی localhost همان `wss://<ABR_URL-host>` کافی است.

سند خود SDK (`doc/fa/index.md`) مثال آموزشی `ws://localhost:7200` می‌زند. آن پورت کیت عمومی Abr است، نه بک‌اند نیپوتو.

### گام ۲ — WebSocket را باز کنید

از `Socket.doConnect`:

```js
new WebSocket(url, protocol, options)  // isomorphic-ws
```

`onopen` → bus `socketConnected`. تا این لحظه هنوز `config` نیامده.

### گام ۳ — (اختیاری) ENC1

سرور اگر رمز بخواهد، **اول** plaintext می‌فرستد:

```json
{
  "type": "ws-crypto-server-hello",
  "data": { "serverPublicKey": "<base64 X25519، دقیقاً ۳۲ بایت>" }
}
```

کلاینت (`wsCryptoClient.respondToServerCryptoHello`) keypair می‌سازد، secret مشترک می‌گیرد، AES-GCM می‌سازد، و **بدون ENC1** جواب می‌دهد:

```json
{
  "type": "ws-crypto-client-hello",
  "data": { "clientPublicKey": "<base64 ۳۲ بایت>" }
}
```

از این به بعد هر فریم: رشتهٔ `ENC1:` + base64(`iv` ۱۲ بایت + ciphertext AES-GCM).
HKDF-SHA256 با info بایت‌های UTF-8ی `abr-ws-crypto-v1` (`wsPayloadCrypto.js`).
بعد از enable، فریم plaintext (جز hello) drop می‌شود.
اگر `SERVER_HELLO` نیاید، همه چیز JSON ساده است. سرویس باید هر دو حالت را تحمل کند.

ترتیب سرور وقتی رمز روشن است (`doc/framework/encryption-scenario.md`): connect → SERVER_HELLO → CLIENT_HELLO → `config` رمزشده.

### گام ۴ — منتظر `config` بمانید

`receive.js` روی `type === "config"` می‌کند `bus.send('configReceived', message.data)`.
`Abr(url)` همین‌جا resolve می‌شود و `$app` ساخته می‌شود.

تنها فیلدی که کلاینت برای اتصال مصرف می‌کند: `config.wss` — به‌عنوان پسوند نام command در `sendToken`. بقیهٔ `config` در SDK برای join namespace استفاده نمی‌شود (FIXME در کد: جداکننده همیشه `.` است).

بدون این پیام، Promiseِ `Abr()` هیچ‌وقت resolve نمی‌شود. user-panel حداکثر ۱۵ ثانیه صبر می‌کند (`src/boot/abr.js`).

### گام ۵ — توکن را بفرستید (`sendToken`)

هویت Abr از **کوکی مرورگر روی خود WebSocket نیست**. بعد از `config`، کلاینت یک command داخلی می‌فرستد.

کوکی (فقط مرورگر):

| اپ | نام کوکی | فایل |
|---|---|---|
| user-panel / website / market | `user-token` | `front-end/user-panel/src/utils/authCookie.js` |
| staff | `staff-token` | `front-end/staff/src/utils/authCookie.js` |
| new-support | همان دو تا، بر اساس side | `packages/support-sdk/src/side.ts` |
| پیش‌فرض SDK | `token` | `src/auth.js` — فرانت override می‌کند |

مقدار کوکی: `Bearer <jwt>` (نه JWT لخت). `Socket.sendToken`:

```js
const token = auth.getToken()
if (!token) return
data: { token: token.split(' ')[1] }
```

یعنی روی سیم **فقط JWT** می‌رود. اگر مقدار کوکی فاصله نداشته باشد، `split(' ')[1]` برابر `undefined` است و سرور توکن خالی می‌گیرد.

فریم خروجی `sendToken` (از `Socket.sendToken` + `Command.send`):

```json
{
  "type": "command",
  "namespace": "Abr.Socket",
  "aggregate": { "id": "<uuid تازه>", "exists": true },
  "name": "sendToken-<config.wss>",
  "id": "<uuid پیام>",
  "data": { "token": "<jwt بدون پیشوند Bearer>" },
  "options": {
    "delivered": true,
    "rejected": true,
    "events": ["tokenVerified"]
  },
  "metadata": { "date": "<ISO از JSON.stringify(Date)>" }
}
```

منتظر event به نام `tokenVerified` بمانید (timeout ۴۰ ثانیه). موفقیت → شیء user. شکست → JS کوکی را پاک می‌کند و `tokenRemoved` پابلیش می‌شود.

`Abr()` **قبل از تمام شدن `sendToken` resolve می‌شود.** website صریحاً برای `Auth.tokenVerified` تا ۲۰ ثانیه صبر می‌کند (`front-end/website/utils/panelSessionBootstrap.js`). سرویس هم باید بعد از `tokenVerified` command بزند، نه بعد از `config`.

توکن Abr همان JWT نشست بک‌اند اصلی است. JWT خود `nipoto-ai` (`aud=nipoto-ai`) را به `sendToken` ندهید.

### گام ۶ — command / list / subscribe event

بعد از auth، فریم‌ها را با `Socket.send` بفرستید. همبستگی با `id` پیام (UUID).

**command** — `Socket.command` / `tests/socket.test.js` / `Command.send`:

```json
{
  "type": "command",
  "namespace": "MyContext.MyAggregate",
  "aggregate": { "id": "<uuid>", "exists": true },
  "name": "commandName",
  "id": "<uuid پیام>",
  "data": { "foo": "bar" },
  "options": {
    "delivered": true,
    "rejected": true,
    "events": ["loggedIn"]
  },
  "metadata": { "date": "<ISO Date>" }
}
```

- اگر aggregate id ندهید: `aggregate` برابر `{ "id": "<uuid تازه>" }` است (**بدون** `exists`).
- اگر id بدهید: `{ "id": "<uuid>", "exists": true }`.
- `options.events` = نام eventهایی که command ممکن است publish کند (`await` + کلیدهای `events`). سرور فقط وقتی این‌ها رخ بدهند جواب معنادار می‌فرستد؛ command مقدار return ندارد.
- `data` باید **object** باشد، هرگز `string`.

**list** — `Socket.list` + `tests/socket.test.js` + `tests/domain.test.js`:

```json
{
  "type": "list",
  "namespace": "MyContext.MyAggregate",
  "aggregate": { "id": "<id یا undefined>" },
  "name": "listName",
  "id": "<uuid پیام>",
  "data": {
    "methods": [
      { "name": "scopeName", "args": [] },
      { "name": "methodName", "args": ["some", "argument"] }
    ]
  },
  "options": { "delivered": true, "rejected": true, "live": true }
}
```

اگر `methods` خالی باشد، `data` روی سیم `{}` می‌شود (`methods: undefined` در `JSON.stringify` حذف می‌شود). `aggregate` در list فیلد `exists` ندارد. `live: true` اشتراک است؛ `send()` یک‌باره است.

**subscribe event** — `Socket.event` + `tests/event.test.js` (کلید `data` روی سیم نیست چون `undefined` است):

```json
{
  "type": "event",
  "namespace": "MyContext.MyAggregate",
  "aggregate": { "id": "<uuid>" },
  "name": "eventName",
  "id": "<uuid پیام>",
  "options": { "delivered": true, "rejected": true },
  "metadata": { "date": "<ISO Date>" }
}
```

با aggregate id: `"aggregate": { "id": "<uuid>", "exists": true }`.
`options.minimal: true` یعنی سرور فقط payload کوتاه بفرستد.

لغو listener (`Event.cancel`): همان فریم `event` با

```json
"options": { "delivered": false, "rejected": false, "cancel": "<id همان subscribe>" }
```

### گام ۷ — پاسخ‌ها چطور می‌آیند

از `dispatchSocketMessage` در `src/socket/receive.js`. کل پیام `JSON.parse` می‌شود مگر پیشوند `ENC1:`.

| `type` ورودی | همبستگی | کاربرد |
|---|---|---|
| `config` | — | handshake؛ `data` همان config |
| `delivered` | `message.data.id` | رسید به سرور |
| `command-rejected` / `event-rejected` / `list-rejected` / `message-rejected` | `message.metadata.message.id` | خطا |
| `command-event` | `message.data.name` + `metadata.message.id` | نتیجهٔ command (await) |
| `event` | همان | event اشتراک |
| `list` | `message.data.name` + `metadata.message.id` | نتیجهٔ query؛ کلاینت `message.data.data` را resolve می‌کند |
| `command` | `message.data.name` + `message.data.command.id` | کمتر رایج |
| `event-canceled` | `metadata.message.id` | لغو |
| `set-token` | — | نوشتن کوکی: `data.token`، `metadata.expires` (ثانیه)، `metadata.dev` |
| `remove-token` | — | پاک کردن کوکی |
| `set-user` / `remove-user` / `set-roles` / `add-role` / `remove-role` / `set-permissions` / `add-permission` / `remove-permission` | — | هویت سمت سوکت |
| `ping` | — | doc: هر ۳ ثانیه؛ `data` = delay ms |
| `dev` | — | لاگ توسعه |
| سایر | — | `bus.publish(type, data)` |

فریم `delivered` که تست event می‌فرستد:

```json
{
  "type": "delivered",
  "data": { "id": "<id درخواست>", "name": "eventName", "data": { "foo": "bar" } },
  "metadata": { "message": { "id": "<id درخواست>" } }
}
```

فریم reject که تست list می‌فرستد:

```json
{
  "type": "list-rejected",
  "data": {
    "name": "listName",
    "data": { "message": "error-message", "code": "ERROR_CODE" }
  },
  "metadata": { "message": { "id": "<id درخواست>" } }
}
```

فریم list موفق (تست):

```json
{
  "type": "list",
  "data": { "name": "listName", "data": {} },
  "metadata": { "message": { "id": "<id درخواست>" } }
}
```

فریم event (تست + `doc/fa/event.md`):

```json
{
  "type": "event",
  "data": {
    "name": "eventName",
    "data": { "foo": "bar" }
  },
  "metadata": { "message": { "id": "<id همان subscribe>" } }
}
```

شکل کامل‌تر doc برای event غیرminimal:

```json
{
  "type": "event",
  "data": {
    "type": "event",
    "namespace": [{ "name": "ContextName" }, { "name": "AggregateName" }],
    "aggregate": { "id": "<uuid aggregate>" },
    "name": "eventName",
    "id": "<uuid event>",
    "data": { "foo": "bar" }
  },
  "metadata": {
    "date": "2022-04-27T14:21:12.242Z",
    "message": { "id": "<id subscribe کلاینت>" }
  }
}
```

`command-event`: کلاینت `resolve({ ...res.aggregate, ...res.data })` می‌کند.

timeout کلاینت: ۴۰ ثانیه (`commandTimeout` / `listTimeout` در `src/domains/config.js`). کلاینت خودش `rejected.<id>` با `{ data: REQUEST_TIMEOUT_EXCEEDED() }` می‌فرستد:

```json
{
  "type": "message",
  "code": "REQUEST_TIMEOUT_EXCEEDED",
  "message": "request timeout exceeded",
  "level": "warn"
}
```

list روی این کد تا ۳ بار retry می‌کند (`List.retryCounter = 3`).

کدهای سرور از `doc/fa/index.md` (در این ریپو enum ثابت نیست): endpoint اشتباه یا بی‌مجوز → `FORBIDDEN`؛ نیاز به لاگین / توکن مرده → `UNAUTHORIZED`.

### گام ۸ — reconnect

`Socket.reconnect`: تأخیر `[1, 1, 2, 5, 10, 20, 40, 60]` ثانیه، بعد سقف ۶۰. بعد از اتصال دوباره، سرور دوباره `config` می‌فرستد → دوباره `sendToken(config.wss)` → `Event.enable()` همهٔ listenerهای event را cancel و از نو subscribe می‌کند.

برای بستن بدون reconnect، `new-support` مقدار `socket.reconnectTimeoutId` را به sentinel غیرتهی (`-1`) می‌گذارد تا `onclose` دوباره schedule نکند (`createAbrApp.ts` → `disconnectAbrApp`).

`Socket` یک **singleton ماژول** است (`src/socket/index.js` → `export default new Socket()`). فرانت‌ها روی `Abr()` هم `getOrInit` می‌گذارند. دو اتصال موازی از یک فرآیند JS پشتیبانی نمی‌شود.

---

## ۴. پروکسی `$app` (فقط برای فهم فریم، نه برای پورت کامل)

`generateDomains({ config, socket, bus, auth })` یک Proxy برمی‌گرداند. `app.$abr` همان همان شیء است.

تشخیص از `generateNamespace.js`:

- `app.Context.Aggregate.commandName(dataObject)` → command؛ `data` باید object باشد.
- `app.Context.Aggregate('<uuid>').commandName(data)` → همان command روی aggregate موجود.
- اگر آرگومان اول **رشتهٔ UUID** (regex هگز ۸-۴-۴-۴-۱۲) باشد، آن aggregate id است.
- اگر رشتهٔ غیر UUID بدهید، SDK آن را **dataِ command** می‌گیرد — و معمولاً سرور `no authorization` می‌دهد. **هرگز `data` را string نفرستید.**
- `app.Context.Aggregate.lists.listName.where(...).get().send()` → list؛ هر متد زنجیره یک `{ name, args }` است.
- `app.Context.Aggregate.on('name', fn)` یا `.events.name(fn)` → subscribe.

سرویس Python این Proxy را لازم ندارد؛ همان JSON بالا را بفرستد.

---

## ۵. Auth برای اینکه اتصال زنده بماند

1. کوکی مرورگر (اگر از SDK JS استفاده شود): نام درست، مقدار `Bearer <jwt>`، روی localhost **بدون** `domain` و `secure: false`، روی دامنهٔ واقعی `domain=.nipoto.…` و `secure: true`.
2. پیش‌فرض SDK: `cookieAttributes.sameSite = 'secure'` که مقدار معتبر مرورگر نیست. فرانت‌ها `sameSite: 'Lax'` می‌گذارند (`staff/src/utils/abr.js`, `createAbrApp.ts`). سرویس Python اگر کوکی نمی‌نویسد این را نادیده بگیرد؛ اگر نوشت، `Lax` بگذارد نه `'secure'`.
3. روی سیم: `sendToken` بعد از **هر** `config` (اتصال اول و reconnect).
4. تا `tokenVerified` صبر کنید؛ وگرنه command بعدی reject می‌شود.
5. `set-token` از سرور کوکی را با `expires` (unix ثانیه) بازنویسی می‌کند؛ `remove-token` یا rejectِ `sendToken` جلسه را می‌کشد.
6. توکن سرویس AI ≠ توکن Abr.

---

## ۶. سطح مینیمال یک کلاینت Python

کلاینت رسمی Python نیست. حداقل سطح:

1. باز کردن `ws` / `wss`
2. اگر `ws-crypto-server-hello` آمد → CLIENT_HELLO + ENC1
3. منتظر `config`؛ `config.wss` را نگه دارید
4. `sendToken-<wss>` با JWT (قسمت بعد از `Bearer `)
5. `command` / `list` / `event` با UUID پیام
6. incoming: `delivered`، `*-rejected`، `command-event`، `list`، `event`، timeout ۴۰ ثانیه
7. reconnect + دوباره sendToken + دوباره subscribe eventها

JWT را در حافظه نگه دارید؛ به `js-cookie` وابسته نباشید.

---

## ۷. Env و URL محلی (سرویس روی localhost)

`@abr/client` env ندارد. فرانت:

| env | کی خوانده می‌شود | مثال واقعی روی دیسک |
|---|---|---|
| `ABR_URL` | فقط localhost / IP | user-panel `.env`: `b5-back.nipoto.pro`؛ staff: `b2-back.nipoto.pro` |
| `ABR_WS_URL` | فقط new-support، و host باید با `ABR_URL` یکی باشد | `wss://b1-back.nipoto.pro` |

پیشنهاد برای connector آینده روی ماشین توسعه:

```
ABR_URL=b5-back.nipoto.pro
# اتصال:
wss://b5-back.nipoto.pro
```

اگر سرور Abr را خودتان محلی بالا بیاورید (سورسش در این workspace نیست): `ws://localhost:7200` مطابق `doc/fa/index.md`.

از localhost به `wss://b*-back.nipoto.pro` وصل می‌شوید، نه به `ws://` همان host.

---

## ۸. تله‌هایی که کلاینت سرویس را می‌شکنند

1. **`sameSite: 'secure'`** — پیش‌فرض SDK نامعتبر است؛ فرانت `Lax` می‌گذارد.
2. **`token.split(' ')[1]`** — کوکی باید `Bearer <jwt>` باشد. JWT لخت → توکن `undefined`. روی سیم فقط JWT برود، نه کل `Bearer …`.
3. **UUID به‌عنوان aggregate id** — فقط رشتهٔ مطابق regex UUID aggregate است. هر رشتهٔ دیگری dataِ command حساب می‌شود.
4. **`data` را string نفرستید** — `doc/fa/command.md` و `generateNamespace.js`.
5. **singleton** — یک `Socket` در فرآیند JS. سرویس هم یک اتصال را نگه دارد، نه یکی per request بدون فکر.
6. **reconnect بدون re-auth** — بعد از وصل دوباره باید `sendToken` و دوباره enable کردن eventها؛ وگرنه listenerها مرده‌اند.
7. **command قبل از `tokenVerified`** — `Abr()` زود resolve می‌شود.
8. **۱۵ ثانیه بدون `config`** — یعنی URL/فایروال/ENC1 غلط است.
9. **`Socket.close` در SDK** `this._ws` را می‌بندد که وجود ندارد؛ فیلد واقعی `this.ws` است. برای قطع واقعی `ws.close` + جلوگیری از reconnect.
10. **دو مسیر قاطی نشود:** `MAIN_BACKEND=http|fake` در `nipoto-ai` REST/فیک است، Abr نیست.

---

## ۹. `nipoto-ai` امروز

- `app/connectors/__init__.py` فقط `fake` و `http` می‌سازد.
- `pyproject.toml` وابستگی WebSocket / Abr ندارد.
- هیچ ماژول Pythonای `sendToken` یا فریم `command` نمی‌فرستد.

این سند آن شکاف را پر نمی‌کند؛ فقط دستور پخت است.
