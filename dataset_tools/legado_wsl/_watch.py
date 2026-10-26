import time

import rclpy
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from rclpy.node import Node
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

rclpy.init()
n = Node("tw")
est = {}
n.create_subscription(
    JointState, "/joint_states",
    lambda m: est.update(dict(zip(m.name, m.position))), 10)
c = ActionClient(n, FollowJointTrajectory,
                 "/arm_controller/follow_joint_trajectory")
c.wait_for_server(timeout_sec=10)

alvo = [1.2, 0.8, -0.9, 0.5, -0.6]
tr = JointTrajectory()
tr.joint_names = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5"]
p = JointTrajectoryPoint()
p.positions = alvo
p.time_from_start.sec = 2
tr.points = [p]
g = FollowJointTrajectory.Goal()
g.trajectory = tr

f = c.send_goal_async(g)
rclpy.spin_until_future_complete(n, f, timeout_sec=10)
h = f.result()
print("accepted:", h.accepted)
fr = h.get_result_async()
for i in range(15):
    t = time.time()
    while time.time() - t < 1:
        rclpy.spin_once(n, timeout_sec=0.05)
    st = fr.result().status if fr.done() else "pend"
    j1 = est.get("joint_1", 0)
    j2 = est.get("joint_2", 0)
    j3 = est.get("joint_3", 0)
    print("  {}s j1={:.2f} j2={:.2f} j3={:.2f} status={}".format(
        i + 1, j1, j2, j3, st))
rclpy.shutdown()
