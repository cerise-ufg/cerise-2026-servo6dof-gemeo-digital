#!/usr/bin/env python3
"""
Grade de amostras do dataset: para N poses, as 6 imagens (RGB, profundidade
colorizada e segmentacao) das duas cameras. Tambem extrai uma AMOSTRA pequena
(--amostra K poses, < 50 MB) para versionar no repositorio.

Uso: python3 dataset_tools/analise/grades.py --dataset /dataset --meta /dataset_meta --n 4 [--amostra 8]
"""
import argparse
import csv
import json
import os
import shutil
import sys

import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(RAIZ, "modelo_digital"))
import estilo  # noqa: E402

CAMERAS = ["camera_frontal", "camera_diagonal"]
COR_ROTULO = np.array([[235, 104, 52], [70, 74, 82], [150, 155, 165]], dtype=np.uint8)  # 0 braco, 1 chao, 2 fundo


def depth_cor(d, cmap):
    v = d.astype(float) / 1000.0
    m = v > 0
    lo, hi = np.percentile(v[m], 1), np.percentile(v[m], 99)
    x = np.clip((v - lo) / (hi - lo + 1e-9), 0, 1)
    rgb = (cmap(1 - x)[:, :, :3] * 255).astype(np.uint8)
    rgb[~m] = 0
    return rgb, lo, hi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/dataset")
    ap.add_argument("--meta", default="/dataset_meta")
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--amostra", type=int, default=0)
    ap.add_argument("--semente", type=int, default=5)
    a = ap.parse_args()
    from PIL import Image
    L = list(csv.DictReader(open(os.path.join(a.meta, "index.csv"))))
    rng = np.random.default_rng(a.semente)
    sel = sorted(rng.choice(len(L), a.n, replace=False).tolist())
    estilo.aplicar()
    import matplotlib.pyplot as plt
    cmap = plt.get_cmap("viridis")
    fig, axs = plt.subplots(a.n, 6, figsize=(17, 1.62 * a.n + 0.75))
    tit = ["frontal - RGB", "frontal - profundidade", "frontal - segmentacao",
           "diagonal - RGB", "diagonal - profundidade", "diagonal - segmentacao"]
    for r, k in enumerate(sel):
        lin = L[k]
        i = int(lin["id"])
        for c_i, c in enumerate(CAMERAS):
            rgb = np.asarray(Image.open(os.path.join(a.dataset, lin[c + "_image_arquivo"])).convert("RGB"))
            dep = np.asarray(Image.open(os.path.join(a.dataset, lin[c + "_depth_arquivo"])))
            seg = np.asarray(Image.open(os.path.join(a.dataset, lin[c + "_segmentation_labels_map_arquivo"])))
            seg = seg[:, :, 0] if seg.ndim == 3 else seg
            dc, lo, hi = depth_cor(dep, cmap)
            sc = COR_ROTULO[np.clip(seg, 0, 2)]
            for t, (img, extra) in enumerate([(rgb, ""), (dc, "%.1f-%.1f m" % (lo, hi)), (sc, "")]):
                ax = axs[r, 3 * c_i + t]
                ax.imshow(img)
                ax.set_xticks([])
                ax.set_yticks([])
                ax.grid(False)
                for s in ax.spines.values():
                    s.set_visible(False)
                if r == 0:
                    ax.set_title(tit[3 * c_i + t], loc="left", fontsize=10)
                if extra:
                    ax.text(8, 700, extra, color="white", fontsize=7.5, va="bottom",
                            bbox=dict(facecolor="black", alpha=0.45, lw=0, pad=1.5))
        q = [float(lin["real_joint_%d" % j]) for j in range(1, 6)]
        axs[r, 0].set_ylabel("pose %06d\njuntas reais\n[%s] graus" % (i, ", ".join("%.0f" % np.degrees(v) for v in q)),
                             fontsize=8, rotation=0, ha="right", va="center", labelpad=6)
    fig.suptitle("Amostras do dataset servo6dof HD (1280x720): RGB, profundidade (colorizada, viridis: perto = claro) "
                 "e segmentacao (laranja = rotulo 0: braco; tambem o ceu sem retorno de profundidade)", x=0.01, ha="left", fontsize=11.5, fontweight="semibold")
    fig.tight_layout(rect=(0.03, 0, 1, 1 - 0.5 / fig.get_figheight()))
    fig.subplots_adjust(wspace=0.03, hspace=0.06)
    fig.savefig(os.path.join(RAIZ, "evidencias", "a7_grade_amostras.png"))
    print("figura: evidencias/a7_grade_amostras.png", [int(L[k]["id"]) for k in sel])

    if a.amostra:
        dest = os.path.join(RAIZ, "amostra_dataset")
        os.makedirs(dest, exist_ok=True)
        testes = [l for l in L if l["split"] == "teste"]
        esc = [testes[k] for k in sorted(rng.choice(len(testes), min(a.amostra, len(testes)), replace=False))]
        total = 0
        for lin in esc:
            nomes = ["%06d.json" % int(lin["id"])] + [lin["%s_%s_arquivo" % (c, m)] for c in CAMERAS
                                                      for m in ("image", "depth", "segmentation_labels_map")]
            for nm in nomes:
                shutil.copy2(os.path.join(a.dataset, nm), os.path.join(dest, nm))
                total += os.path.getsize(os.path.join(dest, nm))
        with open(os.path.join(dest, "index_amostra.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(esc[0].keys()))
            w.writeheader()
            w.writerows(esc)
        print("amostra: %d poses, %.1f MB em %s" % (len(esc), total / 1e6, dest))
        json.dump({"poses": [int(l["id"]) for l in esc], "bytes": total},
                  open(os.path.join(dest, "amostra.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
