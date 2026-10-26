#!/usr/bin/env python3
"""Gera uma variante do URDF do servo6dof com hardware FALSO do ros2_control
(mock_components/GenericSystem) para rodar MoveIt 2 + ros2_control sem Gazebo.

- troca ign_ros2_control/IgnitionSystem por mock_components/GenericSystem;
- remove o bloco <gazebo> (plugin do Ignition);
- remove joint_7 do <ros2_control> (mimic tratado pelo robot_state_publisher);
- define initial_value = 0 nas interfaces de estado.
Uso: python3 urdf_fake.py <entrada.urdf> <saida.urdf>
"""
import sys
import xml.etree.ElementTree as ET

ent, sai = sys.argv[1], sys.argv[2]
arv = ET.parse(ent)
r = arv.getroot()
for g in r.findall("gazebo"):
    r.remove(g)
for rc in r.findall("ros2_control"):
    hw = rc.find("hardware/plugin")
    hw.text = "mock_components/GenericSystem"
    for j in list(rc.findall("joint")):
        if j.find("param[@name='mimic']") is not None:
            rc.remove(j)
            continue
        for si in j.findall("state_interface"):
            if si.find("param[@name='initial_value']") is None:
                p = ET.SubElement(si, "param", {"name": "initial_value"})
                p.text = "0.0"
arv.write(sai, encoding="unicode")
print("URDF com hardware falso:", sai)
