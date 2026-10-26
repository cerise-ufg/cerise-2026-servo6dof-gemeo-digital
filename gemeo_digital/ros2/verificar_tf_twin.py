#!/usr/bin/env python3
"""Compara, via tf2, world->base_garra (referencia) e world->twin/base_garra (gemeo),
descontado o deslocamento do twin/world. Com o predictor oraculo a diferenca deve ser ~0."""
import json
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.time import Time
from tf2_ros import Buffer, TransformListener

rclpy.init()
no = Node("verificar_tf_twin")
buf = Buffer()
TransformListener(buf, no)
amostras = []
t0 = time.time()
while time.time() - t0 < 8 and len(amostras) < 10:
    rclpy.spin_once(no, timeout_sec=0.1)
    try:
        b = buf.lookup_transform("world", "twin/base_garra", Time())
        # referencia no MESMO carimbo (o gemeo herda o carimbo da imagem = carimbo do joint_state)
        a = buf.lookup_transform("world", "base_garra", Time.from_msg(b.header.stamp))
        o = buf.lookup_transform("world", "twin/world", Time())
    except Exception:
        continue
    pa = np.array([a.transform.translation.x, a.transform.translation.y, a.transform.translation.z])
    pb = np.array([b.transform.translation.x, b.transform.translation.y, b.transform.translation.z])
    po = np.array([o.transform.translation.x, o.transform.translation.y, o.transform.translation.z])
    amostras.append(float(np.linalg.norm((pb - po) - pa)))
    time.sleep(0.5)
res = {"n_amostras": len(amostras), "erro_max_m": max(amostras) if amostras else None,
       "nota": "distancia entre o efetuador do gemeo (twin/base_garra, descontado twin/world) e o da "
               "referencia (base_garra) no mesmo carimbo de tempo, via tf2"}
print(json.dumps(res, indent=1, ensure_ascii=False))
json.dump(res, open("/repo/resultados/ros2_twin_tf.json", "w"), indent=1)
no.destroy_node()
rclpy.shutdown()
