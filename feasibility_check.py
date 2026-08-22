"""
Round 5: inspect all <img> tags inside a real listing card to find the
actual photo thumbnail (not the "TOP" ranking badge icon).
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
          const out = [];
          for (let i = 0; i < Math.min(3, links.length); i++) {
            const link = links[i];
            let node = link;
            for (let j = 0; j < 4 && node.parentElement; j++) node = node.parentElement;
            const imgs = Array.from(node.querySelectorAll('img')).map(img => ({
              src: img.getAttribute('src'),
              dataSrc: img.getAttribute('data-src'),
              className: img.className,
              width: img.getAttribute('width'),
              height: img.getAttribute('height'),
            }));
            out.push({ href: link.getAttribute('href'), containerClass: node.className, imgs });
          }
          return out;
        }
        """)
        print(json.dumps(info, ensure_ascii=False, indent=2))

        browser.close()


if __name__ == "__main__":
    main()
