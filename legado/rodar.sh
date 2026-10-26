#!/usr/bin/env bash
#
# COMANDO UNICO do dataset: roda, vê de onde parou, continua, e vai salvando.
#
# Faz tudo sozinho:
#   1. gera o plano de poses se ainda nao existir
#   2. olha o disco e descobre quantas poses faltam
#   3. gera em LOTES, salvando cada pose na hora
#   4. se um lote travar (Gazebo cai numa maratona longa), reinicia e continua
#   5. para quando atingir a meta (10.000 imagens = 5.000 poses)
#
# Uso (dentro do WSL):
#     bash /mnt/e/cerise/braco/rodar.sh
#
# Ou direto do PowerShell do Windows:
#     wsl -d Ubuntu-22.04 bash /mnt/e/cerise/braco/rodar.sh
#
# Opcional:  bash rodar.sh <workers> <poses_por_lote>   (padrao: 2 250)
#
# Parar: Ctrl+C. O que ja foi salvo fica; rodar de novo continua de onde parou.
#
WORKERS="${1:-2}"
LOTE="${2:-250}"
WS=/mnt/e/cerise/braco
PLANO="$WS/plano_poses.json"
SAIDA="${SAIDA:-$WS/dataset}"

source /opt/ros/humble/setup.bash >/dev/null 2>&1
source "$WS/install/setup.bash" >/dev/null 2>&1
mkdir -p "$SAIDA"

# 1. gera o plano se faltar
if [ ! -f "$PLANO" ]; then
    echo ">> plano nao existe, gerando..."
    python3 "$WS/gerar_plano.py" || exit 1
fi

# conta quantas poses ainda faltam (lendo o plano vs o disco)
faltam() {
    python3 - "$PLANO" "$SAIDA" <<'PY'
import json, os, sys
plano, saida = sys.argv[1], sys.argv[2]
ids = [int(p["id"]) for p in json.load(open(plano))["poses"]]
print(sum(1 for i in ids
          if not os.path.exists(os.path.join(saida, "%06d.json" % i))))
PY
}

# para tudo ao sair (Ctrl+C incluso)
trap 'echo; echo ">> parado. progresso salvo — rode de novo para continuar."; pkill -f "ign gazebo" 2>/dev/null; exit 0' INT TERM

echo "=================================================="
echo " DATASET servo6dof — comando unico (auto-continua)"
echo "   meta .......... 5.000 poses / 10.000 imagens"
echo "   workers ....... $WORKERS   |   lote ... $LOTE poses"
echo "   saida ......... $SAIDA"
echo "=================================================="

parados=0
while true; do
    N=$(faltam)
    if [ -z "$N" ]; then echo ">> erro lendo o plano"; exit 1; fi
    if [ "$N" -eq 0 ]; then
        echo
        echo ">> COMPLETO! meta de 10.000 imagens atingida."
        python3 "$WS/status_dataset.py"
        break
    fi

    echo
    echo ">> faltam $N poses — rodando mais um lote (ate $LOTE)..."
    antes=$N

    # um lote = uma rodada limpa de Gazebo + captura resumavel
    bash "$WS/continuar.sh" "$LOTE" "$WORKERS"

    # detecta lote que nao andou (Gazebo nao subiu, etc.) e evita loop infinito
    depois=$(faltam)
    if [ "$depois" -ge "$antes" ]; then
        parados=$((parados + 1))
        echo ">> AVISO: o lote nao avancou ($parados seguidos)."
        if [ "$parados" -ge 3 ]; then
            echo ">> abortando apos 3 lotes sem progresso. Veja /tmp/continuar_w*.log"
            exit 1
        fi
        sleep 5
    else
        parados=0
    fi
done
