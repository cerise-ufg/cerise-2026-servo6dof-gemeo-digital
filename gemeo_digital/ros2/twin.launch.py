"""Gemeo digital em ROS 2: imagem -> /twin/joint_states -> TF com prefixo twin/ -> RViz.

    ros2 launch twin.launch.py urdf:=<servo6dof.urdf> predictor:=auto \
         camera_topic:=/camera_frontal/image rviz:=false offset_y:=3.0

Sobe: robot_state_publisher do GEMEO (frame_prefix twin/, /joint_states -> /twin/joint_states),
TF estatico world -> twin/world (deslocado em y para ver lado a lado), o no gemeo_twin e,
opcionalmente, o RViz com dois RobotModel (referencia e gemeo). A referencia (robot_state_publisher
sem prefixo) vem da simulacao (estudio.launch.py) ou do robo real.
"""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

AQUI = os.path.dirname(os.path.abspath(__file__))


def gerar(context):
    lc = lambda n: LaunchConfiguration(n).perform(context)  # noqa: E731
    urdf = open(lc("urdf")).read()
    return [
        Node(package="robot_state_publisher", executable="robot_state_publisher", name="rsp_twin",
             parameters=[{"robot_description": urdf, "frame_prefix": "twin/"}],
             remappings=[("joint_states", "/twin/joint_states"), ("robot_description", "/twin/robot_description")]),
        Node(package="tf2_ros", executable="static_transform_publisher", name="tf_twin",
             arguments=["--x", "0", "--y", lc("offset_y"), "--z", "0", "--frame-id", "world",
                        "--child-frame-id", "twin/world"]),
        Node(executable=os.path.join(AQUI, "gemeo_twin_node.py"), name="gemeo_twin", output="screen",
             parameters=[{"predictor": lc("predictor"), "camera_topic": lc("camera_topic"),
                          "camera": lc("camera_topic").strip("/").split("/")[0]}]),
        Node(package="rviz2", executable="rviz2", arguments=["-d", os.path.join(AQUI, "gemeo.rviz")],
             condition=IfCondition(lc("rviz"))),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("urdf"),
        DeclareLaunchArgument("predictor", default_value="auto"),
        DeclareLaunchArgument("camera_topic", default_value="/camera_frontal/image"),
        DeclareLaunchArgument("offset_y", default_value="3.0"),
        DeclareLaunchArgument("rviz", default_value="false"),
        OpaqueFunction(function=gerar),
    ])
