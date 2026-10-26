import time
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

rclpy.init()
n = Node("tj")
estado = {}
n.create_subscription(JointState, "/joint_states",
    lambda m: estado.update(dict(zip(m.name, m.position))), 10)
pub = n.create_publisher(JointTrajectory, "/arm_controller/joint_trajectory", 10)

# espera joint_states e conexao do publisher
t = time.time()
while time.time() - t < 5:
    rclpy.spin_once(n, timeout_sec=0.1)
print("antes:", {j: round(estado.get(j, 0), 3) for j in ["joint_1","joint_2","joint_3"]})
print("subscritos no meu pub:", pub.get_subscription_count())

alvo = [1.2, 0.8, -0.9, 0.5, -0.6]
tr = JointTrajectory()
tr.joint_names = ["joint_1","joint_2","joint_3","joint_4","joint_5"]
p = JointTrajectoryPoint()
p.positions = alvo
p.time_from_start.sec = 1
tr.points = [p]
pub.publish(tr)
print("publicado alvo:", alvo[:3])

t = time.time()
while time.time() - t < 4:
    rclpy.spin_once(n, timeout_sec=0.1)
print("depois:", {j: round(estado.get(j, 0), 3) for j in ["joint_1","joint_2","joint_3"]})
rclpy.shutdown()
