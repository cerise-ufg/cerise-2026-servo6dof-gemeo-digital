import time

import rclpy
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

rclpy.init()
n = Node("ta")
estado = {}
n.create_subscription(
    JointState, "/joint_states",
    lambda m: estado.update(dict(zip(m.name, m.position))), 10)
cli = ActionClient(n, FollowJointTrajectory,
                   "/arm_controller/follow_joint_trajectory")
cli.wait_for_server(timeout_sec=10)

alvo = [1.2, 0.8, -0.9, 0.5, -0.6]
tr = JointTrajectory()
tr.joint_names = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
p = JointTrajectoryPoint()
p.positions = alvo
p.time_from_start.sec = 1
tr.points = [p]
g = FollowJointTrajectory.Goal()
g.trajectory = tr

t0 = time.time()
fut = cli.send_goal_async(g)
rclpy.spin_until_future_complete(n, fut, timeout_sec=10)
h = fut.result()
print("aceito em {:.2f}s accepted={}".format(
    time.time() - t0, h.accepted if h else None))
fr = h.get_result_async()
rclpy.spin_until_future_complete(n, fr, timeout_sec=30)
print("RESULTADO em {:.2f}s".format(time.time() - t0))
t = time.time()
while time.time() - t < 1:
    rclpy.spin_once(n, timeout_sec=0.1)
print("juntas:", {j: round(estado.get(j, 0), 3)
                  for j in ["joint_1", "joint_2", "joint_3"]},
      "alvo", alvo[:3])
rclpy.shutdown()
