"""
Round 1: reconnaissance on imoti.bg's homepage/search UI to find the location
dropdown's actual DOM structure (buttons, list items, data attributes) so we
can script real clicks on it (open dropdown -> click "Sofia" -> click submit).
"""

from playwright.sync_api import sync_playwright

URL = "https://imoti.bg"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="bg-BG")
        page = context.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        print("page title:", page.title())
        print("page url:", page.url)

        # Dump all elements that look like a location/city selector.
        print("\n--- elements mentioning 'sofia' / 'sofiya' / 'grad' / 'lokation' / 'location' (case-insensitive) in text or attrs ---")
        candidates = page.evaluate("""
        () => {
          const out = [];
          const all = document.querySelectorAll('*');
          const kw = /sofia|sofiya|софия|grad|lokat|location|city|населено/i;
          for (const el of all) {
            const text = (el.textContent || '').trim();
            const attrs = Array.from(el.attributes || []).map(a => a.name + '=' + a.value).join(' ');
            if ((text.length > 0 && text.length < 60 && kw.test(text)) || kw.test(attrs)) {
              out.push({
                tag: el.tagName,
                id: el.id,
                cls: el.className && el.className.toString ? el.className.toString().slice(0,80) : '',
                text: text.slice(0, 60),
                attrs: attrs.slice(0, 150)
              });
            }
            if (out.length >= 60) break;
          }
          return out;
        }
        """)
        for c in candidates:
            print(c)

        print("\n--- all <select> elements ---")
        selects = page.evaluate("""
        () => Array.from(document.querySelectorAll('select')).map(s => ({
          id: s.id, name: s.name,
          options: Array.from(s.options).slice(0, 10).map(o => o.value + '|' + o.text)
        }))
        """)
        for s in selects:
            print(s)

        print("\n--- all <button> and role=button elements with short text ---")
        buttons = page.evaluate("""
        () => Array.from(document.querySelectorAll('button, [role=button], input[type=submit]')).map(b => ({
          tag: b.tagName, id: b.id,
          cls: b.className && b.className.toString ? b.className.toString().slice(0,80) : '',
          text: (b.textContent || b.value || '').trim().slice(0, 40)
        })).filter(b => b.text.length > 0 && b.text.length < 40)
        """)
        for b in buttons[:40]:
            print(b)

        browser.close()


if __name__ == "__main__":
    main()
