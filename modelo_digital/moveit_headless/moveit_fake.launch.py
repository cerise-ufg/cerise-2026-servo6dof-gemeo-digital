"""MoveIt 2 headless com hardware falso (mock_components) para o servo6dof.

Sobe: robot_state_publisher + ros2_control_node (GenericSystem) + spawners
(joint_state_broadcaster, arm_controller, gripper_controller) + move_group
(OMPL, KDL). Sem RViz e sem Gazebo.
    ros2 launch moveit_fake.launch.py urdf:=/caminho/servo6dof_fake.urdf
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import OpaqueFunction, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from moveit_configs_utils import MoveItConfigsBuilder


def gerar(context):
    urdf = LaunchConfiguration("urdf").perform(context)
    descricao = open(urdf).read()
    pkg_ctrl = get_package_share_directory("servo6dof_controller")
    ctrl_yaml = os.path.join(pkg_ctrl, "config", "servo6dof_controllers.yaml")

    moveit_config = (
        MoveItConfigsBuilder("servo6dof", package_name="servo6dof_moveit")
        .robot_description(file_path=urdf)
        .robot_description_semantic(file_path="config/servo6dof.srdf")
        .robot_description_kinematics(file_path="config/kinematics.yaml")
        .joint_limits(file_path="config/joint_limits.yaml")
        .trajectory_execution(file_path="config/moveit_controllers.yaml")
        .planning_pipelines(default_planning_pipeline="ompl", pipelines=["ompl"])
        .planning_scene_monitor(publish_robot_description=True, publish_robot_description_semantic=True)
        .to_moveit_configs()
    )

    rsp = Node(package="robot_state_publisher", executable="robot_state_publisher", output="log",
               parameters=[{"robot_description": descricao}])
    cm = Node(package="controller_manager", executable="ros2_control_node", output="log",
              parameters=[{"robot_description": descricao}, ctrl_yaml])
    spawn = [Node(package="controller_manager", executable="spawner", output="log",
                  arguments=[n, "--controller-manager", "/controller_manager"])
             for n in ("joint_state_broadcaster", "arm_controller", "gripper_controller")]
    mg = Node(package="moveit_ros_move_group", executable="move_group", output="screen",
              parameters=[moveit_config.to_dict(), {"use_sim_time": False}])
    return [rsp, cm, *spawn, mg]


def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument("urdf"), OpaqueFunction(function=gerar)])
