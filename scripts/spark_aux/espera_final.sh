export PADRAO="FINAL_OK|${2:-real_vs_comandado}"
timeout ${1:-560} bash -c 'until grep -q -E "$PADRAO" ~/cerise2026/gemeo/tmp/final.log; do sleep 15; done'
date
grep -E '^\+|n_poses_verificadas|n_problemas|duplicados|tempo_s|FINAL|Traceback|Error|-> a12' ~/cerise2026/gemeo/tmp/final.log | tail -30 | cut -c1-220
