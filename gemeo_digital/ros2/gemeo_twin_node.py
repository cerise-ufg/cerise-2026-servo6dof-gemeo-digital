#!/usr/bin/env python3
"""
No ROS 2 do gemeo digital: imagem da camera -> Predictor -> /twin/joint_states.

  assina   <camera_topic> (sensor_msgs/Image, QoS sensor: best effort, fila 1)
           /joint_states  (opcional; so para predictors oraculo/ruido, que precisam da referencia)
  publica  /twin/joint_states        (sensor_msgs/JointState, carimbo = carimbo da imagem)
           /twin/latencia_ms         (std_msgs/Float32, tempo do predictor)

Um segundo robot_state_publisher (frame_prefix "twin/", joint_states remapeado para
/twin/joint_states) transforma isso em TF (twin/world -> ... -> twin/base_garra) e o
RViz mostra dois RobotModel: a referencia e o gemeo (ver twin.launch.py).

Parametros: camera_topic (/camera_frontal/image), camera (camera_frontal),
            predictor (gt | ruido | pose | http | auto), pose_dir (~/cerise2026/pose)
"""
import os
import sys
import time

import numpy as np
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSHistoryPolicy, QoSProfile, QoSReliabilityPolicy
from sensor_msgs.msg import Image, JointState
from std_msgs.msg import Float32

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "servidor"))
import predictors  # noqa: E402

QOS_SENSOR = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT, history=QoSHistoryPolicy.KEEP_LAST, depth=1)


def img_para_rgb(msg):
    a = np.frombuffer(msg.data, dtype=np.uint8)
    canais = {"rgb8": 3, "bgr8": 3, "rgba8": 4, "bgra8": 4, "mono8": 1}.get(msg.encoding, 3)
    a = a.reshape(msg.height, msg.step)[:, :msg.width * canais].reshape(msg.height, msg.width, canais)
    if msg.encoding.startswith("bgr"):
        a = a[:, :, 2::-1]
    elif canais == 1:
        a = np.repeat(a, 3, axis=2)
    return np.ascontiguousarray(a[:, :, :3])


class GemeoTwin(Node):
    def __init__(self):
        super().__init__("gemeo_twin")
        self.declare_parameter("camera_topic", "/camera_frontal/image")
        self.declare_parameter("camera", "camera_frontal")
        self.declare_parameter("predictor", "auto")
        self.declare_parameter("pose_dir", os.path.expanduser("~/cerise2026/pose"))
        self.camera = self.get_parameter("camera").value
        self.pred, aviso = predictors.carregar_predictor(self.get_parameter("predictor").value,
                                                         self.get_parameter("pose_dir").value)
        if aviso:
            self.get_logger().warn(aviso)
        self.get_logger().info("predictor: " + self.pred.nome)
        self.ref = None
        self.pub = self.create_publisher(JointState, "/twin/joint_states", 10)
        self.pub_lat = self.create_publisher(Float32, "/twin/latencia_ms", 10)
        self.create_subscription(Image, self.get_parameter("camera_topic").value, self.cb_img, QOS_SENSOR)
        if getattr(self.pred, "usa_meta", False):
            self.create_subscription(JointState, "/joint_states", self.cb_ref, 10)
        self.n = 0

    def cb_ref(self, msg):
        self.ref = dict(zip(msg.name, msg.position))

    def cb_img(self, msg):
        rgb = img_para_rgb(msg)
        meta = None
        if getattr(self.pred, "usa_meta", False):
            if self.ref is None:
                return
            meta = {"juntas_reais": {j: self.ref[j] for j in predictors.JUNTAS[:5] if j in self.ref},
                    "garra_comandada": {"joint_6": self.ref.get("joint_6", 0.0)}}
        t0 = time.perf_counter()
        q = predictors.chamar(self.pred, rgb, self.camera, meta)
        lat = 1000 * (time.perf_counter() - t0)
        js = JointState()
        js.header.stamp = msg.header.stamp
        js.name = list(q.keys())
        js.position = [float(v) for v in q.values()]
        self.pub.publish(js)
        self.pub_lat.publish(Float32(data=float(lat)))
        self.n += 1
        if self.n % 20 == 0:
            self.get_logger().info("%d quadros -> /twin/joint_states (ultimo: %.2f ms)" % (self.n, lat))


def main():
    rclpy.init()
    no = GemeoTwin()
    try:
        rclpy.spin(no)
    except KeyboardInterrupt:
        pass
    finally:
        no.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
