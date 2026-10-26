#!/usr/bin/env python3
"""
Valida a cinematica direta (cinematica.py, numpy) contra o TF publicado pelo
robot_state_publisher (ROS 2 Humble) para o MESMO URDF.

Procedimento: sobe o robot_state_publisher como subprocesso; para N
configuracoes aleatorias dentro dos limites publica /joint_states (so as 6
juntas ativas: o RSP resolve as mimic) com um carimbo de tempo unico; consulta
o TF world->link naquele carimbo para todos os links moveis e compara com a FK
propria (erro de posicao em m e de orientacao em rad).

Saidas: resultados/validacao_fk_tf.json, resultados/validacao_fk_tf.csv,
        evidencias/a11_validacao_fk_tf.png

Uso (no container):  python3 modelo_digital/validar_fk_tf.py --n 300
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
import rclpy
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import JointState
from tf2_ros import Buffer, TransformListener

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cinematica import ModeloURDF, URDF_PADRAO  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def quat_para_R(x, y, z, w):
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def ang_rot(Ra, Rb):
    c = (np.trace(Ra.T @ Rb) - 1) / 2
    return float(np.arccos(np.clip(c, -1, 1)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--semente", type=int, default=7)
    a = ap.parse_args()

    modelo = ModeloURDF(URDF_PADRAO)
    urdf_txt = open(URDF_PADRAO).read()
    params = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    import yaml
    yaml.safe_dump({"robot_state_publisher": {"ros__parameters": {"robot_description": urdf_txt,
                                                                  "publish_frequency": 50.0}}}, params)
    params.close()
    rsp = subprocess.Popen(["ros2", "run", "robot_state_publisher", "robot_state_publisher",
                            "--ros-args", "--params-file", params.name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    time.sleep(3.0)

    rclpy.init()
    no = Node("validador_fk")
    pub = no.create_publisher(JointState, "/joint_states", 10)
    buf = Buffer(cache_time=Duration(seconds=120))
    TransformListener(buf, no)

    rng = np.random.default_rng(a.semente)
    ativas = modelo.ativas
    lims = [(modelo.juntas[n].inf, modelo.juntas[n].sup) for n in ativas]
    links = [l for l in modelo.links if l not in ("world", "base_link")]
    linhas = []
    falhas = 0
    t_ini = time.time()
    # espera o RSP aparecer
    for _ in range(100):
        rclpy.spin_once(no, timeout_sec=0.05)
        if no.count_subscribers("/joint_states") > 0:
            break
    for i in range(a.n):
        q = {n: float(rng.uniform(lo, hi)) for n, (lo, hi) in zip(ativas, lims)}
        if i == 0:
            q = {n: 0.0 for n in ativas}
        msg = JointState()
        stamp = no.get_clock().now()
        msg.header.stamp = stamp.to_msg()
        msg.name = list(q.keys())
        msg.position = list(q.values())
        pub.publish(msg)
        poses = modelo.fk(q)
        for link in links:
            tf = None
            t0 = time.time()
            while time.time() - t0 < 3.0:
                rclpy.spin_once(no, timeout_sec=0.01)
                if buf.can_transform("world", link, Time.from_msg(msg.header.stamp)):
                    tf = buf.lookup_transform("world", link, Time.from_msg(msg.header.stamp))
                    break
            if tf is None:
                falhas += 1
                continue
            tr = tf.transform.translation
            ro = tf.transform.rotation
            p_tf = np.array([tr.x, tr.y, tr.z])
            R_tf = quat_para_R(ro.x, ro.y, ro.z, ro.w)
            e_pos = float(np.linalg.norm(p_tf - poses[link][:3, 3]))
            e_ang = ang_rot(R_tf, poses[link][:3, :3])
            linhas.append({"config": i, "link": link, "erro_pos_m": e_pos, "erro_ang_rad": e_ang,
                           **{n: round(v, 6) for n, v in q.items()}})
        if (i + 1) % 50 == 0:
            print("%d/%d configuracoes" % (i + 1, a.n), flush=True)
    dur = time.time() - t_ini
    no.destroy_node()
    rclpy.shutdown()
    rsp.terminate()

    ep = np.array([l["erro_pos_m"] for l in linhas])
    ea = np.array([l["erro_ang_rad"] for l in linhas])
    por_link = {}
    for link in links:
        sel = [l for l in linhas if l["link"] == link]
        if sel:
            por_link[link] = {"max_erro_pos_m": max(s["erro_pos_m"] for s in sel),
                              "max_erro_ang_rad": max(s["erro_ang_rad"] for s in sel)}
    res = {
        "n_configuracoes": a.n, "n_links_comparados": len(links), "n_comparacoes": len(linhas),
        "consultas_tf_falhas": falhas, "duracao_s": round(dur, 1),
        "erro_pos_m": {"media": float(ep.mean()), "max": float(ep.max()), "p99": float(np.percentile(ep, 99))},
        "erro_ang_rad": {"media": float(ea.mean()), "max": float(ea.max()), "p99": float(np.percentile(ea, 99))},
        "por_link": por_link,
        "referencia": "robot_state_publisher (ROS 2 Humble) + tf2_ros, mesmo URDF",
    }
    os.makedirs(os.path.join(RAIZ, "resultados"), exist_ok=True)
    with open(os.path.join(RAIZ, "resultados", "validacao_fk_tf.json"), "w") as f:
        json.dump(res, f, indent=2)
    with open(os.path.join(RAIZ, "resultados", "validacao_fk_tf.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    print(json.dumps({k: res[k] for k in ("n_comparacoes", "consultas_tf_falhas", "erro_pos_m", "erro_ang_rad")},
                     indent=1))

    # figura
    import estilo
    estilo.aplicar()
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(10, 3.6))
    nomes = list(por_link.keys())
    for ax, chave, rot, esc in [(axs[0], "erro_pos_m", "erro de posicao (m)", 1),
                                (axs[1], "erro_ang_rad", "erro de orientacao (rad)", 1)]:
        dados = [[l[chave] for l in linhas if l["link"] == n] for n in nomes]
        bp = ax.boxplot(dados, vert=False, labels=nomes, patch_artist=True, widths=0.55,
                        flierprops=dict(marker="o", markersize=3, markerfacecolor=estilo.CATEG[0],
                                        markeredgecolor="none", alpha=0.6))
        for b in bp["boxes"]:
            b.set(facecolor="#cde2fb", edgecolor=estilo.CATEG[0])
        for k in ("whiskers", "caps", "medians"):
            for x in bp[k]:
                x.set(color=estilo.CATEG[0])
        ax.set_xlabel(rot)
        ax.ticklabel_format(axis="x", style="sci", scilimits=(0, 0))
        ax.grid(axis="y", visible=False)
    axs[0].set_title("Posicao: max %.2e m" % ep.max(), loc="left")
    axs[1].set_title("Orientacao: max %.2e rad" % ea.max(), loc="left")
    fig.suptitle("Validacao da FK propria (numpy) contra o TF do robot_state_publisher - %d configuracoes x %d links"
                 % (a.n, len(links)), x=0.01, ha="left", fontsize=11.5, fontweight="semibold")
    fig.tight_layout()
    fig.savefig(os.path.join(RAIZ, "evidencias", "a11_validacao_fk_tf.png"))


if __name__ == "__main__":
    main()
