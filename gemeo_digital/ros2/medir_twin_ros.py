#!/usr/bin/env python3
"""
Mede o gemeo em ROS 2: casa /joint_states (referencia, publicada junto com a imagem) e
/twin/joint_states (gemeo, carimbo = carimbo da imagem) pelo carimbo de tempo e calcula:
  - erro por junta (graus) e erro do efetuador (FK do URDF) do gemeo;
  - atraso imagem -> /twin/joint_states (instante de chegada - carimbo da imagem);
  - taxa de publicacao do gemeo e tempo do predictor (/twin/latencia_ms).
  python3 medir_twin_ros.py --duracao 40 --saida /integ/resultados/ros2_twin_pose.json
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "..", "modelo_digital"))
from cinematica import ModeloURDF  # noqa: E402

J5 = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]


def est(v):
    v = np.asarray(v, float)
    if v.size == 0:
        return None
    return {"n": int(v.size), "media": float(v.mean()), "mediana": float(np.median(v)),
            "p95": float(np.percentile(v, 95)), "max": float(v.max())}


class Medidor(Node):
    def __init__(self):
        super().__init__("medir_twin")
        self.ref = {}
        self.pares = []
        self.t_twin = []
        self.lat_pred = []
        self.create_subscription(JointState, "/joint_states", self.cb_ref, 50)
        self.create_subscription(JointState, "/twin/joint_states", self.cb_twin, 50)
        self.create_subscription(Float32, "/twin/latencia_ms", lambda m: self.lat_pred.append(m.data), 50)

    @staticmethod
    def chave(st):
        return (st.sec, st.nanosec)

    def cb_ref(self, m):
        self.ref[self.chave(m.header.stamp)] = dict(zip(m.name, m.position))

    def cb_twin(self, m):
        agora = self.get_clock().now().nanoseconds / 1e9
        st = m.header.stamp.sec + m.header.stamp.nanosec / 1e9
        self.t_twin.append(agora)
        r = self.ref.get(self.chave(m.header.stamp))
        if r is not None:
            self.pares.append((r, dict(zip(m.name, m.position)), 1000 * (agora - st)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duracao", type=float, default=40)
    ap.add_argument("--saida", default="/integ/resultados/ros2_twin_pose.json")
    ap.add_argument("--urdf", default=os.path.join(AQUI, "..", "..", "modelo_digital", "urdf", "servo6dof.urdf"))
    a = ap.parse_args()
    rclpy.init()
    no = Medidor()
    t0 = time.time()
    while time.time() - t0 < a.duracao:
        rclpy.spin_once(no, timeout_sec=0.1)
    modelo = ModeloURDF(a.urdf)
    err = {j: [] for j in J5}
    ee, atraso = [], []
    for r, t, d in no.pares:
        for j in J5:
            err[j].append(abs(math.degrees(t[j] - r[j])))
        qt = dict(t)
        qt.setdefault("joint_6", r.get("joint_6", 0.0))
        pr = modelo.fk(r)["base_garra"][:3, 3]
        pt = modelo.fk(qt)["base_garra"][:3, 3]
        ee.append(1000 * float(np.linalg.norm(pr - pt)))
        atraso.append(d)
    tt = np.array(no.t_twin)
    res = {"descricao": "no ROS 2 gemeo_twin (predictor=http -> POST /api/prever do servidor do gemeo, PosePredictor "
                        "na GPU) recebendo /camera_frontal/image do publicador do conjunto de teste; pares casados "
                        "pelo carimbo da imagem",
           "duracao_s": a.duracao, "msgs_twin": int(tt.size), "pares_casados": len(no.pares),
           "taxa_twin_hz": float((tt.size - 1) / (tt[-1] - tt[0])) if tt.size > 2 else None,
           "atraso_imagem_ate_twin_ms": est(atraso), "latencia_predictor_http_ms": est(no.lat_pred),
           "erro_efetuador_mm": est(ee), "abs_err_graus": {j: est(v) for j, v in err.items()},
           "mae5_graus": float(np.mean([np.mean(v) for v in err.values()])) if no.pares else None}
    print(json.dumps(res, indent=1, ensure_ascii=False))
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    json.dump(res, open(a.saida, "w"), indent=2, ensure_ascii=False)
    no.destroy_node()
    rclpy.try_shutdown()


if __name__ == "__main__":
    main()
