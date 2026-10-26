#!/usr/bin/env bash
# Prepara o shell para trabalhar no projeto do braco servo6dof.
#
# Uso (dentro do WSL Ubuntu-22.04):
#     source /mnt/e/cerise/braco/ambiente.sh
#
# Dica: para nao digitar isso toda vez, coloque a linha acima no fim do
# seu ~/.bashrc.

export WS=/mnt/e/cerise/braco

source /opt/ros/humble/setup.bash
if [ -f "$WS/install/setup.bash" ]; then
    source "$WS/install/setup.bash"
fi

# WSLg: interface grafica (RViz, Gazebo, MoveIt Setup Assistant)
export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/1000

# Cada maquina na rede usa um dominio proprio para os nos ROS nao se
# misturarem. Troque o numero se estiver dividindo a rede com colegas.
export ROS_DOMAIN_ID=0

# Onde o Gazebo procura as malhas referenciadas como package://...
export GZ_SIM_RESOURCE_PATH="$WS/install"
export IGN_GAZEBO_RESOURCE_PATH="$WS/install"

alias ws="cd $WS"
alias cb="cd $WS && colcon build --symlink-install && source $WS/install/setup.bash"

echo "ambiente servo6dof pronto  |  ROS_DISTRO=$ROS_DISTRO  DISPLAY=$DISPLAY"
echo "  ws  -> vai para $WS"
echo "  cb  -> recompila o workspace"
