#!/usr/bin/env python3
"""
Avaliacao do gemeo digital INTEGRADO ao modelo de pose, pelo navegador (Playwright headless,
Chromium com WebGL por SwiftShader), no mesmo host do servidor (relogio comum).

O servidor (gemeo_digital/servidor/app.py, modo pose, GEMEO_LOG_DIR definido) grava, por sessao
WebSocket, um JSONL com as medicoes de cada quadro; este script so dirige o front-end:

  avaliar    percorre o conjunto de TESTE inteiro em malha fechada (fps=0: o proximo quadro so sai
             quando o front-end confirma que desenhou o anterior) nas duas cameras; depois mede a taxa
             sustentada com taxa-alvo fixa (2 e 5 quadros/s) por N quadros.
  capturas   capturas de tela de quadros escolhidos (baixo erro, falha), com aquecimento para o grafico.
  varredura  uma imagem por quadro de uma faixa da sequencia (para o GIF/MP4 via ffmpeg).

Uso (container cerise26_gemeo_playwright, --network host):
  python avaliar_gemeo.py avaliar   --url http://127.0.0.1:8091 --saida /integ/resultados/cliente_avaliacao.json
  python avaliar_gemeo.py capturas  --url ... --escolhas /integ/resultados/escolhas_capturas.json --pasta /integ/evidencias
  python avaliar_gemeo.py varredura --url ... --inicio 40 --n 60 --pasta /integ/varredura
"""
import argparse
import json
import os
import statistics as st
import time

from playwright.sync_api import sync_playwright

# GEMEO_GL=gpu (padrao): WebGL acelerado na GPU do GB10 via ANGLE/EGL (container com --gpus all e
# NVIDIA_DRIVER_CAPABILITIES=all; continua headless, sem tocar na tela fisica). GEMEO_GL=swiftshader:
# rasterizacao por software na CPU (pior caso, ~600 ms por quadro a 1600x1000).
if os.environ.get("GEMEO_GL", "gpu") == "gpu":
    ARGS_CHROMIUM = ["--use-gl=angle", "--use-angle=gl-egl", "--ignore-gpu-blocklist", "--enable-gpu", "--enable-webgl"]
else:
    ARGS_CHROMIUM = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                     "--ignore-gpu-blocklist", "--enable-webgl"]


def abrir(nav, url, qs, vp=(1600, 1000)):
    pag = nav.new_page(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=1)
    console = []
    pag.on("console", lambda m: console.append("%s: %s" % (m.type, m.text)))
    pag.on("pageerror", lambda e: console.append("pageerror: %s" % e))
    t0 = time.time()
    pag.goto(url + "/" + qs, wait_until="networkidle")
    pag.wait_for_function("window.__gemeo && window.__gemeo.pronto === true", timeout=180000)
    return pag, console, time.time() - t0


def resumo(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    return {"n": len(v), "media": st.mean(v), "mediana": st.median(v), "p95": v[int(0.95 * (len(v) - 1))],
            "max": v[-1], "min": v[0]}


def avaliar(a):
    rel = {"url": a.url, "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "sessoes": []}
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True, args=ARGS_CHROMIUM)
        info = None
        planos = [(cam, 0.0, a.n_max) for cam in a.cameras] + [("camera_frontal", f, a.n_fps) for f in a.fps_fixos]
        for cam, fps, n in planos:
            pag, console, t_carga = abrir(nav, a.url, "?modo=lado&vista=livre&camera=%s&fps=%g&ir=0" % (cam, fps))
            fps_pagina = pag.evaluate("document.getElementById('sel-fps').value")
            assert float(fps_pagina) == fps, "taxa nao aplicada na pagina: %r != %r" % (fps_pagina, fps)
            if info is None:
                info = pag.evaluate("fetch('/api/info').then(r => r.json())")
            alvo = n or info["n_quadros"]
            t0 = time.time()
            pag.wait_for_function("window.__gemeo.acks >= %d" % alvo, timeout=int(alvo * 4000) + 60000, polling=250)
            dur = time.time() - t0
            est = pag.evaluate("({acks: window.__gemeo.acks, quadros: window.__gemeo.quadros, erros: window.__gemeo.erros,"
                               " render_ms: window.__gemeo.render_ms})")
            webgl = pag.evaluate("""() => { const c = document.querySelector('#viewport canvas');
                const gl = c.getContext('webgl2') || c.getContext('webgl');
                const ext = gl && gl.getExtension('WEBGL_debug_renderer_info');
                return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : null; }""")
            pag.close()
            s = {"camera": cam, "fps_alvo": fps or "malha fechada", "quadros_alvo": alvo, "duracao_s": dur,
                 "gl": os.environ.get("GEMEO_GL", "gpu"),
                 "acks": est["acks"], "quadros_recebidos": est["quadros"], "fps_cliente": est["acks"] / dur,
                 "tempo_ate_pronto_s": t_carga, "recebido_ate_desenhado_ms": resumo(est["render_ms"]),
                 "erros_js": est["erros"], "console": console[-10:], "webgl": webgl}
            rel["sessoes"].append(s)
            print("%-16s fps_alvo=%-14s %4d quadros em %6.1f s -> %.2f quadros/s (cliente) | recebido->desenhado mediana %.1f ms"
                  % (cam, s["fps_alvo"], est["acks"], dur, s["fps_cliente"],
                     (s["recebido_ate_desenhado_ms"] or {}).get("mediana", float("nan"))), flush=True)
            time.sleep(1.0)  # o servidor fecha o JSONL da sessao
        nav.close()
    rel["fim"] = time.strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    json.dump(rel, open(a.saida, "w"), indent=2, ensure_ascii=False)


def esperar_quadro(pag, idx, acks0, timeout=60000):
    pag.wait_for_function("window.__gemeo.ultimo && window.__gemeo.ultimo.idx === %d && window.__gemeo.acks > %d"
                          % (idx, acks0), timeout=timeout, polling=100)


def capturas(a):
    esc = json.load(open(a.escolhas))
    out = {}
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True, args=ARGS_CHROMIUM)
        for c in esc["capturas"]:
            n = c["n_quadros"]
            ini = (c["idx"] - a.aquecimento) % n
            qs = "?modo=%s&vista=%s&camera=%s&fps=0&ir=%d" % (c["modo"], c["vista"], c["camera"], ini)
            pag, console, _ = abrir(nav, a.url, qs)
            pag.wait_for_function("window.__gemeo.acks >= %d" % a.aquecimento, timeout=300000, polling=200)
            pag.evaluate("window.__gemeoCmd({cmd: 'pausar'})")
            pag.wait_for_timeout(600)
            acks0 = pag.evaluate("window.__gemeo.acks")
            pag.evaluate("window.__gemeoCmd({cmd: 'ir', idx: %d})" % c["idx"])
            esperar_quadro(pag, c["idx"], acks0)
            pag.wait_for_timeout(1200)
            arq = os.path.join(a.pasta, c["arquivo"])
            pag.screenshot(path=arq)
            est = pag.evaluate("JSON.parse(JSON.stringify({ultimo: window.__gemeo.ultimo, efetuador: window.__gemeo.efetuador,"
                               " malhas: window.__gemeo.malhas, erros: window.__gemeo.erros}))")
            out[c["arquivo"]] = {"pedido": c, "estado": est, "console": console[-5:]}
            print(c["arquivo"], "->", est["ultimo"], flush=True)
            pag.close()
        nav.close()
    json.dump(out, open(os.path.join(a.pasta, "capturas_a12_integracao.json"), "w"), indent=2, ensure_ascii=False)


def varredura(a):
    os.makedirs(a.pasta, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch(headless=True, args=ARGS_CHROMIUM)
        qs = "?modo=%s&vista=%s&camera=%s&fps=0&ir=%d&pausar=1" % (a.modo, a.vista, a.camera, a.inicio)
        pag, console, _ = abrir(nav, a.url, qs, vp=(a.largura, a.altura))
        pag.wait_for_function("window.__gemeo.acks >= 1", timeout=60000)
        info = pag.evaluate("fetch('/api/info').then(r => r.json())")
        for k in range(a.n):
            idx = (a.inicio + k) % info["n_quadros"]
            acks0 = pag.evaluate("window.__gemeo.acks")
            pag.evaluate("window.__gemeoCmd({cmd: 'ir', idx: %d})" % idx)
            esperar_quadro(pag, idx, acks0)
            pag.wait_for_timeout(250)  # imagem da camera (data URL) decodificada
            pag.screenshot(path=os.path.join(a.pasta, "q_%03d.png" % k))
        print("varredura: %d quadros em %s" % (a.n, a.pasta), flush=True)
        pag.close()
        nav.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["avaliar", "capturas", "varredura"])
    ap.add_argument("--url", default="http://127.0.0.1:8091")
    ap.add_argument("--saida", default="/integ/resultados/cliente_avaliacao.json")
    ap.add_argument("--cameras", nargs="*", default=["camera_frontal", "camera_diagonal"])
    ap.add_argument("--fps_fixos", nargs="*", type=float, default=[2.0, 5.0])
    ap.add_argument("--n_fps", type=int, default=60)
    ap.add_argument("--n_max", type=int, default=None, help="quadros por camera em malha fechada (padrao: todos)")
    ap.add_argument("--escolhas", default="/integ/resultados/escolhas_capturas.json")
    ap.add_argument("--pasta", default="/integ/evidencias")
    ap.add_argument("--aquecimento", type=int, default=45)
    ap.add_argument("--inicio", type=int, default=0)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--camera", default="camera_frontal")
    ap.add_argument("--modo", default="sobreposto")
    ap.add_argument("--vista", default="camera")
    ap.add_argument("--largura", type=int, default=1440)
    ap.add_argument("--altura", type=int, default=900)
    a = ap.parse_args()
    {"avaliar": avaliar, "capturas": capturas, "varredura": varredura}[a.acao](a)


if __name__ == "__main__":
    main()
