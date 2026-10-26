#!/usr/bin/env python3
"""
Capturas de tela do front-end do Gemeo Digital com Playwright (Chromium
headless, WebGL por SwiftShader) e VERIFICACAO de que as malhas aparecem:

  1. estado JS (window.__gemeo): URDFs carregados, n. de malhas por braco,
     erros de carregamento, quadros recebidos pelo WebSocket;
  2. analise de pixels do canvas WebGL: fracao de pixels "de braco"
     (aluminio claro ou verde do fantasma) contra o fundo/chao escuros.

Uso (container mcr.microsoft.com/playwright/python, --network host):
  python capturar.py --url http://127.0.0.1:8091 --saida /repo/evidencias --cenarios lado sobreposto
"""
import argparse
import base64
import io
import json
import os
import time

from playwright.sync_api import sync_playwright

CENARIOS = {
    "lado": ("a12_gemeo_lado_a_lado.png", "?modo=lado&vista=livre&camera=camera_frontal&fps=2", 6),
    "sobreposto": ("a12_gemeo_sobreposto_vista_camera.png",
                   "?modo=sobreposto&vista=camera&camera=camera_frontal&fps=2", 6),
    "diagonal": ("a12_gemeo_sobreposto_camera_diagonal.png",
                 "?modo=sobreposto&vista=camera&camera=camera_diagonal&fps=2", 6),
    "ruido": ("a12_gemeo_demo_predictor_ruido.png", "?modo=lado&vista=livre&camera=camera_frontal&fps=10", 70),
    "ruido_sobreposto": ("a12_gemeo_demo_ruido_sobreposto.png",
                         "?modo=sobreposto&vista=livre&camera=camera_diagonal&fps=10", 70),
}


def analisar_canvas(png_bytes):
    from PIL import Image
    import numpy as np
    a = np.asarray(Image.open(io.BytesIO(png_bytes)).convert("RGB")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    aluminio = (lum > 105) & (abs(r - b) < 40)   # fundo/chao/grade da cena tem lum < 100
    verde = (g > r + 25) & (g > b + 5) & (g > 70)
    return {"largura": int(a.shape[1]), "altura": int(a.shape[0]),
            "frac_pixels_aluminio": float(aluminio.mean()), "frac_pixels_verde_gemeo": float(verde.mean()),
            "cores_distintas": int(len(np.unique(a.reshape(-1, 3)[::37], axis=0)))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8091")
    ap.add_argument("--saida", default="/repo/evidencias")
    ap.add_argument("--relatorio", default="/repo/resultados/capturas_verificacao.json")
    ap.add_argument("--cenarios", nargs="+", default=["lado", "sobreposto", "diagonal"])
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    try:
        rel = json.load(open(a.relatorio))
    except Exception:
        rel = {}
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True, args=[
            "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            "--ignore-gpu-blocklist", "--enable-webgl"])
        for nome in a.cenarios:
            arq, qs, min_quadros = CENARIOS[nome]
            pag = nav.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
            console = []
            pag.on("console", lambda m: console.append("%s: %s" % (m.type, m.text)))
            pag.on("pageerror", lambda e: console.append("pageerror: %s" % e))
            t0 = time.time()
            pag.goto(a.url + "/" + qs, wait_until="networkidle")
            pag.wait_for_function("window.__gemeo && window.__gemeo.pronto === true", timeout=120000)
            t_carga = time.time() - t0
            pag.wait_for_function("window.__gemeo.quadros >= %d" % min_quadros, timeout=180000)
            pag.wait_for_timeout(1200)
            est = pag.evaluate("JSON.parse(JSON.stringify(window.__gemeo))")
            webgl = pag.evaluate("""() => { const c = document.querySelector('#viewport canvas');
                const gl = c.getContext('webgl2') || c.getContext('webgl');
                const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
                return {renderer: ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : (gl ? gl.getParameter(gl.RENDERER) : null),
                        versao: gl ? gl.getParameter(gl.VERSION) : null}; }""")
            efe = est.get("efetuador") or {}
            import math
            def dist(u, v):
                return math.dist(u, v) if u and v else None
            fk_js = {"ref_vs_servidor_m": dist(efe.get("ref"), efe.get("servidor_gt")),
                     "gemeo_vs_servidor_m": dist(efe.get("gemeo"), efe.get("servidor_pred"))}
            dataurl = pag.evaluate("document.querySelector('#viewport canvas').toDataURL('image/png')")
            canvas = analisar_canvas(base64.b64decode(dataurl.split(",", 1)[1]))
            pag.screenshot(path=os.path.join(a.saida, arq))
            ok = (est.get("robos") == 2 and est["malhas"]["ref"] > 0 and est["malhas"]["gemeo"] > 0
                  and not est.get("erros")
                  and canvas["frac_pixels_aluminio"] + canvas["frac_pixels_verde_gemeo"] > 0.003)
            rel[nome] = {"arquivo": arq, "url": a.url + "/" + qs, "tempo_ate_pronto_s": round(t_carga, 2),
                         "estado_js": est, "fk_threejs_vs_python": fk_js, "webgl": webgl, "canvas": canvas,
                         "console": console[-15:], "malhas_visiveis": bool(ok)}
            print(nome, "->", arq, "| malhas", est["malhas"], "| canvas aluminio %.3f verde %.3f" % (
                canvas["frac_pixels_aluminio"], canvas["frac_pixels_verde_gemeo"]),
                "| fk js-py", fk_js, "| quadros", est["quadros"], "| erros", est.get("erros"), "| OK" if ok else "| FALHA", flush=True)
            pag.close()
        nav.close()
    with open(a.relatorio, "w") as f:
        json.dump(rel, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
