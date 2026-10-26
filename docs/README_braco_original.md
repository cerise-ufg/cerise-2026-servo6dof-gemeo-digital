# Braço robótico servo6dof — ROS 2 Humble

Projeto do braço de 6 servos (pacote do prof. Alisson) rodando em **ROS 2 Humble +
Ignition Gazebo Fortress**, dentro do **WSL2 (Ubuntu 22.04)**.

Duas frentes:

1. **MoveIt 2** — configurar pelo *Setup Assistant* (interface gráfica) e testar
   planejamento de movimentos.
2. **Câmera no Gazebo** — fotografar o braço em diferentes poses.

---

## Estrutura

```
E:\cerise\braco\
├── ambiente.sh                  # source nele antes de tudo
├── fotos/                       # saída das fotos (gerada)
└── src/servo6dof/
    ├── servo6dof_description/   # URDF/xacro, malhas STL, mundos do professor
    ├── servo6dof_controller/    # ros2_control: arm_controller, gripper_controller
    ├── servo6dof_moveit/        # configuração do MoveIt 2
    └── servo6dof_camera/        # NOVO: estúdio fotográfico no Gazebo
```

O robô é um braço de **5 juntas** (`joint_1`..`joint_5`) mais **1 junta de garra**
(`joint_6`). As outras cinco juntas da garra são `mimic` do `joint_6` — seguem
sozinhas, não se planeja para elas.

---

## Preparar o ambiente

Dentro do WSL (`wsl -d Ubuntu-22.04`):

```bash
source /mnt/e/cerise/braco/ambiente.sh
cb        # atalho: recompila o workspace
```

Se a interface gráfica não abrir (RViz/Gazebo/Setup Assistant), rode no
PowerShell do Windows `wsl --shutdown`, abra o WSL de novo e tente outra vez —
isso reinicializa o WSLg.

---

## 1. MoveIt 2

### Abrir o Setup Assistant

```bash
ros2 run moveit_setup_assistant moveit_setup_assistant
```

O passo a passo de quais opções marcar para *este* robô está em
[`GUIA_MOVEIT.md`](GUIA_MOVEIT.md).

### Testar o planejamento

Três terminais (todos com `source ambiente.sh`):

```bash
# 1 - simulação
ros2 launch servo6dof_camera estudio.launch.py

# 2 - MoveIt + RViz
ros2 launch servo6dof_moveit moveit.launch.py
```

No RViz: painel **MotionPlanning** → aba *Planning* → escolha o grupo `arm`,
arraste a bola/setas do marcador interativo, **Plan** e depois **Execute**.

---

## 2. Câmera no Gazebo

### Subir o estúdio

```bash
ros2 launch servo6dof_camera estudio.launch.py                 # com janela
ros2 launch servo6dof_camera estudio.launch.py headless:=true  # sem janela
```

Isso sobe o mundo `estudio.sdf` (chão, ciclorama de fundo, iluminação e
**duas câmeras**), spawna o braço, liga os controladores e faz a ponte
Gazebo→ROS das imagens.

Tópicos publicados:

| tópico | o que é |
|---|---|
| `/camera_frontal/image` | câmera de frente, 1280x720 |
| `/camera_diagonal/image` | câmera diagonal alta, 1280x720 |

Ver ao vivo:

```bash
ros2 run rqt_image_view rqt_image_view /camera_frontal/image
```

### Tirar as fotos

```bash
ros2 run servo6dof_camera tirar_fotos.py \
  --ros-args -p saida:=/mnt/e/cerise/braco/dataset -p use_sim_time:=true
```

Para cada pose o script move o braço, espera assentar, descarta o buffer de
quadros (para a foto ser posterior ao movimento) e salva um PNG por
câmera/modalidade, mais um `000001.json` com os ângulos daquela captura e um
`poses_registradas.csv` de índice. O CSV é regravado a cada 10 capturas, então
interromper no meio ainda deixa metadados completos.

Parâmetros úteis:

| parâmetro | padrão | o que faz |
|---|---|---|
| `saida` | `~/fotos_servo6dof` | pasta de destino |
| `n_aleatorias` | `0` | se > 0, sorteia N poses cobrindo o espaço de juntas |
| `semente` | `42` | semente do sorteio — mesma semente, mesmas poses |
| `poses_file` | `config/poses.yaml` | usado quando `n_aleatorias` é 0 |
| `duracao` | `3.0` | segundos para executar cada trajetória |
| `assentamento` | `1.5` | segundos de espera antes de fotografar |
| `cameras` | as duas RGB | lista de tópicos de imagem |

Poses fixas ficam em `poses.yaml` (limites: `joint_1..5` em ±π/2, `joint_6`
entre −0,698 e +0,524 rad). Para escalar, use `n_aleatorias`.

---

## 3. Dataset grande — geração em etapas (parar e continuar)

Configuração: **640×480 RGB, 2 câmeras, ogre1** — confiável e sem depender de
GPU. Meta: **10.000 imagens = 5.000 poses**. O fluxo é resumável: dá para
parar quando quiser e continuar depois, sem duplicar nem deixar buraco.

### Comando único (o normal)

```bash
wsl -d Ubuntu-22.04 bash /mnt/e/cerise/braco/rodar.sh
```

É só isso. Ele **gera o plano se faltar**, vê no disco de onde parou, gera em
lotes salvando cada pose na hora, e — se o Gazebo cair numa maratona longa —
**reinicia sozinho e continua**, até bater os 10.000. Pare com `Ctrl+C` quando
quiser; rodar de novo continua exatamente de onde parou. Opcional:
`bash rodar.sh <workers> <poses_por_lote>` (padrão `2 250`).

Ritmo medido: **~17 s/pose por worker**. Com 2 workers, 5.000 poses (10k
imagens) ≈ **12 h**, ~1 GB — divisível em quantas noites quiser.

### Ver o progresso

```bash
python3 /mnt/e/cerise/braco/status_dataset.py
```

### As peças por baixo (se quiser controle fino)

| arquivo | o que faz |
|---|---|
| `plano_poses.json` | a lista fixa das 5.000 poses (a "fonte da verdade") |
| `gerar_plano.py` | gera o `plano_poses.json` (o `rodar.sh` chama sozinho) |
| `rodar.sh` | **o comando único** — loop de lotes com auto-recuperação |
| `continuar.sh [max] [workers]` | um lote só (pula o que já foi feito) |
| `status_dataset.py` | progresso (quanto falta) |

O plano é determinístico (cada pose tem id fixo), então parar e continuar
sempre gera as **mesmas** poses — sem duplicar, sem buraco. Cada pose vira
`{id:06d}.json` + 2 PNGs; a retomada pula os ids que já existem no disco.

### Detalhes que importam (aprendidos na marra)

- **A espera de cada pose é por tempo de simulação** (tópico `/clock`), não
  pela action nem pelos `joint_states`. Isso torna a captura robusta ao fator
  de tempo real baixo e ao `joint_state_broadcaster`, que às vezes não ativa
  no boot.
- **Não adicione o plugin `Label` ao URDF do robô.** Ele quebra os
  controladores (os `joint_states` param de ser publicados e o braço não se
  move). Foi o que impediu a segmentação semântica nesta máquina.
- O mundo HD-multimodal (`estudio_hd.sdf`, com profundidade e segmentação em
  ogre2/zink) existe, mas a GPU integrada (Iris Xe) não o roda de forma
  confiável — o fator de tempo real cai para ~0,1 e o controle do braço fica
  intermitente. Por isso a escolha pelo 640×480 RGB.

### Consolidar no fim

```bash
python3 /mnt/e/cerise/braco/slides/consolidar_dataset.py /mnt/e/cerise/braco/dataset
```

Junta os CSVs dos workers num `index.csv` e confere que toda imagem
referenciada existe.

---

## Notas do ambiente (WSL)

- **Render engine:** o mundo usa `<render_engine>ogre</render_engine>` em vez de
  `ogre2`. O ogre2 precisa de GPU via `/dev/dri/renderD128`, e o usuário não está
  no grupo `render` — a renderização cai para software e o ogre2 **aborta** em
  `GL3PlusTextureGpu::copyTo`. Para habilitar o ogre2 (mais rápido e bonito):

  ```bash
  sudo usermod -aG render $USER
  ```

  depois `wsl --shutdown` no Windows e trocar `ogre` por `ogre2` no
  `estudio.sdf`.

- Por software as câmeras publicam a ~0,6 Hz. É lento para vídeo, mas
  irrelevante para tirar fotos paradas.
