"""Open the baked viewer in headless Chromium, wait for the first model, report console errors, save a screenshot.
  python check_viewer.py <viewer.html> <screenshot_base>   (writes <screenshot_base>_<theme>.png)
"""
import sys

from playwright.sync_api import sync_playwright

html, shot = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    for scheme in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 1200, "height": 900}, color_scheme=scheme)
        pg = ctx.new_page()
        logs = []
        pg.on("console", lambda m: logs.append(f"{m.type}: {m.text[:200]}"))
        pg.on("pageerror", lambda e: logs.append(f"PAGEERROR: {str(e)[:300]}"))
        pg.goto("file://" + html)
        try:
            pg.wait_for_function("document.body.dataset.loaded", timeout=45000)
            ok = True
        except Exception as e:
            ok = False
        pg.wait_for_timeout(1500)
        nogl = pg.evaluate("getComputedStyle(document.getElementById('nogl')).display")
        txt = pg.evaluate("document.getElementById('nogl').textContent")
        # does the canvas actually contain non-background pixels?
        px = pg.evaluate("""() => { const c = document.getElementById('gl'); const t = document.createElement('canvas');
            t.width = c.width; t.height = c.height; const x = t.getContext('2d'); x.drawImage(c, 0, 0);
            const d = x.getImageData(0, 0, t.width, t.height).data; let n = 0;
            for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return [t.width, t.height, n]; }""")
        print(f"[{scheme}] model loaded: {ok}; nogl display: {nogl}; canvas {px[0]}x{px[1]}, drawn pixels: {px[2]}")
        if nogl != "none": print("   nogl text:", txt)
        for l in logs[:8]: print("   ", l)
        pg.screenshot(path=f"{shot}_{scheme}.png", full_page=True)
        ctx.close()
    b.close()
