#!/usr/bin/env bash
# Roda uma etapa da coleta (cwd: code/backend), registra duração e pico de memória e publica o progresso.
LIVE=../../results/backend/tests/fixtures/live
mkdir -p "$LIVE"
start=$(date +%s)
echo "### $* (início $(date -u +%H:%M:%SZ))" | tee -a "$LIVE/COLLECT.log"
if [ -x /usr/bin/time ]; then
  /usr/bin/time -f "pico de memória: %M KB" python -m app.cli collect --only "$@" 2>&1 | tee -a "$LIVE/COLLECT.log"
else
  python -m app.cli collect --only "$@" 2>&1 | tee -a "$LIVE/COLLECT.log"
fi
rc=${PIPESTATUS[0]}
echo "### $* duração: $(( $(date +%s) - start ))s (saída $rc)" | tee -a "$LIVE/COLLECT.log"
# Publicar o progresso permite acompanhar de fora; pushes com GITHUB_TOKEN não disparam novo workflow.
(cd ../../results && git add -f backend/tests/fixtures/live && \
  git -c user.name=probe-bot -c user.email=probe-bot@users.noreply.github.com commit -qm "Progresso: $*" && \
  git push -q origin HEAD:tmp/verify-live-sources) || echo "(progresso não publicado)"
exit "$rc"
