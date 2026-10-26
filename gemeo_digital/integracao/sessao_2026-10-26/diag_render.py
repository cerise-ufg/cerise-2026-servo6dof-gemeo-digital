import json, sys, time
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8091"
extra = sys.argv[2] if len(sys.argv) > 2 else ""
with sync_playwright() as p:
    for args in (["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl"],):
        nav = p.chromium.launch(headless=True, args=args)
        pag = nav.new_page(viewport={"width": 1600, "height": 1000})
        pag.goto(url + "/?modo=lado&vista=livre&fps=1&pausar=1" + extra, wait_until="networkidle")
        pag.wait_for_function("window.__gemeo && window.__gemeo.pronto === true", timeout=180000)
        pag.wait_for_timeout(2000)
        r = pag.evaluate("""() => new Promise(ok => { const t = []; const f = ts => { t.push(performance.now()); if (t.length < 15) requestAnimationFrame(f); else ok(t); }; requestAnimationFrame(f); })""")
        d = [b - a for a, b in zip(r, r[1:])]
        print("args", args[:2], "intervalos rAF ms:", [round(x) for x in d])
        nav.close()
