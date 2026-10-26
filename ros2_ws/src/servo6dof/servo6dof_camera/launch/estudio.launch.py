"""
Sobe o "estudio fotografico" completo:

    Gazebo (mundo estudio.sdf, com 2 cameras)
      + robot_state_publisher (URDF do servo6dof)
      + spawn do braco
      + ros2_control (joint_state_broadcaster, arm_controller, gripper_controller)
      + ponte Gazebo->ROS de /clock e das imagens das cameras

Uso:
    ros2 launch servo6dof_camera estudio.launch.py
    ros2 launch servo6dof_camera estudio.launch.py headless:=true   # sem janela do Gazebo
"""
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    RegisterEventHandler,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg_description = get_package_share_directory("servo6dof_description")
    pkg_camera = get_package_share_directory("servo6dof_camera")

    headless_arg = DeclareLaunchArgument(
        "headless",
        default_value="false",
        description="true = roda o Gazebo sem interface grafica (so servidor)",
    )
    headless = LaunchConfiguration("headless")

    # Modo HD: 1920x1080 com RGB + profundidade + segmentacao, render ogre2.
    # EXIGE a GPU liberada (usuario no grupo 'render'), senao o ogre2 aborta.
    hd_arg = DeclareLaunchArgument(
        "hd",
        default_value="false",
        description="true = estudio_hd.sdf (1920x1080, RGB+depth+segmentacao, ogre2)",
    )
    hd = LaunchConfiguration("hd")

    world_sd = os.path.join(pkg_camera, "worlds", "estudio.sdf")
    world_hd = os.path.join(pkg_camera, "worlds", "estudio_hd.sdf")

    model_arg = DeclareLaunchArgument(
        "model",
        default_value=os.path.join(pkg_description, "urdf", "servo6dof.urdf.xacro"),
        description="Caminho absoluto do xacro do robo",
    )

    # Para o Gazebo achar as malhas referenciadas como package://servo6dof_description/...
    # precisamos apontar o resource path para a pasta share/ (pai do pacote).
    share_parent = str(Path(pkg_description).parent.resolve())
    resource_path_gz = SetEnvironmentVariable("GZ_SIM_RESOURCE_PATH", share_parent)
    resource_path_ign = SetEnvironmentVariable("IGN_GAZEBO_RESOURCE_PATH", share_parent)

    # Renderizacao por GPU no WSL: o ogre2 aborta no driver D3D12/EGL (cai para
    # software), mas funciona com o zink (OpenGL sobre Vulkan). Definido mais
    # abaixo, so no modo HD. A GPU precisa estar liberada (grupo 'render').

    # No Humble o par correto e' Ignition Fortress -> is_ignition:=true
    is_ignition = "true" if os.environ.get("ROS_DISTRO") == "humble" else "false"

    robot_description = ParameterValue(
        Command(["xacro ", LaunchConfiguration("model"), " is_ignition:=", is_ignition]),
        value_type=str,
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        output="screen",
        parameters=[{"robot_description": robot_description, "use_sim_time": True}],
    )

    # -r = start rodando (nao pausado); -s = server only (headless); -v 4 = verbose
    # O mundo e' escolhido em tempo de execucao pelo argumento 'hd'.
    mundo = PythonExpression(
        ["'", world_hd, "' if '", hd, "'.lower() in ('true','1') else '", world_sd, "'"]
    )
    gazebo_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")
        ),
        launch_arguments=[("gz_args", [" -r -v 4 ", mundo])],
        condition=UnlessCondition(headless),
    )

    gazebo_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(get_package_share_directory("ros_gz_sim"), "launch", "gz_sim.launch.py")
        ),
        launch_arguments=[("gz_args", [" -r -s -v 4 ", mundo])],
        condition=IfCondition(headless),
    )

    spawn_robo = Node(
        package="ros_gz_sim",
        executable="create",
        output="screen",
        arguments=["-topic", "robot_description", "-name", "servo6dof", "-z", "0.0"],
    )

    # ---- pontes Gazebo -> ROS ----
    bridge_clock = Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        output="screen",
        arguments=["/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock"],
    )

    # image_bridge republica a imagem do Gazebo como sensor_msgs/Image no mesmo topico.
    # No modo padrao sao so as duas RGB; no modo HD entram tambem profundidade
    # e segmentacao de cada camera.
    bridge_imagens = Node(
        package="ros_gz_image",
        executable="image_bridge",
        output="screen",
        arguments=["/camera_frontal/image", "/camera_diagonal/image"],
        parameters=[{"use_sim_time": True}],
        condition=UnlessCondition(hd),
    )

    # A camera de segmentacao publica em subtopicos: .../labels_map (mascara
    # com o id de cada objeto) e .../colored_map (versao colorida para ver).
    # Usamos labels_map, que e' o que serve para treinar. O topico base
    # /camera_.../segmentation nao existe -- por isso a ponte aponta para o
    # labels_map diretamente.
    bridge_imagens_hd = Node(
        package="ros_gz_image",
        executable="image_bridge",
        output="screen",
        arguments=[
            "/camera_frontal/image",
            "/camera_frontal/depth",
            "/camera_frontal/segmentation/labels_map",
            "/camera_diagonal/image",
            "/camera_diagonal/depth",
            "/camera_diagonal/segmentation/labels_map",
        ],
        parameters=[{"use_sim_time": True}],
        condition=IfCondition(hd),
    )

    # ---- controladores ----
    def spawner(nome):
        return Node(
            package="controller_manager",
            executable="spawner",
            output="screen",
            arguments=[nome, "--controller-manager", "/controller_manager"],
        )

    jsb_spawner = spawner("joint_state_broadcaster")
    arm_spawner = spawner("arm_controller")
    gripper_spawner = spawner("gripper_controller")

    # Encadeamento: so spawna controlador depois que o robo entrou no Gazebo.
    apos_spawn = RegisterEventHandler(
        OnProcessExit(target_action=spawn_robo, on_exit=[jsb_spawner])
    )
    apos_jsb = RegisterEventHandler(
        OnProcessExit(target_action=jsb_spawner, on_exit=[arm_spawner])
    )
    apos_arm = RegisterEventHandler(
        OnProcessExit(target_action=arm_spawner, on_exit=[gripper_spawner])
    )

    acoes = [
        headless_arg,
        hd_arg,
        model_arg,
        resource_path_gz,
        resource_path_ign,
    ]
    # zink so no modo HD (ogre2). No modo padrao o ogre1 roda por software
    # sem problema, e forcar zink so atrasaria a inicializacao.
    # O driver pode ser trocado pela env RENDER_DRIVER_OVERRIDE: no WSL (Iris Xe)
    # o padrao 'zink' (OpenGL sobre Vulkan do Mesa); numa GPU NVIDIA real
    # (ex.: DGX Spark) exporte RENDER_DRIVER_OVERRIDE="" para o ogre2 usar o
    # EGL da NVIDIA diretamente, sem passar pelo Mesa.
    _render_override = os.environ.get("RENDER_DRIVER_OVERRIDE", "zink")
    acoes.append(SetEnvironmentVariable(
        "MESA_LOADER_DRIVER_OVERRIDE",
        PythonExpression(
            ["'", _render_override, "' if '", hd, "'.lower() in ('true','1') else ''"]
        ),
    ))

    return LaunchDescription(acoes + [
        robot_state_publisher,
        gazebo_gui,
        gazebo_headless,
        spawn_robo,
        bridge_clock,
        bridge_imagens,
        bridge_imagens_hd,
        apos_spawn,
        apos_jsb,
        apos_arm,
    ])
