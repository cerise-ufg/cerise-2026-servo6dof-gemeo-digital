#!/usr/bin/env bash
exec > ~/braco/finalize.log 2>&1
echo "=== aguardando braco_gen (laranja) $(date) ==="
sudo docker wait braco_gen
echo "=== terminou $(date); chown ==="
sudo chown -R energiainteligente:energiainteligente ~/braco/dataset ~/braco/gen_logs 2>/dev/null
echo "poses: $(find ~/braco/dataset -maxdepth 1 -name "*.json" | wc -l)"
echo "=== FINALIZADO $(date) ==="
