#!/usr/bin/env python3
"""Grafico das trajetorias de juntas planejadas pelo MoveIt 2 (OMPL) e
executadas pelo ros2_control (hardware falso)."""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import estilo  # noqa: E402

d = json.load(open(sys.argv[1]))
estilo.aplicar()
import matplotlib.pyplot as plt  # noqa: E402

js = np.array(d["joint_states"])
objs = [o for o in d["objetivos"] if o.get("trajetoria")]
fig, axs = plt.subplots(2, 1, figsize=(12, 7.2), sharex=True, gridspec_kw={"height_ratios": [1.15, 1]})
t0 = objs[0]["t_inicio_s"] - 0.5 if objs else 0
for k, j in enumerate(d["juntas"]):
    cor = estilo.CATEG[k]
    for n, o in enumerate(objs):
        tt = np.array([p["t"] for p in o["trajetoria"]]) + o["t_fim_s"] - o["duracao_trajetoria_s"] - t0
        qq = np.degrees([p["q"][o["juntas"].index(j)] for p in o["trajetoria"]])
        axs[0].plot(tt, qq, color=cor, lw=1.6, marker="o", ms=2.5, label=j if n == 0 else None)
    if len(js):
        axs[1].plot(js[:, 0] - t0, np.degrees(js[:, 1 + k]), color=cor, lw=1.6, label=j)
for o in objs:
    ts = o["t_fim_s"] - o["duracao_trajetoria_s"] - t0
    tp = o.get("estatisticas_plan_only", {}).get("tempo_planejamento_s") or [0]
    for ax in axs:
        ax.axvline(ts, color=estilo.TEXTO2, lw=0.6, ls=":")
    axs[0].text(ts + 0.08, 107, "%s\n%s | plano %.0f ms" % (
        o["nome"], o["status"], 1000 * sum(tp) / len(tp)), fontsize=7.5, color=estilo.TEXTO2, va="top")
axs[0].set_ylim(-100, 110)
axs[1].set_ylim(-100, 100)
axs[0].set_ylabel("angulo planejado (graus)")
axs[1].set_ylabel("angulo executado (graus)")
axs[1].set_xlabel("tempo (s)")
axs[0].set_title("Trajetorias planejadas (pontos = waypoints com parametrizacao temporal)", loc="left")
axs[1].set_title("/joint_states publicados pelo joint_state_broadcaster durante a execucao", loc="left")
axs[0].legend(ncol=5, loc="lower left")
fig.suptitle("MoveIt 2 headless (move_group + OMPL RRTConnect + ros2_control com hardware falso) - servo6dof",
             x=0.01, ha="left", fontsize=12, fontweight="semibold")
fig.tight_layout()
fig.savefig(sys.argv[2])
print("figura:", sys.argv[2])
