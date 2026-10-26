import threading
import time

import rclpy
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

rclpy.init()
n = Node("ff")
estado = {}
n.create_subscription(
    JointState, "/joint_states",
    lambda m: estado.update(dict(zip(m.name, m.position))), 10)
cli = ActionClient(n, FollowJointTrajectory,
                   "/arm_controller/follow_joint_trajectory")

ex = MultiThreadedExecutor()
ex.add_node(n)
threading.Thread(target=ex.spin, daemon=True).start()

cli.wait_for_server(timeout_sec=10)
time.sleep(2)
print("antes:", {j: round(estado.get(j, 0), 2)
                 for j in ["joint_1", "joint_2", "joint_3"]})

alvo = [1.3, 0.9, -1.0, 0.6, -0.7]
tr = JointTrajectory()
tr.joint_names = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
p = JointTrajectoryPoint()
p.positions = alvo
p.time_from_start.sec = 1
tr.points = [p]
g = FollowJointTrajectory.Goal()
g.trajectory = tr

# DISPARA E ESQUECE: nao espera nem accept nem result
cli.send_goal_async(g)
print("disparado (sem esperar). alvo:", alvo[:3])

for s in [1.5, 3.0, 5.0]:
    time.sleep(s if s == 1.5 else s - 1.5)
    print("apos {:.1f}s:".format(s), {j: round(estado.get(j, 0), 2)
          for j in ["joint_1", "joint_2", "joint_3"]})
rclpy.shutdown()
