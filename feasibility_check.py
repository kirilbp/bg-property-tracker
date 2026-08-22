"""
Round 4: inspect the HTML structure around a REAL classified listing card
(not a "new building" promo card) on imot.bg's Sofia sales page.
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
        page.goto("https://www.imot.bg/obiavi/prodazhbi/grad-sofiya", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)

        info = page.evaluate(r"""
        () => {
          const idRe = /\/obiava-\d[a-z]\d{10,}-/;
          const links = Array.from(document.querySelectorAll('a[href*="/obiava-"]'))
            .filter(a => idRe.test(a.getAttribute('href')));
          if (links.length === 0) return { error: 'no matching links', count: 0 };

          const link = links[0];
          const results = [];
          let node = link;
          for (let i = 0; i < 6 && node.parentElement; i++) {
            node = node.parentElement;
            const priceMatches = (node.innerText.match(/[\d\s]{3,10}\s?€/g) || []);
            results.push({
              tag: node.tagName,
              className: node.className,
              textLen: node.innerText.length,
              priceMentions: priceMatches.length,
              text: node.innerText.slice(0, 500),
            });
          }
          return { href: link.getAttribute('href'), totalMatchingLinks: links.length, ancestors: results };
        }
        """)
        print(json.dumps(info, ensure_ascii=False, indent=2))

        browser.close()


if __name__ == "__main__":
    main()
