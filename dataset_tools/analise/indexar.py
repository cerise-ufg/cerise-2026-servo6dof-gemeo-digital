#!/usr/bin/env python3
"""
Indexa o dataset servo6dof HD: gera um index.csv consolidado (uma linha por
pose) com angulos comandados/reais, garra, split recomendado e, para cada
camera x modalidade, o arquivo, o tamanho em bytes e o mtime.

NUNCA escreve dentro da pasta do dataset (somente leitura).
Uso (container): python3 dataset_tools/analise/indexar.py --dataset /dataset --saida /dataset_meta
"""
import argparse
import csv
import json
import os
import re
import time

CAMERAS = ["camera_frontal", "camera_diagonal"]
MODALIDADES = ["image", "depth", "segmentation_labels_map"]
JUNTAS = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
RX_PNG = re.compile(r"^(\d{6})_(camera_frontal|camera_diagonal)_(image|depth|segmentation_labels_map)\.png$")
RX_JSON = re.compile(r"^(\d{6})\.json$")


def split_de(i):
    r = i % 10
    return "treino" if r < 8 else ("validacao" if r == 8 else "teste")


def varrer(pasta):
    """Uma unica varredura do diretorio: nome -> (bytes, mtime)."""
    arq = {}
    with os.scandir(pasta) as it:
        for e in it:
            if e.is_file():
                st = e.stat()
                arq[e.name] = (st.st_size, st.st_mtime)
    return arq


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="/dataset")
    ap.add_argument("--saida", default="/dataset_meta")
    ap.add_argument("--plano", default=None, help="plano_poses.json (para listar poses faltantes)")
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)
    t0 = time.time()
    arq = varrer(a.dataset)
    ids = sorted(int(m.group(1)) for n in arq for m in [RX_JSON.match(n)] if m)
    pngs = {n for n in arq if RX_PNG.match(n)}
    outros = sorted(n for n in arq if not RX_PNG.match(n) and not RX_JSON.match(n))

    cab = (["id", "pose", "split"] + ["cmd_" + j for j in JUNTAS] + ["real_" + j for j in JUNTAS]
           + ["garra_joint_6", "max_dif_real_cmd_rad", "json_bytes", "json_mtime"])
    for c in CAMERAS:
        for m in MODALIDADES:
            cab += ["%s_%s_arquivo" % (c, m), "%s_%s_bytes" % (c, m), "%s_%s_mtime" % (c, m)]
    cab += ["pose_bytes", "arquivos_faltando"]

    referenciados = set()
    linhas = []
    erros_json = []
    for i in ids:
        nome = "%06d.json" % i
        try:
            meta = json.load(open(os.path.join(a.dataset, nome)))
        except Exception as e:
            erros_json.append({"id": i, "erro": str(e)})
            continue
        cmd = meta.get("juntas_comandadas", {})
        real = meta.get("juntas_reais", {})
        lin = {"id": i, "pose": meta.get("pose"), "split": split_de(i)}
        for j in JUNTAS:
            lin["cmd_" + j] = cmd.get(j)
            lin["real_" + j] = real.get(j)
        lin["garra_joint_6"] = meta.get("garra_comandada", {}).get("joint_6")
        difs = [abs(real[j] - cmd[j]) for j in JUNTAS if j in real and j in cmd]
        lin["max_dif_real_cmd_rad"] = max(difs) if difs else ""
        lin["json_bytes"], lin["json_mtime"] = arq[nome]
        total = arq[nome][0]
        falt = []
        cams = meta.get("cameras", {})
        for c in CAMERAS:
            for m in MODALIDADES:
                chave = "%s_%s" % (c, m)
                f = cams.get(chave, {}).get("arquivo", "%06d_%s.png" % (i, chave))
                referenciados.add(f)
                lin[chave + "_arquivo"] = f
                if f in arq:
                    lin[chave + "_bytes"], lin[chave + "_mtime"] = arq[f]
                    total += arq[f][0]
                else:
                    lin[chave + "_bytes"], lin[chave + "_mtime"] = "", ""
                    falt.append(f)
        lin["pose_bytes"] = total
        lin["arquivos_faltando"] = ";".join(falt)
        linhas.append(lin)

    with open(os.path.join(a.saida, "index.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cab)
        w.writeheader()
        w.writerows(linhas)

    faltantes_plano = []
    if a.plano and os.path.exists(a.plano):
        plano = json.load(open(a.plano))
        faltantes_plano = sorted(set(int(p["id"]) for p in plano["poses"]) - set(ids))
    orfaos = sorted(pngs - referenciados)
    resumo = {
        "dataset": a.dataset, "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_poses_json": len(ids), "n_poses_indexadas": len(linhas), "erros_json": erros_json,
        "n_png": len(pngs), "n_png_referenciados": len(referenciados & pngs),
        "png_orfaos": len(orfaos), "exemplos_orfaos": orfaos[:10],
        "outros_arquivos": outros, "poses_com_arquivo_faltando": sum(1 for l in linhas if l["arquivos_faltando"]),
        "faltantes_no_plano": len(faltantes_plano), "exemplos_faltantes_plano": faltantes_plano[:20],
        "bytes_total": int(sum(v[0] for v in arq.values())),
        "splits": {s: sum(1 for l in linhas if l["split"] == s) for s in ("treino", "validacao", "teste")},
        "tempo_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(a.saida, "index_resumo.json"), "w") as f:
        json.dump(resumo, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in resumo.items() if k not in ("exemplos_orfaos", "exemplos_faltantes_plano")},
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
