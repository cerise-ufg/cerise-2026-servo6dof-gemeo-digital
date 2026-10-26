# Configurando o MoveIt 2 pelo Setup Assistant — servo6dof

Passo a passo da interface gráfica, com as escolhas certas **para este braço**.

Abrir:

```bash
source /mnt/e/cerise/braco/ambiente.sh
ros2 run moveit_setup_assistant moveit_setup_assistant
```

> O Setup Assistant **gera um pacote novo**. Ele não altera o
> `servo6dof_moveit` que já existe. Gere em
> `src/servo6dof/servo6dof_moveit_config` e depois compare com o que já está
> pronto — as diferenças são o aprendizado.

---

## Antes de começar: o robô

| | |
|---|---|
| Juntas do braço | `joint_1` … `joint_5` — **5 graus de liberdade**, não 6 |
| Junta da garra | `joint_6` (a que realmente se comanda) |
| Juntas `mimic` | `joint_7`, `joint_garra_1`, `joint_garra_3`, `joint_pinca_a`, `joint_pinca_b` |
| Elo base | `base_link` (preso ao `world` por junta fixa `virtual_joint`) |
| Ponta do braço | `base_garra` |

As juntas `mimic` copiam o `joint_6` automaticamente. **Não** se planeja para
elas — é o erro mais comum aqui.

---

## 1. Start

**Create New MoveIt Configuration Package** → *Browse* →

```
/mnt/e/cerise/braco/src/servo6dof/servo6dof_description/urdf/servo6dof.urdf.xacro
```

→ **Load Files**.

O braço deve aparecer no visualizador à direita. Se não aparecer, o xacro não
carregou — confira o terminal.

---

## 2. Self-Collisions

Clique em **Generate Collision Matrix** (densidade padrão, 10000 amostras).

Ele testa pares de elos e desabilita a checagem entre os que:

- são **Adjacent** (vizinhos na cadeia — sempre se tocam),
- **Never** colidem em nenhuma amostra,
- estão **Always** colidindo (geometria sobreposta no modelo).

Para este robô saem ~48 pares desabilitados.

> **Por que isso importa:** o SRDF que veio no pacote usava a tag
> `<disable_collision>` (singular). O MoveIt só entende
> `<disable_collisions>` (**plural**) — as sete linhas eram silenciosamente
> ignoradas, o braço se via em auto-colisão permanente e **nenhum plano era
> encontrado**. Duas dessas linhas ainda citavam elos inexistentes
> (`garra_elo_1`, `garra_elo_2a`; os reais são `garra_elo1`, `garra_elo2a`).

---

## 3. Virtual Joints

**Pode pular.** O URDF já tem um elo `world` preso ao `base_link` por uma junta
fixa chamada `virtual_joint`. Se o assistente reclamar, é só aviso.

---

## 4. Planning Groups

### Grupo `arm`

*Add Group* →

| campo | valor |
|---|---|
| Group Name | `arm` |
| Kinematic Solver | `kdl_kinematics_plugin/KDLKinematicsPlugin` |
| Kin. Search Resolution / Timeout | padrão |

→ **Add Kin. Chain** → Base Link `base_link`, Tip Link `base_garra` → *Save*.

> Use **cadeia**, não lista de juntas. Listando à mão é fácil incluir a junta
> fixa `virtual_joint` no grupo — e junta fixa não pode fazer parte de um grupo
> de planejamento.

### Grupo `gripper`

*Add Group* → Group Name `gripper`, **sem** solver (`None`) →
**Add Joints** → selecione **apenas `joint_6`** → *Save*.

> Não inclua as cinco juntas `mimic`. O SRDF original incluía, e o MoveIt não
> planeja para juntas mimic.

---

## 5. Robot Poses

Crie ao menos:

| nome | grupo | valores |
|---|---|---|
| `home` | arm | tudo 0 |
| `recolhido` | arm | j2 = −1,20 · j3 = +1,20 · resto 0 |
| `estendido` | arm | j2 = +0,90 · j3 = −0,60 · j5 = +0,30 |
| `aberta` | gripper | j6 = −0,60 |
| `fechada` | gripper | j6 = +0,45 |

---

## 6. End Effectors

*Add End Effector*:

| campo | valor |
|---|---|
| Name | `garra` |
| End Effector Group | `gripper` |
| Parent Link | `base_garra` |
| Parent Group | `arm` |

---

## 7. Passive Joints

**Marque como passivas** as cinco juntas `mimic`:

`joint_7`, `joint_garra_1`, `joint_garra_3`, `joint_pinca_a`, `joint_pinca_b`

Assim o MoveIt sabe que elas existem mas não são comandáveis.

---

## 8. ros2_control URDF Modification

**Pule.** O URDF já traz o bloco `<ros2_control>` com o plugin
`ign_ros2_control/IgnitionSystem`, que é o certo para Gazebo Fortress no
Humble. Deixar o assistente reescrever isso quebra a simulação.

---

## 9. ROS 2 Controllers

*Add Controller* duas vezes:

| nome | tipo | juntas |
|---|---|---|
| `arm_controller` | `joint_trajectory_controller/JointTrajectoryController` | joint_1 … joint_5 |
| `gripper_controller` | `joint_trajectory_controller/JointTrajectoryController` | joint_6 |

Os mesmos nomes já usados em `servo6dof_controller/config/servo6dof_controllers.yaml`.

---

## 10. MoveIt Controllers

*Add Controller* → mesmos dois nomes, tipo **`FollowJointTrajectory`**.

> **Aqui mora o segundo bug do pacote original.** O `moveit_controllers.yaml`
> tinha:
>
> ```yaml
> moveit_controller_manage: ...          # faltava o "r" de manager
>   action_ns: follow_joint trajectory   # espaço no lugar do "_"
> ```
>
> Com isso o MoveIt até planeja, mas na hora de executar responde
> *"Unable to identify any set of controllers"*. O correto é
> `moveit_controller_manager` e `follow_joint_trajectory`.

---

## 11. Perception

`None` — não há câmera declarada no URDF (a câmera do projeto está no **mundo**
do Gazebo, não no robô).

---

## 12–14. Launch Files · Author · Generate

- **Launch Files:** deixe o padrão.
- **Author Information:** nome e e-mail (obrigatório para gerar).
- **Configuration Files:** escolha
  `/mnt/e/cerise/braco/src/servo6dof/servo6dof_moveit_config`
  → **Generate Package**.

---

## Depois de gerar

### Ajuste obrigatório: braço de 5 juntas

Um braço de 5 DOF **não alcança uma pose 6D qualquer** (posição + orientação
completas). Sem ajuste, arrastar o marcador no RViz quase sempre dá
`NO_IK_SOLUTION`.

Edite `config/kinematics.yaml` do pacote gerado:

```yaml
arm:
  kinematics_solver: kdl_kinematics_plugin/KDLKinematicsPlugin
  kinematics_solver_search_resolution: 0.005
  kinematics_solver_timeout: 0.005
  position_only_ik: True      # <-- acrescente esta linha
```

Assim a IK resolve só a **posição** da ponta e ignora a orientação.

### Compilar e testar

```bash
cd /mnt/e/cerise/braco && colcon build --symlink-install
source install/setup.bash
```

Terminal 1 — simulação:

```bash
ros2 launch servo6dof_camera estudio.launch.py
```

Terminal 2 — MoveIt + RViz:

```bash
ros2 launch servo6dof_moveit_config move_group.launch.py
ros2 launch servo6dof_moveit_config moveit_rviz.launch.py
```

No RViz, painel **MotionPlanning**:

1. aba **Planning** → *Planning Group*: `arm`
2. em *Goal State* escolha uma pose nomeada (ex.: `recolhido`) ou arraste o
   marcador interativo
3. **Plan** → aparece a prévia da trajetória
4. **Execute** → o braço se move no Gazebo

### Teste sem a interface

```bash
ros2 run servo6dof_moveit testar_planejamento.py
```

Percorre quatro poses e imprime o código de erro do MoveIt em cada uma —
útil para saber se o problema é planejamento ou execução.

---

## Problemas que aparecem neste robô (e a solução)

Estes quatro apareceram de verdade ao pôr o pacote para rodar. Vale conferir
cada um depois de gerar a configuração.

### 1. `disable_collision` no singular → nenhum plano é encontrado

O SRDF original usava `<disable_collision>`. O MoveIt só lê
`<disable_collisions>` (plural) e ignora o resto em silêncio.
**O Setup Assistant escreve certo** — é só regerar.

### 2. Auto-colisão da garra no estado inicial

Sintoma no log do `move_group`:

```
Found a contact between 'garra_elo3b' and 'base_garra' ... constitutes a collision
Start state appears to be in collision with respect to group arm
[ompl] Skipping invalid start state (invalid state)
[ompl] RRTConnect: Motion planning start tree could not be initialized!
```

e o objetivo volta com `FAILURE` (99999).

A amostragem aleatória do *Generate Collision Matrix* desabilita quase todos
os pares internos da garra, mas escapa pelo menos um. Como a pose relativa
dessas peças depende **só** do `joint_6`, nenhum plano evita esse contato —
checar colisão entre elas não serve para nada.

**Solução:** na aba *Self-Collisions*, depois de gerar a matriz, marque à mão
todos os pares entre `base_garra`, `garra_elo1`, `garra_elo2`, `garra_elo2a`,
`garra_elo2b`, `garra_elo3a` e `garra_elo3b` (21 pares).

### 3. `CONTROL_FAILED` a cada movimento

Sintoma:

```
[moveit_ros.current_state_monitor]: No state update received within 100ms of system clock
[moveit_ros.trajectory_execution_manager]: Validating trajectory with allowed_start_tolerance 0.01
Solution found but controller failed during execution
```

Não é do MoveIt: em `servo6dof_controller/config/servo6dof_controllers.yaml`
o `controller_manager` estava com `update_rate: 10`. A 10 Hz os
`/joint_states` chegam a cada 100 ms — exatamente o limite em que o MoveIt
considera o estado desatualizado e recusa a trajetória.

**Solução:** `update_rate: 100`.

### 4. `NO_IK_SOLUTION` ao arrastar o marcador

Braço de 5 juntas não alcança pose 6D arbitrária. Ver
*"Ajuste obrigatório"* acima (`position_only_ik: True`).
