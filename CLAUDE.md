@AGENTS.md

## Só para Claude Code

- Para usar o motor do Google Maps direto (sem o painel), carregue a skill `.claude/skills/google-maps-scraper/SKILL.md`: ela tem o fluxo exato da API (`POST /api/v1/jobs` exige `max_time` em segundos, `lat`/`lon` como string e `keywords`). Comandos: `/scrape`, `/scrape-batch`, `/scrape-setup`, `/scrape-jobs`.
- Neste projeto o motor roda nativo (`engine/google-maps-scraper.exe`), não pelo `docker compose` da raiz; `scripts/iniciar.py` liga tudo.
- Busca grande (depth alto, muitas palavras, grade): avise uma vez sobre o risco de bloqueio temporário do IP pelo Google e siga.
- Acompanhe jobs longos em segundo plano (`run_in_background`); `sleep` em primeiro plano é bloqueado.
- Atribuição do motor: `gosom/google-maps-scraper` (MIT). Mantenha `CREDITS.md` e `LICENSE`.
