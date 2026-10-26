import time

import rclpy
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

rclpy.init()
n = Node("mv")
est = {}
n.create_subscription(
    JointState, "/joint_states",
    lambda m: est.update(dict(zip(m.name, m.position))), 10)
c = ActionClient(n, FollowJointTrajectory,
                 "/arm_controller/follow_joint_trajectory")
print("server:", c.wait_for_server(timeout_sec=10))

t = time.time()
while time.time() - t < 3:
    rclpy.spin_once(n, timeout_sec=0.1)
print("antes:", {j: round(est.get(j, -9), 2) for j in
                 ["joint_1", "joint_2", "joint_3"]})

alvo = [1.3, 0.9, -1.0, 0.5, -0.6]
tr = JointTrajectory()
tr.joint_names = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
p = JointTrajectoryPoint()
p.positions = alvo
p.time_from_start.sec = 3
tr.points = [p]
g = FollowJointTrajectory.Goal()
g.trajectory = tr
f = c.send_goal_async(g)
rclpy.spin_until_future_complete(n, f, timeout_sec=10)
h = f.result()
print("accepted:", h.accepted if h else None)
fr = h.get_result_async()
rclpy.spin_until_future_complete(n, fr, timeout_sec=30)
print("result status:", fr.result().status)
t = time.time()
while time.time() - t < 1:
    rclpy.spin_once(n, timeout_sec=0.1)
print("depois:", {j: round(est.get(j, -9), 2) for j in
                  ["joint_1", "joint_2", "joint_3"]}, "alvo", alvo[:3])
rclpy.shutdown()
