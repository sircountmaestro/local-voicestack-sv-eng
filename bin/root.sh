# shellcheck shell=bash
# Sourcas från bin/*. BASH_SOURCE[0] är den här filen.
if [[ -n "${TTSPRO_ROOT:-}" && -d "${TTSPRO_ROOT}/apps" ]]; then
  ROOT="$TTSPRO_ROOT"
else
  ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
fi
export TTSPRO_ROOT="$ROOT"
export STT_WHISPER_COMPOSE="$ROOT/apps/whisper-stt-sv/compose.yml"
