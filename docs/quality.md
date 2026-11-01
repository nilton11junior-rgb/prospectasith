# Qualidade

## Comandos e o que provam

| Comando | Prova | Não prova |
|---|---|---|
| `python -X utf8 scripts/verificar.py` | tudo abaixo de uma vez; sai com código 1 se algo falhar | comportamento com WhatsApp/IA reais |
| sintaxe Python (dentro do verificar) | todos os `.py` compilam (em memória, sem `.pyc`) | erro de lógica |
| `python -X utf8 -m unittest discover -s painel -p "test_*.py"` | segmentos, variáveis e rodízio, follow-up, agenda sem conflito, eventos do WhatsApp (só CRM, optout, duplicada), senha, login obrigatório, token, webhook, envio só para CRM, `/static/` sem fuga de pasta e as regressões de segurança (Host, Origin/CSRF, corpo grande, bloqueio de login, opt-out por número, DDI 55, SSRF, limites da IA) | envio real pelo WAHA, chamada real à IA, busca real no Google |
| `python -X utf8 -m unittest discover -s scripts -p "test_*.py"` | CLI do kit (grade, dedupe, e-mails, redes) | motor real |
| sintaxe JS (dentro do verificar, precisa de Node) | `painel/static/js/*.js` sem erro de sintaxe | renderização das telas |
| tamanho de arquivo (aviso) | nenhum arquivo do painel passa de 400 linhas | — |
| segredos fora do git | `.env` e `painel/dados/` não estão versionados | segredo colado dentro de código |

Lint e checagem de tipos: indisponíveis (sem ruff/mypy no projeto, por ser só biblioteca padrão). Para checar nomes indefinidos sem instalar nada no projeto: `uvx ruff@0.14.1 check --select F821,F811 painel`.

## Testes

- Ficam junto do código, só biblioteca padrão: `painel/test_painel.py` (núcleo), `test_seguranca.py`, `test_lixeira.py`, `test_estrategia.py` (apoio em `testes_comum.py`) e `scripts/test_scrape.py`.
- Rodam com `PROSPECTA_DADOS` numa pasta temporária: nunca tocam em `painel/dados/`, WhatsApp, Google ou IA.
- Bug corrigido ganha teste que reproduz o problema. Funções que falam com serviços externos (WAHA, Claude, motor) são testadas pelo comportamento ao redor, sem simular sucesso da integração.
- Telas: depois de mexer em `painel/static/js`, abra o painel e confira as telas afetadas (o verificar só garante a sintaxe).

## Revisão

- Mudança não trivial: revisão independente (subagente só-leitura), escopo pelo risco: comportamento, segurança/dados, integrações, UX.
- O revisor devolve severidade, local, cenário concreto e evidência; o coordenador confere antes de corrigir.

## Revisão de segurança (reutilizável)

- Fonte: Vibe Coding Toolkit, `docs/prompts/13-security-review.md`, revisão `790a895` (https://github.com/soumatheusgomes/vibe-coding-toolkit). Use a seção "Prompt" desse arquivo, na mesma revisão.
- Como invocar: "Leia `docs/prompts/13-security-review.md` do Vibe Coding Toolkit (revisão 790a895) e execute a seção Prompt neste projeto, modo repositório (ou diff `A..B`), relatório privado em `..\privado\seguranca-AAAA-MM-DD.md`."
- Só leitura por padrão; não sonda serviços no ar; relatório fica FORA do repositório (`C:\Users\nilto\projetos\gmaps-crm\privado\`), sem valores de segredo.
- Superfícies deste projeto: rotas do painel e login, webhook do WAHA, `/static/`, comando do Claude CLI (prompt injection vindo do lead), busca em sites de terceiros (SSRF), XSS com dados de leads, portas do Docker, ferramentas do MCP.
- Última revisão: ver `docs/setup.md`.

## Avaliação do harness (reutilizável)

- Fontes (revisão `790a895`): `docs/07-harness-evaluation.md`, `docs/prompts/14-harness-evaluation.md`, `docs/prompts/15-harness-improvement.md`, fixture `templates/harness-evaluation/` e avaliador `scripts/validate-harness.mjs` (precisa de Node).
- Quando rodar: depois de mudar `AGENTS.md`/`CLAUDE.md`, MCP, skills ou forma de delegar.
- Como: copie a fixture para uma pasta temporária por caso (fora do projeto e do toolkit), confirme que o avaliador falha 2 de 7 no estado inicial, dê a tarefa a um contexto limpo sem a solução, depois rode o avaliador e confira o diff você mesmo. Casos mínimos: correção de limite, handoff desatualizado, revisão só-leitura.
- Modo de melhoria: adaptação nativa inspirada no Harness2 (não executa o framework Harness2). Uma comparação de candidato por falha observada; o CLI oficial do Harness2 não está selecionado.
- Registre o resultado de cada caso em `docs/setup.md`.

## Dependências

Nenhuma dependência Python. Externos: motor gosom v1.18.1 (binário fixo), imagem `devlikeapro/waha:latest` (atualizar de propósito: `docker compose -f whatsapp/docker-compose.yml pull`), Claude Code CLI.
