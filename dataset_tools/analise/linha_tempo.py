#!/usr/bin/env python3
"""
Linha do tempo e vazao da geracao do dataset, a partir dos mtimes dos JSONs
(index.csv) e dos logs (gen_main.log e gen_logs/w*.log):
  - poses acumuladas x tempo; vazao em janela movel (poses/min);
  - contribuicao por worker (id %% n_workers);
  - rondas do gerador ("faltam N poses") e avisos/erros nos logs.
Saidas: resultados/dataset_geracao.json, evidencias/a7_linha_tempo_geracao.png
Uso: python3 dataset_tools/analise/linha_tempo.py --meta /dataset_meta --logs /braco
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "modelo_digital"))
import estilo  # noqa: E402

FUSO = dt.timezone(dt.timedelta(hours=-3))  # hora de Brasilia (Spark)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", default="/dataset_meta")
    ap.add_argument("--logs", default="/braco")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--desde", default=None, help="ignora poses com mtime anterior (epoch ou YYYY-mm-ddTHH:MM)")
    a = ap.parse_args()
    L = list(csv.DictReader(open(os.path.join(a.meta, "index.csv"))))
    ids = np.array([int(l["id"]) for l in L])
    t = np.array([max(float(l["json_mtime"]), *[float(l[k]) for k in l if k.endswith("_mtime") and l[k]])
                  for l in L])
    ordem = np.argsort(t)
    t, ids = t[ordem], ids[ordem]

    # rondas e eventos do log principal
    rondas = []
    inicio_log = None
    p_main = os.path.join(a.logs, "gen_main.log")
    if os.path.exists(p_main):
        for linha in open(p_main, errors="ignore"):
            m = re.search(r"=== inicio (.+?) \| workers=(\d+)", linha)
            if m:
                inicio_log = m.group(1)
            m = re.match(r"(\d\d:\d\d:\d\d) faltam (\d+) poses", linha)
            if m:
                rondas.append({"hora_utc": m.group(1), "faltam": int(m.group(2))})
    avisos = {}
    for p in sorted(glob.glob(os.path.join(a.logs, "gen_logs", "w*.log"))):
        txt = open(p, errors="ignore").read()
        avisos[os.path.basename(p)] = {
            "erro_residual": len(re.findall(r"erro residual", txt)),
            "sem_quadro": len(re.findall(r"sem quadro novo", txt)),
            "pulando": len(re.findall(r"pulando foto", txt)),
            "FIM": len(re.findall(r"FIM: \d+ poses", txt)),
            "linhas_ERROR": len(re.findall(r"\[ERROR\]", txt)),
        }

    dur = t[-1] - t[0]
    # vazao em janelas de 5 min
    jan = 300.0
    bordas = np.arange(t[0], t[-1] + jan, jan)
    cont, _ = np.histogram(t, bins=bordas)
    vaz = cont / (jan / 60.0)
    # intervalos entre poses do mesmo worker
    por_worker = {}
    for w in range(a.workers):
        tw = t[ids % a.workers == w]
        por_worker[w] = {"poses": int(len(tw)),
                         "intervalo_mediano_s": float(np.median(np.diff(tw))) if len(tw) > 2 else None}
    regime = vaz[1:-1] if len(vaz) > 2 else vaz
    res = {
        "n_poses": int(len(t)),
        "primeira_pose": dt.datetime.fromtimestamp(t[0], FUSO).isoformat(),
        "ultima_pose": dt.datetime.fromtimestamp(t[-1], FUSO).isoformat(),
        "duracao_h": dur / 3600, "vazao_media_poses_s": len(t) / dur if dur else None,
        "vazao_media_poses_min": 60 * len(t) / dur if dur else None,
        "vazao_janela5min_poses_min": {"mediana": float(np.median(regime)), "max": float(np.max(vaz)),
                                       "min_regime": float(np.min(regime))},
        "imagens_por_s": 6 * len(t) / dur if dur else None,
        "workers": a.workers, "por_worker": por_worker,
        "s_por_pose_por_worker_mediano": float(np.median([v["intervalo_mediano_s"] for v in por_worker.values()
                                                          if v["intervalo_mediano_s"]])),
        "inicio_log": inicio_log, "rondas": rondas, "avisos_logs_workers": avisos,
    }
    with open(os.path.join(RAIZ, "resultados", "dataset_geracao.json"), "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: res[k] for k in ("n_poses", "primeira_pose", "ultima_pose", "duracao_h",
                                          "vazao_media_poses_s", "vazao_janela5min_poses_min",
                                          "s_por_pose_por_worker_mediano", "rondas")}, indent=1, ensure_ascii=False))

    estilo.aplicar()
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    tempos = [dt.datetime.fromtimestamp(x, FUSO) for x in t]
    fig, axs = plt.subplots(1, 3, figsize=(14, 3.9), gridspec_kw={"width_ratios": [1.3, 1.3, 1]})
    ax = axs[0]
    ax.plot(tempos, np.arange(1, len(t) + 1), color=estilo.CATEG[0])
    ax.axhline(5000, color=estilo.TEXTO2, lw=0.8, ls="--")
    ax.text(tempos[0], 5000, " meta 5000 poses", va="bottom", fontsize=8, color=estilo.TEXTO2)
    ax.set_ylabel("poses concluidas")
    ax.set_title("Poses acumuladas", loc="left")
    ax = axs[1]
    tb = [dt.datetime.fromtimestamp(x + jan / 2, FUSO) for x in bordas[:-1]]
    ax.bar(tb, vaz, width=jan / 86400 * 0.85, color=estilo.CATEG[0])
    ax.axhline(res["vazao_media_poses_min"], color=estilo.CATEG[1], lw=1.5)
    ax.text(tb[-1], res["vazao_media_poses_min"], "media %.1f poses/min " % res["vazao_media_poses_min"],
            va="bottom", ha="right", fontsize=8, color=estilo.TEXTO,
            bbox=dict(facecolor=estilo.SUPERFICIE, edgecolor="none", pad=1.5, alpha=0.9))
    ax.set_ylabel("poses/min (janelas de 5 min)")
    ax.set_title("Vazao da geracao (%d workers Gazebo)" % a.workers, loc="left")
    for ax in axs[:2]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=FUSO))
        ax.set_xlabel("hora (Brasilia)")
    ax = axs[2]
    ws = list(range(a.workers))
    ax.bar(ws, [por_worker[w]["poses"] for w in ws], color=estilo.CATEG[0], width=0.65)
    for w in ws:
        ax.text(w, por_worker[w]["poses"], str(por_worker[w]["poses"]), ha="center", va="bottom", fontsize=8,
                color=estilo.TEXTO2)
    ax.set_xticks(ws)
    ax.set_xlabel("worker (id mod %d)" % a.workers)
    ax.set_ylabel("poses")
    ax.set_title("Poses por worker", loc="left")
    ax.grid(axis="x", visible=False)
    fig.suptitle("Geracao do dataset no DGX Spark: %d poses em %.2f h (%.2f poses/s, %.1f imagens/s)" % (
        len(t), dur / 3600, res["vazao_media_poses_s"], res["imagens_por_s"]), x=0.01, ha="left",
        fontsize=12, fontweight="semibold")
    fig.tight_layout()
    fig.savefig(os.path.join(RAIZ, "evidencias", "a7_linha_tempo_geracao.png"))


if __name__ == "__main__":
    main()
