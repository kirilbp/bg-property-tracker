from collections import Counter
from playwright.sync_api import sync_playwright
from PIL import Image
import io

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

URL = "https://www.imot.bg/obiava-1c178744086909362-prodava-tristaen-apartament-oblast-burgas-k-k-slanchev-bryag"

PIN_RED = (234, 67, 53)


def color_dist(c1, c2):
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="bg-BG", viewport={"width": 1400, "height": 1200})
    page = context.new_page()

    print(f"Navigating to {URL}")
    page.goto(URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    for _ in range(20):
        page.mouse.wheel(0, 800)
        page.wait_for_timeout(400)
    try:
        page.evaluate("() => AvrPricesShowGmap()")
    except Exception as e:
        print(f"trigger call failed: {e}")
    page.wait_for_timeout(3000)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass

    loc = page.get_by_text("Местоположение", exact=False).first
    if loc.count() > 0:
        loc.scroll_into_view_if_needed()
        page.wait_for_timeout(1000)
        png_bytes = page.screenshot()
        print(f"screenshot captured, {len(png_bytes)} bytes")

        img = Image.open(io.BytesIO(png_bytes)).convert("RGB")
        w, h = img.size
        print(f"image size: {w}x{h}")

        pixels = list(img.getdata())
        color_counts = Counter(pixels)
        print(f"distinct colors in screenshot: {len(color_counts)}")
        most_common = color_counts.most_common(5)
        print("5 most common colors (color, count):", most_common)

        red_matches = []
        for i in range(0, len(pixels), 7):
            if color_dist(pixels[i], PIN_RED) < 30:
                x = (i % w)
                y = (i // w)
                red_matches.append((x, y))
        print(f"pixels resembling Google Maps red pin color: {len(red_matches)}")
        if red_matches:
            print("sample matching pixel coordinates:", red_matches[:10])
    else:
        print("could not find Местоположение heading to screenshot near")

    browser.close()
