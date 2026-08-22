"""
Round 3: inspect the HTML structure around a real imot.bg listing card on
the Sofia sales page, to figure out how to extract price/sqm/area/photo.
"""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="bg-BG",
        )
        page = context.new_page()
        page.goto("https://www.imot.bg/obiavi/prodazhbi/grad-sofiya", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        # Find the first real listing link and walk up its ancestors, printing
        # each ancestor's outerHTML length and text, to find the smallest
        # container that holds price + size + area for that one listing.
        info = page.evaluate("""
        () => {
          const links = Array.from(document.querySelectorAll('a[href*="/obiava-"]'));
          if (links.length === 0) return null;
          const link = links[0];
          const results = [];
          let node = link;
          for (let i = 0; i < 8 && node.parentElement; i++) {
            node = node.parentElement;
            results.push({
              tag: node.tagName,
              className: node.className,
              textLen: node.innerText.length,
              text: node.innerText.slice(0, 400),
            });
          }
          return { href: link.getAttribute('href'), linkText: link.innerText.slice(0,200), ancestors: results };
        }
        """)
        import json
        print(json.dumps(info, ensure_ascii=False, indent=2))

        browser.close()


if __name__ == "__main__":
    main()
