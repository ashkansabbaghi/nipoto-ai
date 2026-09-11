# Knowledge base data

`nipoto_kb.json` is a **synthetic** knowledge base (T0.2), written to mirror Nipoto's real FAQ
categories (`website/api/FAQ.js`). Numbers, limits and procedures are **placeholders**,
not official policy. Swap in the real export when it arrives; nothing else changes.

| | count |
|---|---|
| FAQ, public | 36 |
| help docs, public (h2/h3 sections) | 5 |
| internal staff guidelines (doc 3 + faq 1) | 4 |
| **total** | **45** |

Topics: احراز هویت (faq_1–4)، واریز (faq_5–10، doc_4)، برداشت (faq_11–15، doc_1)،
معاملات (faq_16–19، doc_3)، بازار عمده (faq_20)، حساب و امنیت (faq_21–25، 34، 36، doc_5)،
رفرال (faq_26–27)، API (faq_28–29)، حسابداری (faq_30–31)، پشتیبانی/پیشنهادات (faq_32–33)،
حقوقی (faq_35)، شروع کار (doc_2).

## Real data

The FAQ source of truth is the main backend (`Support.FAQ`, grouped by department). Put a
JSON dump in `data/kb/raw/` and convert it:

```
uv run python scripts/convert_kb.py data/kb/raw/faqs.json -o data/kb/nipoto_kb.json
uv run python scripts/convert_kb.py data/kb/nipoto_kb.json --check   # validate + stats
```
