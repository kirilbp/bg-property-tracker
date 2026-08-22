"""
Round 4: test the combined Sofia + sales category URL, and inspect one
real listing card's HTML structure for price/sqm/area extraction.
"""

import json
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
        url = "https://www.olx.bg/nedvizhimi-imoti/prodazhbi/oblast-sofiya-grad/"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        print("title:", page.title())
        print("final url:", page.url)

        ad_links = page.eval_on_selector_all(
            "a[href*='/d/ad/']", "els => Array.from(new Set(els.map(e => e.getAttribute('href'))))"
        )
        print(f"unique ad links: {len(ad_links)}")
        for l in ad_links[:15]:
            print("  ", l)

        # inspect ancestor structure of the first ad link to find price/sqm/area
        info = page.evaluate("""
        () => {
          const link = document.querySelector("a[href*='/d/ad/']");
          if (!link) return null;
          let node = link;
          const results = [];
          for (let i = 0; i < 6 && node.parentElement; i++) {
            node = node.parentElement;
            results.push({
              tag: node.tagName,
              className: (node.className || '').toString().slice(0,80),
              textLen: node.innerText.length,
              text: node.innerText.slice(0, 300),
            });
          }
          return { href: link.getAttribute('href'), ancestors: results };
        }
        """)
        print("\nfirst ad card ancestor structure:")
        print(json.dumps(info, ensure_ascii=False, indent=2))

        browser.close()


if __name__ == "__main__":
    main()
