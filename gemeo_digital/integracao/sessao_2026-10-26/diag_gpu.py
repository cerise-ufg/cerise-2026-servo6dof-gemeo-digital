import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8091"
CONFIGS = {
    "egl": ["--use-gl=angle", "--use-angle=gl-egl", "--ignore-gpu-blocklist", "--enable-gpu", "--enable-webgl"],
    "vulkan": ["--use-gl=angle", "--use-angle=vulkan", "--enable-features=Vulkan", "--ignore-gpu-blocklist", "--enable-gpu", "--enable-webgl"],
    "egl2": ["--use-gl=egl", "--ignore-gpu-blocklist", "--enable-gpu", "--enable-webgl"],
}
with sync_playwright() as p:
    for nome, args in CONFIGS.items():
        try:
            nav = p.chromium.launch(headless=True, args=args)
            pag = nav.new_page(viewport={"width": 1600, "height": 1000})
            pag.goto(url + "/?modo=lado&vista=livre&fps=1&pausar=1", wait_until="networkidle")
            pag.wait_for_function("window.__gemeo && window.__gemeo.pronto === true", timeout=120000)
            rend = pag.evaluate("""() => { const c = document.querySelector('#viewport canvas');
                const gl = c.getContext('webgl2') || c.getContext('webgl');
                const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
                return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null; }""")
            pag.wait_for_timeout(1500)
            r = pag.evaluate("""() => new Promise(ok => { const t = []; const f = ts => { t.push(performance.now()); if (t.length < 15) requestAnimationFrame(f); else ok(t); }; requestAnimationFrame(f); })""")
            d = [round(b - a) for a, b in zip(r, r[1:])]
            print(nome, "|", rend, "| rAF ms:", d, flush=True)
            nav.close()
        except Exception as e:
            print(nome, "FALHOU", str(e)[:300], flush=True)
