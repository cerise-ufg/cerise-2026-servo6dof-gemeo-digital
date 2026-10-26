#!/usr/bin/env python3
"""
Publicador de teste: reproduz poses do dataset como se fossem a simulacao/robo real.
  /camera_frontal/image (sensor_msgs/Image rgb8)  e  /joint_states (verdade-base),
  com o mesmo carimbo de tempo, a <taxa> Hz. Parametros: dataset, camera, taxa, n.
"""
import glob
import json
import os

import numpy as np
import rclpy
from PIL import Image as PILImage
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Image, JointState

QOS_SENSOR = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, history=QoSHistoryPolicy.KEEP_LAST, depth=1)
# imagens 1280x720 rgb8 (2,7 MB) em BEST_EFFORT perdem fragmentos no DDS e quase nenhuma chega; "confiavel"
# (RELIABLE, fila 1) entrega todas quando publicador e assinante usam o mesmo perfil
QOS_CONFIAVEL = QoSProfile(reliability=QoSReliabilityPolicy.RELIABLE, history=QoSHistoryPolicy.KEEP_LAST, depth=1)


class Publicador(Node):
    def __init__(self):
        super().__init__("publicar_dataset")
        self.declare_parameter("dataset", "/dataset")
        self.declare_parameter("camera", "camera_frontal")
        self.declare_parameter("taxa", 2.0)
        self.declare_parameter("n", 40)
        self.declare_parameter("qos_imagem", "sensor")   # sensor | confiavel
        # split de teste da frente de pose (semente 2026) quando o index.npz estiver montado; senao id % 10 == 9
        self.declare_parameter("pose_index", "/pose/dados/final/index.npz")
        ds = self.get_parameter("dataset").value
        self.cam = self.get_parameter("camera").value
        ids = sorted(int(os.path.basename(p)[:6]) for p in glob.glob(os.path.join(ds, "[0-9]" * 6 + ".json")))
        pidx = self.get_parameter("pose_index").value
        if pidx and os.path.exists(pidx):
            teste = set(int(i) for i in np.load(pidx)["teste_ids"])
            ids = [i for i in ids if i in teste]
            self.get_logger().info("split de teste da frente de pose (%s)" % pidx)
        else:
            ids = [i for i in ids if i % 10 == 9]
        ids = ids[: int(self.get_parameter("n").value)]
        self.quadros = []
        for i in ids:
            meta = json.load(open(os.path.join(ds, "%06d.json" % i)))
            rgb = np.asarray(PILImage.open(os.path.join(ds, "%06d_%s_image.png" % (i, self.cam))).convert("RGB"))
            q = dict(meta["juntas_reais"])
            q["joint_6"] = meta["garra_comandada"]["joint_6"]
            self.quadros.append((i, rgb, q))
        qos = QOS_CONFIAVEL if self.get_parameter("qos_imagem").value == "confiavel" else QOS_SENSOR
        self.pub_img = self.create_publisher(Image, "/%s/image" % self.cam, qos)
        self.pub_js = self.create_publisher(JointState, "/joint_states", 10)
        self.k = 0
        self.create_timer(1.0 / float(self.get_parameter("taxa").value), self.tick)
        self.get_logger().info("%d quadros carregados (split teste)" % len(self.quadros))

    def tick(self):
        i, rgb, q = self.quadros[self.k % len(self.quadros)]
        agora = self.get_clock().now().to_msg()
        js = JointState()
        js.header.stamp = agora
        js.name = list(q.keys())
        js.position = [float(v) for v in q.values()]
        self.pub_js.publish(js)
        im = Image()
        im.header.stamp = agora
        im.header.frame_id = self.cam
        im.height, im.width = rgb.shape[:2]
        im.encoding = "rgb8"
        im.step = rgb.shape[1] * 3
        im.data = rgb.tobytes()
        self.pub_img.publish(im)
        self.k += 1


def main():
    rclpy.init()
    no = Publicador()
    try:
        rclpy.spin(no)
    except KeyboardInterrupt:
        pass
    finally:
        no.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
