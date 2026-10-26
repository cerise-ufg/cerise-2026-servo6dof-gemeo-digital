#!/usr/bin/env python3
"""
Extrai do URDF gerado as caracteristicas fisicas e cinematicas do servo6dof:
  - tabela de juntas (tipo, pai/filho, origem xyz/rpy, eixo, limites, esforco,
    velocidade, mimic)  -> resultados/modelo_juntas.csv + .md
  - tabela de links (massa, inercia, malha, escala, cor)  -> resultados/modelo_links.csv + .md
  - resumo (contagens, GDL, comprimentos entre juntas)  -> resultados/modelo_resumo.json
  - arvore cinematica (graphviz)  -> evidencias/a11_arvore_cinematica.png

Uso (no container cerise26_gemeo):  python3 modelo_digital/tabela_modelo.py
"""
import csv
import json
import math
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cinematica import ModeloURDF, URDF_PADRAO  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(RAIZ, "resultados")
EVI = os.path.join(RAIZ, "evidencias")
os.makedirs(RES, exist_ok=True)
os.makedirs(EVI, exist_ok=True)


def fmt(v, nd=4):
    if v is None:
        return "-"
    if isinstance(v, (list, tuple)):
        return "(" + ", ".join(fmt(x, nd) for x in v) + ")"
    return ("%." + str(nd) + "g") % v


def md_tabela(cab, linhas):
    s = "| " + " | ".join(cab) + " |\n|" + "|".join(["---"] * len(cab)) + "|\n"
    for l in linhas:
        s += "| " + " | ".join(str(x) for x in l) + " |\n"
    return s


def main():
    m = ModeloURDF(URDF_PADRAO)

    # ---------------- juntas
    cab_j = ["junta", "tipo", "pai", "filho", "origem_xyz_m", "origem_rpy_rad", "eixo",
             "lim_inf_rad", "lim_sup_rad", "lim_inf_graus", "lim_sup_graus",
             "esforco", "velocidade_rad_s", "mimic"]
    lin_j = []
    for j in m.juntas.values():
        mim = "" if j.mimic is None else "%s x %g %+g" % j.mimic
        lin_j.append([j.nome, j.tipo, j.pai, j.filho, fmt(j.xyz), fmt(j.rpy), fmt(j.eixo, 3),
                      fmt(j.inf), fmt(j.sup),
                      fmt(math.degrees(j.inf), 4) if j.inf is not None else "-",
                      fmt(math.degrees(j.sup), 4) if j.sup is not None else "-",
                      fmt(j.esforco), fmt(j.velocidade), mim])
    with open(os.path.join(RES, "modelo_juntas.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cab_j)
        w.writerows(lin_j)
    cab_md = ["Junta", "Tipo", "Pai -> filho", "Origem xyz (m)", "Origem rpy (rad)", "Eixo",
              "Limites (graus)", "Mimic"]
    lin_md = [[l[0], l[1], "%s -> %s" % (l[2], l[3]), l[4], l[5], l[6],
               ("[%s, %s]" % (l[9], l[10])) if l[9] != "-" else "-", l[13] or "-"] for l in lin_j]
    with open(os.path.join(RES, "modelo_juntas.md"), "w") as f:
        f.write(md_tabela(cab_md, lin_md))

    # ---------------- links
    cab_l = ["link", "massa_kg", "ixx", "iyy", "izz", "malha", "escala", "visual_xyz", "visual_rpy", "rgba"]
    lin_l = []
    for l in m.links.values():
        v = l.visuais[0] if l.visuais else None
        it = l.inercia or {}
        xyz = list(np.round(v["T"][:3, 3], 4)) if v else None
        lin_l.append([l.nome, fmt(l.massa), fmt(it.get("ixx")), fmt(it.get("iyy")), fmt(it.get("izz")),
                      os.path.basename(v["arquivo"]) if v else "-",
                      fmt(v["escala"], 3) if v else "-", fmt(xyz) if v else "-", "-",
                      fmt(v["rgba"], 3) if v else "-"])
    with open(os.path.join(RES, "modelo_links.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cab_l)
        w.writerows(lin_l)
    with open(os.path.join(RES, "modelo_links.md"), "w") as f:
        f.write(md_tabela(["Link", "Massa (kg)", "Ixx", "Iyy", "Izz", "Malha (STL)", "Escala"],
                          [[x[0], x[1], x[2], x[3], x[4], x[5], x[6]] for x in lin_l]))

    # ---------------- resumo
    poses0 = m.fk({})
    cadeia = ["base_link", "primeiro_elo", "segundo_elo", "terceiro_elo", "quarto_elo", "base_garra"]
    seg = []
    for a, b in zip(cadeia[:-1], cadeia[1:]):
        seg.append({"de": a, "ate": b,
                    "distancia_m": float(np.linalg.norm(poses0[b][:3, 3] - poses0[a][:3, 3]))})
    tipos = {}
    for j in m.juntas.values():
        tipos[j.tipo] = tipos.get(j.tipo, 0) + 1
    resumo = {
        "urdf": os.path.relpath(m.caminho, RAIZ),
        "robo": m.nome,
        "raiz": m.raiz,
        "n_links": len(m.links),
        "n_juntas": len(m.juntas),
        "juntas_por_tipo": tipos,
        "juntas_ativas": m.ativas,
        "gdl_braco": 5,
        "gdl_garra": 1,
        "juntas_mimic": [j.nome for j in m.juntas.values() if j.mimic],
        "massa_total_kg": float(sum(l.massa or 0 for l in m.links.values())),
        "inercias_placeholder": all((l.inercia or {}).get("ixx") == 1.0 for l in m.links.values() if l.inercia),
        "malhas_stl": sorted({os.path.basename(v["arquivo"]) for l in m.links.values() for v in l.visuais}),
        "escala_malhas": sorted({tuple(v["escala"]) for l in m.links.values() for v in l.visuais}),
        "posicao_zero": {n: [round(float(x), 4) for x in poses0[n][:3, 3]] for n in cadeia},
        "segmentos_cadeia_zero": seg,
    }
    with open(os.path.join(RES, "modelo_resumo.json"), "w") as f:
        json.dump(resumo, f, indent=2, ensure_ascii=False, default=list)
    print(json.dumps({k: resumo[k] for k in ("n_links", "n_juntas", "juntas_por_tipo", "massa_total_kg",
                                              "inercias_placeholder")}, ensure_ascii=False))

    # ---------------- arvore cinematica (graphviz)
    ativa = "#2a78d6"
    mimic = "#eb6834"
    fixa = "#8a8984"
    dot = ['digraph servo6dof {',
           '  graph [rankdir=TB, bgcolor="#fcfcfb", fontname="Helvetica", nodesep=0.35, ranksep=0.42, pad=0.3,',
           '         label="Arvore cinematica do servo6dof (URDF gerado do xacro)\\n'
           'azul = junta ativa (comandada) | laranja = mimic de joint_6 | cinza = fixa", labelloc=t, fontsize=15];',
           '  node [shape=box, style="rounded,filled", fillcolor="#ffffff", color="#b9b8b2", fontname="Helvetica", fontsize=11];',
           '  edge [fontname="Helvetica", fontsize=9.5];']
    for l in m.links:
        extra = ""
        if l == "base_garra":
            extra = ', fillcolor="#e8f1fc", color="#2a78d6", penwidth=1.6'
        if l == m.raiz:
            extra = ', fillcolor="#f0efec"'
        massa = m.links[l].massa
        lab = l if massa is None else "%s\\nm = %g kg" % (l, massa)
        dot.append('  "%s" [label="%s"%s];' % (l, lab, extra))
    for j in m.juntas.values():
        if j.tipo == "fixed":
            cor, lab = fixa, "%s\\n(fixa)" % j.nome
        elif j.mimic:
            cor = mimic
            lab = "%s\\nmimic %s x%g %+g" % (j.nome, j.mimic[0], j.mimic[1], j.mimic[2])
        else:
            cor = ativa
            lab = "%s  eixo %s\\n[%.0f, %.0f] graus" % (
                j.nome, "".join("xyz"[k] for k in range(3) if abs(j.eixo[k]) > 0.5),
                math.degrees(j.inf), math.degrees(j.sup))
        dot.append('  "%s" -> "%s" [label="%s", color="%s", fontcolor="%s", penwidth=1.8];'
                   % (j.pai, j.filho, lab, cor, "#0b0b0b" if cor != fixa else "#52514e"))
    dot.append("}")
    caminho_dot = os.path.join(RES, "arvore_cinematica.dot")
    with open(caminho_dot, "w") as f:
        f.write("\n".join(dot))
    png = os.path.join(EVI, "a11_arvore_cinematica.png")
    subprocess.run(["dot", "-Tpng", "-Gdpi=150", caminho_dot, "-o", png], check=True)
    print("figura:", png)


if __name__ == "__main__":
    main()
