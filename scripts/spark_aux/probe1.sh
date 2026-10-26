#!/bin/bash
sudo docker images --format '{{.Repository}}:{{.Tag}}\t{{.Size}}' | head -30
python3 -c 'import numpy, matplotlib, PIL; print(numpy.__version__, matplotlib.__version__, PIL.__version__)'
python3 --version
sudo docker run --rm servo6dof:humble bash -c 'ls /opt/ros/humble/share | grep -i -E "moveit|kdl|tf2_ros|urdf|joint_state" | head -30; python3 -c "import numpy;print(numpy.__version__)"; python3 -c "import scipy; print(scipy.__version__)"'
ls -la ~/cerise2026
df -h ~ | tail -1
grep -n '<pose' ~/braco/src/servo6dof/servo6dof_camera/worlds/estudio_hd.sdf
grep -n '<model name' ~/braco/src/servo6dof/servo6dof_camera/worlds/estudio_hd.sdf
which node npm graphviz dot pip3 2>&1
