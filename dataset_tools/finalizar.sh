#!/usr/bin/env bash
# Espera a geracao do dataset terminar, corrige dono dos arquivos e RELIGA a
# producao automaticamente. Rodar destacado: setsid bash ~/braco/finalizar.sh &
exec > ~/braco/finalize.log 2>&1
echo "=== finalizador iniciado $(date) ; aguardando braco_gen terminar ==="
EXIT=$(sudo docker wait braco_gen 2>/dev/null)
echo "=== braco_gen saiu (codigo $EXIT) em $(date) ==="
POSES=$(sudo bash -c "ls /home/energiainteligente/braco/dataset/*.json 2>/dev/null | wc -l")
echo "poses no disco: $POSES"
echo "=== chown do dataset para o usuario ==="
sudo chown -R energiainteligente:energiainteligente /home/energiainteligente/braco/dataset /home/energiainteligente/braco/gen_logs 2>/dev/null
echo "=== religando producao ==="
bash ~/braco/dataset_run_restore.sh
echo "=== FINALIZADO $(date) ==="
