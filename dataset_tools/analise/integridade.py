#!/usr/bin/env python3
"""
Verificacao de integridade do dataset (a partir do index.csv):
  - todo arquivo referenciado existe e tem tamanho > 0;
  - decodificacao COMPLETA de cada PNG (PIL .load()), dimensoes 1280x720,
    modo esperado (RGB para cor/segmentacao, inteiro 16/32 bits para profundidade);
  - estatisticas por imagem: RGB (media/desvio - detecta quadro vazio),
    profundidade (fracao sem retorno, min/max em mm), segmentacao (rotulos
    presentes, fracao de pixels do braco = rotulo 0 com profundidade valida);
  - quadros RGB duplicados entre poses diferentes (hash MD5 do arquivo) - detecta
    captura de quadro "velho".

Saidas: <meta>/integridade_por_imagem.csv, <meta>/integridade.json (+ copia do
resumo em resultados/). Uso:
  python3 dataset_tools/analise/integridade.py --dataset /dataset --meta /dataset_meta --proc 6 [--amostra N]
"""
import argparse
import csv
import hashlib
import json
import os
import time
from multiprocessing import Pool

import numpy as np

CAMERAS = ["camera_frontal", "camera_diagonal"]
MODS = ["image", "depth", "segmentation_labels_map"]
RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verifica_pose(args):
    from PIL import Image
    pasta, lin = args
    i = int(lin["id"])
    saida = []
    deps = {}
    for c in CAMERAS:
        dep = None
        for m in ["depth", "image", "segmentation_labels_map"]:
            f = lin["%s_%s_arquivo" % (c, m)]
            p = os.path.join(pasta, f)
            r = {"id": i, "camera": c, "modalidade": m, "arquivo": f, "existe": os.path.exists(p),
                 "bytes": os.path.getsize(p) if os.path.exists(p) else 0, "decodifica": False,
                 "largura": "", "altura": "", "modo": "", "md5": "", "media": "", "desvio": "",
                 "frac_sem_retorno": "", "min_mm": "", "max_mm": "", "rotulos": "", "frac_braco": ""}
            if r["existe"] and r["bytes"] > 0:
                try:
                    with open(p, "rb") as fh:
                        dados = fh.read()
                    if m == "image":
                        r["md5"] = hashlib.md5(dados).hexdigest()
                    im = Image.open(p)
                    im.load()
                    a = np.asarray(im)
                    r.update(decodifica=True, largura=im.width, altura=im.height, modo=im.mode)
                    if m == "image":
                        r["media"] = round(float(a.mean()), 2)
                        r["desvio"] = round(float(a.std()), 2)
                    elif m == "depth":
                        dep = a
                        nz = a[a > 0]
                        r["frac_sem_retorno"] = round(float((a == 0).mean()), 5)
                        r["min_mm"] = int(nz.min()) if nz.size else 0
                        r["max_mm"] = int(nz.max()) if nz.size else 0
                    else:
                        s = a[:, :, 0] if a.ndim == 3 else a
                        if a.ndim == 3 and not (np.array_equal(a[:, :, 0], a[:, :, 1])
                                                and np.array_equal(a[:, :, 0], a[:, :, 2])):
                            r["modo"] += "(canais diferentes)"
                        u = np.unique(s)
                        r["rotulos"] = " ".join(str(int(x)) for x in u)
                        braco = (s == 0) if dep is None else ((s == 0) & (dep > 0))
                        r["frac_braco"] = round(float(braco.mean()), 5)
                except Exception as e:
                    r["erro"] = str(e)[:200]
            saida.append(r)
        deps[c] = dep
    return saida


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/dataset")
    ap.add_argument("--meta", default="/dataset_meta")
    ap.add_argument("--proc", type=int, default=6)
    ap.add_argument("--amostra", type=int, default=0, help="0 = todas as poses")
    a = ap.parse_args()
    t0 = time.time()
    linhas = list(csv.DictReader(open(os.path.join(a.meta, "index.csv"))))
    if a.amostra and a.amostra < len(linhas):
        rng = np.random.default_rng(3)
        linhas = [linhas[k] for k in sorted(rng.choice(len(linhas), a.amostra, replace=False))]
    with Pool(a.proc) as pool:
        res = [r for rs in pool.imap_unordered(verifica_pose, [(a.dataset, l) for l in linhas], chunksize=8)
               for r in rs]
    res.sort(key=lambda r: (r["id"], r["camera"], r["modalidade"]))
    campos = list(res[0].keys()) + (["erro"] if "erro" not in res[0] else [])
    with open(os.path.join(a.meta, "integridade_por_imagem.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        w.writerows(res)

    esperado_modo = {"image": {"RGB"}, "segmentation_labels_map": {"RGB"}, "depth": {"I", "I;16", "I;16B"}}
    probl = []
    for r in res:
        motivo = []
        if not r["existe"]:
            motivo.append("nao existe")
        elif r["bytes"] == 0:
            motivo.append("vazio")
        elif not r["decodifica"]:
            motivo.append("nao decodifica: " + r.get("erro", ""))
        else:
            if (r["largura"], r["altura"]) != (1280, 720):
                motivo.append("dimensao %sx%s" % (r["largura"], r["altura"]))
            if r["modo"] not in esperado_modo[r["modalidade"]]:
                motivo.append("modo " + r["modo"])
            if r["modalidade"] == "image" and r["desvio"] != "" and r["desvio"] < 2:
                motivo.append("imagem quase uniforme")
            if r["modalidade"] == "segmentation_labels_map" and r["frac_braco"] != "" and r["frac_braco"] < 0.002:
                motivo.append("braco ausente na segmentacao")
        if motivo:
            probl.append({"id": r["id"], "camera": r["camera"], "modalidade": r["modalidade"], "motivos": motivo})

    md5 = {}
    for r in res:
        if r["md5"]:
            md5.setdefault(r["md5"], []).append((r["id"], r["camera"]))
    dup = [v for v in md5.values() if len({x[0] for x in v}) > 1]

    def est(vals):
        v = np.array([float(x) for x in vals if x != ""])
        return {"media": float(v.mean()), "min": float(v.min()), "max": float(v.max()),
                "p5": float(np.percentile(v, 5)), "p95": float(np.percentile(v, 95))} if v.size else None

    rot = {}
    for r in res:
        if r["modalidade"] == "segmentation_labels_map" and r["rotulos"]:
            rot[r["rotulos"]] = rot.get(r["rotulos"], 0) + 1
    resumo = {
        "n_poses_verificadas": len(linhas), "n_imagens_verificadas": len(res),
        "modo": "todas" if not a.amostra else "amostra de %d poses" % a.amostra,
        "n_existem": sum(r["existe"] for r in res), "n_decodificam": sum(r["decodifica"] for r in res),
        "n_problemas": len(probl), "problemas_exemplos": probl[:30],
        "n_quadros_rgb_duplicados_entre_poses": len(dup), "duplicados_exemplos": dup[:10],
        "dimensoes": sorted({"%sx%s" % (r["largura"], r["altura"]) for r in res if r["decodifica"]}),
        "modos_por_modalidade": {m: sorted({r["modo"] for r in res if r["modalidade"] == m and r["decodifica"]})
                                 for m in MODS},
        "combinacoes_de_rotulos_segmentacao": rot,
        "frac_braco_por_camera": {c: est(r["frac_braco"] for r in res if r["camera"] == c
                                         and r["modalidade"] == "segmentation_labels_map") for c in CAMERAS},
        "profundidade_mm_por_camera": {c: {"min": est(r["min_mm"] for r in res if r["camera"] == c
                                                      and r["modalidade"] == "depth"),
                                           "frac_sem_retorno": est(r["frac_sem_retorno"] for r in res
                                                                   if r["camera"] == c and r["modalidade"] == "depth")}
                                       for c in CAMERAS},
        "rgb_desvio_por_camera": {c: est(r["desvio"] for r in res if r["camera"] == c and r["modalidade"] == "image")
                                  for c in CAMERAS},
        "tempo_s": round(time.time() - t0, 1), "processos": a.proc,
    }
    for destino in (os.path.join(a.meta, "integridade.json"), os.path.join(RAIZ, "resultados", "dataset_integridade.json")):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w") as f:
            json.dump(resumo, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: resumo[k] for k in ("n_poses_verificadas", "n_imagens_verificadas", "n_existem",
                                             "n_decodificam", "n_problemas", "n_quadros_rgb_duplicados_entre_poses",
                                             "dimensoes", "modos_por_modalidade", "combinacoes_de_rotulos_segmentacao",
                                             "tempo_s")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
