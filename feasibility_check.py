"""
Round 2: inspect the full search form on imoti.bg's homepage - action/method,
all fields (district_id, type_id, deal-type toggle for sales vs rent), and
the actual submit control (may be icon-only, hence missed by text-based
button search in round 1).
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

        print("--- forms on page ---")
        forms = page.evaluate("""
        () => Array.from(document.querySelectorAll('form')).map(f => ({
          id: f.id, action: f.action, method: f.method,
          html_snippet: f.outerHTML.slice(0, 3000)
        }))
        """)
        for i, f in enumerate(forms):
            print(f"FORM #{i}: id={f['id']} action={f['action']} method={f['method']}")
            print(f['html_snippet'])
            print("-" * 80)

        print("\n--- ALL clickable elements with no/short text (icon buttons, submit inputs, links) near the district_id select ---")
        near = page.evaluate("""
        () => {
          const sel = document.getElementById('district_id');
          if (!sel) return 'no district_id select found';
          let container = sel.closest('form') || sel.parentElement.parentElement.parentElement;
          const clickable = container.querySelectorAll('button, a, input[type=submit], input[type=button], [onclick], [role=button]');
          return Array.from(clickable).map(el => ({
            tag: el.tagName,
            type: el.type || '',
            cls: el.className && el.className.toString ? el.className.toString().slice(0,80) : '',
            text: (el.textContent || el.value || '').trim().slice(0, 40),
            href: el.href || ''
          }));
        }
        """)
        for n in near:
            print(n)

        browser.close()


if __name__ == "__main__":
    main()
