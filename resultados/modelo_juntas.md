| Junta | Tipo | Pai -> filho | Origem xyz (m) | Origem rpy (rad) | Eixo | Limites (graus) | Mimic |
|---|---|---|---|---|---|---|---|
| virtual_joint | fixed | world -> base_link | (0, 0, 0) | (0, 0, 0) | (1, 0, 0) | - | - |
| joint_1 | revolute | base_link -> primeiro_elo | (0, -0.23, -0.01) | (0, 0, 0) | (0, 0, 1) | [-90, 90] | - |
| joint_2 | revolute | primeiro_elo -> segundo_elo | (-0.05, -0.03, 0.57) | (0, 0, 0) | (1, 0, 0) | [-90, 90] | - |
| joint_3 | revolute | segundo_elo -> terceiro_elo | (0.06, 0, 0.63) | (0, 0, 0) | (1, 0, 0) | [-90, 90] | - |
| joint_4 | revolute | terceiro_elo -> quarto_elo | (0, 0.78, 0) | (0, 0, 0) | (1, 0, 0) | [-90, 90] | - |
| joint_5 | revolute | quarto_elo -> base_garra | (0.02, 0.36, 0) | (0, 0, 0) | (0, 1, 0) | [-90, 90] | - |
| joint_6 | revolute | base_garra -> garra_elo1 | (-0.072, 0.12, 0.01) | (0, 0, 0) | (0, 0, 1) | [-40, 30] | - |
| joint_garra_1 | revolute | base_garra -> garra_elo2a | (-0.05, 0.27, 0.01) | (0, 0, 0) | (0, 0, 1) | [-90, 90] | joint_6 x 1 -0.2 |
| joint_pinca_a | revolute | garra_elo1 -> garra_elo3a | (-0.13, 0.13, 0) | (0, 0, -1.571) | (0, 0, 1) | - | joint_6 x -1 +0.2 |
| joint_7 | revolute | base_garra -> garra_elo2 | (0.072, 0.12, 0.01) | (0, 0, 0) | (0, 0, 1) | [-30, 30] | joint_6 x -1 +0 |
| joint_garra_3 | revolute | base_garra -> garra_elo2b | (0.04, 0.27, 0.01) | (0, 0, 0) | (0, 0, 1) | [-90, 90] | joint_6 x -1 -1.6708 |
| joint_pinca_b | revolute | garra_elo2 -> garra_elo3b | (0.13, 0.13, 0) | (0, 0, 1.571) | (0, 0, 1) | - | joint_6 x 1 -0.2 |
