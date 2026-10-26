#!/usr/bin/env python3
"""
Validacao quantitativa do modelo digital contra as imagens do dataset:
IoU entre a SILHUETA do modelo (malhas do URDF posicionadas pela FK com as
juntas registradas e projetadas pelo modelo pinhole da camera) e a MASCARA do
braco obtida da segmentacao do Gazebo (rotulo 0 = braco, pois chao = 1 e
fundo = 2; pixels sem retorno de profundidade - ceu - sao excluidos).

Rasterizacao por Agg (matplotlib), sem antialiasing, na resolucao nativa.
Triangulos inteiramente abaixo do chao (z < 0) sao descartados (o chao os oculta).

Saidas: resultados/validacao_projecao.csv / .json, evidencias/a11_iou_silhueta.png
Uso: python3 modelo_digital/validar_projecao.py --dataset /dataset --n 400 --proc 6
"""
import argparse
import csv
import glob
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cinematica import CAMERAS, ModeloURDF, URDF_PADRAO, malhas_no_mundo, projetar  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARE = os.path.join(RAIZ, "ros2_ws", "src", "servo6dof")
_M = None
_CACHE = {}
_FIG = None


def _init():
    global _M, _FIG
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    _M = ModeloURDF(URDF_PADRAO)
    _FIG = plt.figure(figsize=(12.8, 7.2), dpi=100)


def silhueta(tris_uv, w, h):
    from matplotlib.collections import PolyCollection
    fig = _FIG
    fig.clf()
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    ax.add_collection(PolyCollection(tris_uv, facecolors="k", edgecolors="none", antialiased=False))
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[:, :, 0]
    return buf < 128


def triangulos(q):
    malhas = malhas_no_mundo(_M, q, SHARE, _CACHE)
    tri = np.concatenate([t for t, _, _ in malhas])
    z_min = float(tri[:, :, 2].min())
    return tri[(tri[:, :, 2] > -1e-3).any(axis=1)], z_min


def sil_de(tri, cam):
    w, h = CAMERAS[cam]["largura"], CAMERAS[cam]["altura"]
    uv, prof = projetar(tri.reshape(-1, 3), cam)
    ok = (prof.reshape(-1, 3) > 0).all(axis=1)
    return silhueta(uv.reshape(-1, 3, 2)[ok], w, h)


def iou(a, b):
    u = float((a | b).sum())
    return float((a & b).sum()) / u if u else float("nan")


def avalia(args):
    from PIL import Image
    dataset, i = args
    meta = json.load(open(os.path.join(dataset, "%06d.json" % i)))
    q = dict(meta.get("juntas_reais") or meta["juntas_comandadas"])
    q["joint_6"] = meta["garra_comandada"]["joint_6"]
    qc = dict(meta["juntas_comandadas"])
    qc["joint_6"] = q["joint_6"]
    dif = max(abs(q[j] - qc[j]) for j in qc if j != "joint_6")
    tri, z_min = triangulos(q)
    tri_c = triangulos(qc)[0] if dif > 0.01 else None
    linhas = []
    for cam in CAMERAS:
        sil = sil_de(tri, cam)
        seg = np.asarray(Image.open(os.path.join(dataset, "%06d_%s_segmentation_labels_map.png" % (i, cam))))
        dep = np.asarray(Image.open(os.path.join(dataset, "%06d_%s_depth.png" % (i, cam))))
        seg = seg[:, :, 0] if seg.ndim == 3 else seg
        mask = (seg == 0) & (dep > 0)
        inter = float((sil & mask).sum())
        uni = float((sil | mask).sum())
        iou_c = iou(sil_de(tri_c, cam), mask) if tri_c is not None else ""
        linhas.append({"id": i, "camera": cam, "iou": inter / uni if uni else float("nan"),
                       "dif_real_cmd_rad": round(dif, 4), "iou_com_juntas_comandadas": iou_c,
                       "precisao": inter / max(sil.sum(), 1), "revocacao": inter / max(mask.sum(), 1),
                       "px_modelo": int(sil.sum()), "px_mascara": int(mask.sum()),
                       "z_min_malha_m": round(z_min, 4)})
    return linhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/dataset")
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--proc", type=int, default=6)
    ap.add_argument("--semente", type=int, default=11)
    a = ap.parse_args()
    ids = sorted(int(os.path.basename(p)[:6]) for p in glob.glob(os.path.join(a.dataset, "[0-9]" * 6 + ".json")))
    rng = np.random.default_rng(a.semente)
    sel = sorted(rng.choice(ids, min(a.n, len(ids)), replace=False).tolist())
    with Pool(a.proc, initializer=_init) as pool:
        res = [l for ls in pool.imap_unordered(avalia, [(a.dataset, i) for i in sel], chunksize=4) for l in ls]
    res.sort(key=lambda r: (r["id"], r["camera"]))
    os.makedirs(os.path.join(RAIZ, "resultados"), exist_ok=True)
    with open(os.path.join(RAIZ, "resultados", "validacao_projecao.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(res[0].keys()))
        w.writeheader()
        w.writerows(res)
    resumo = {"n_poses": len(sel), "n_imagens": len(res), "poses_disponiveis": len(ids)}
    for cam in CAMERAS:
        v = np.array([r["iou"] for r in res if r["camera"] == cam])
        p = np.array([r["precisao"] for r in res if r["camera"] == cam])
        rv = np.array([r["revocacao"] for r in res if r["camera"] == cam])
        resumo[cam] = {"iou_media": float(np.nanmean(v)), "iou_mediana": float(np.nanmedian(v)),
                       "iou_p5": float(np.nanpercentile(v, 5)), "iou_min": float(np.nanmin(v)),
                       "precisao_media": float(p.mean()), "revocacao_media": float(rv.mean())}
    acima = [r["iou"] for r in res if r["z_min_malha_m"] >= 0]
    abaixo = [r["iou"] for r in res if r["z_min_malha_m"] < 0]
    resumo["iou_media_malha_acima_do_chao"] = float(np.mean(acima)) if acima else None
    resumo["iou_media_malha_cruza_chao"] = float(np.mean(abaixo)) if abaixo else None
    resumo["frac_poses_malha_cruza_chao"] = len(abaixo) / max(len(res), 1)
    # consistencia do rotulo: a imagem corresponde as juntas REAIS, as COMANDADAS ou a nenhuma?
    lim = 0.8
    baixos = [r for r in res if r["iou"] < lim]
    resumo["limiar_iou_consistente"] = lim
    resumo["frac_imagens_iou_real_abaixo_limiar"] = len(baixos) / len(res)
    resumo["imagens_iou_real_baixo_mas_comandado_alto"] = sum(
        1 for r in baixos if r["iou_com_juntas_comandadas"] != "" and r["iou_com_juntas_comandadas"] >= lim)
    resumo["exemplos_iou_baixo"] = [{k: r[k] for k in ("id", "camera", "iou", "iou_com_juntas_comandadas",
                                                       "dif_real_cmd_rad")} for r in sorted(baixos, key=lambda r: r["iou"])[:12]]
    div = [r for r in res if r["iou_com_juntas_comandadas"] != ""]
    resumo["imagens_de_poses_divergentes"] = len(div)
    resumo["iou_medio_divergentes_real"] = float(np.mean([r["iou"] for r in div])) if div else None
    resumo["iou_medio_divergentes_comandado"] = float(np.mean([r["iou_com_juntas_comandadas"] for r in div])) if div else None
    with open(os.path.join(RAIZ, "resultados", "validacao_projecao.json"), "w") as f:
        json.dump(resumo, f, indent=2)
    print(json.dumps(resumo, indent=1))

    import estilo
    estilo.aplicar()
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.2), gridspec_kw={"width_ratios": [1.5, 1, 1]})
    bins = np.linspace(0.5, 1, 41)
    for k, cam in enumerate(CAMERAS):
        v = [r["iou"] for r in res if r["camera"] == cam]
        axs[0].hist(np.clip(v, 0.5, 1), bins=bins, histtype="step", lw=2, color=estilo.CATEG[k],
                    label="%s (media %.3f)" % (cam.replace("_", " "), np.mean(v)))
    axs[0].set_xlabel("IoU silhueta do modelo x mascara do Gazebo")
    axs[0].set_ylabel("imagens")
    axs[0].legend(loc="upper left")
    axs[0].set_title("Distribuicao do IoU por camera", loc="left")
    # caso mediano e pior caso: verde = so modelo, vermelho = so mascara, cinza claro = ambos
    _init()
    ordem = sorted(res, key=lambda r: r["iou"])
    for ax, r, rot in [(axs[1], ordem[len(ordem) // 2], "caso mediano"), (axs[2], ordem[0], "pior caso")]:
        rgb, sil, mask = mascaras(a.dataset, r["id"], r["camera"])
        img = (0.55 * rgb).astype(np.uint8)
        img[sil & mask] = [205, 205, 210]
        img[sil & ~mask] = [27, 175, 122]
        img[~sil & mask] = [227, 73, 72]
        ys, xs = np.where(sil | mask)
        ax.imshow(img[max(ys.min() - 20, 0):ys.max() + 20, max(xs.min() - 20, 0):xs.max() + 20])
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        ax.set_title("%s: pose %06d, %s, IoU %.3f" % (rot, r["id"], r["camera"].replace("camera_", ""), r["iou"]),
                     loc="left", fontsize=10)
    axs[2].text(1.0, -0.06, "verde = so no modelo | vermelho = so na mascara do Gazebo | claro = ambos",
                transform=axs[2].transAxes, ha="right", va="top", fontsize=8, color=estilo.TEXTO2)
    fig.suptitle("Concordancia geometrica modelo digital x imagens do dataset - %d poses, %d imagens"
                 % (len(sel), len(res)), x=0.01, ha="left", fontsize=11.5, fontweight="semibold")
    fig.tight_layout()
    fig.savefig(os.path.join(RAIZ, "evidencias", "a11_iou_silhueta.png"))


def mascaras(dataset, i, cam):
    from PIL import Image
    meta = json.load(open(os.path.join(dataset, "%06d.json" % i)))
    q = dict(meta.get("juntas_reais") or meta["juntas_comandadas"])
    q["joint_6"] = meta["garra_comandada"]["joint_6"]
    tri = np.concatenate([t for t, _, _ in malhas_no_mundo(_M, q, SHARE, _CACHE)])
    tri = tri[(tri[:, :, 2] > -1e-3).any(axis=1)]
    w, h = CAMERAS[cam]["largura"], CAMERAS[cam]["altura"]
    uv, prof = projetar(tri.reshape(-1, 3), cam)
    sil = silhueta(uv.reshape(-1, 3, 2)[(prof.reshape(-1, 3) > 0).all(axis=1)], w, h)
    seg = np.asarray(Image.open(os.path.join(dataset, "%06d_%s_segmentation_labels_map.png" % (i, cam))))
    dep = np.asarray(Image.open(os.path.join(dataset, "%06d_%s_depth.png" % (i, cam))))
    seg = seg[:, :, 0] if seg.ndim == 3 else seg
    rgb = np.asarray(Image.open(os.path.join(dataset, "%06d_%s_image.png" % (i, cam))).convert("RGB"))
    return rgb, sil, (seg == 0) & (dep > 0)


if __name__ == "__main__":
    main()
