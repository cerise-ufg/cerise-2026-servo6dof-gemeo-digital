#!/usr/bin/env bash
# Derruba o servidor do Gemeo Digital (container cerise26_gemeo).
N="${NOME:-cerise26_gemeo}"; sudo docker rm -f "$N" && echo "$N removido"
