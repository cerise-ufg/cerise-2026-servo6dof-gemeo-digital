cmake_minimum_required(VERSION 3.8)
project(servo6dof_camera)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch worlds config
  DESTINATION share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/tirar_fotos.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
