# Onboarding

## Pré-requisitos (Windows 11)

- `uv` com Python 3.12 (`uv python install 3.12`). O `Prospeccao.cmd` usa `%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe` e cai em `python` se não achar.
- Motor de busca: `engine/google-maps-scraper.exe` (release oficial gosom v1.18.1, sha256 `c124fab3…f7848f`). Fica fora do git; baixe de https://github.com/gosom/google-maps-scraper/releases se faltar. No primeiro job ele baixa Playwright + Chromium (~150 MB).
- Docker Desktop (para o WhatsApp/WAHA). Na primeira abertura aceite os termos.
- Claude Code instalado e logado (`claude`) para o agente IA, ou uma chave da Anthropic na tela Agente IA.
- Node.js (opcional): só para `scripts/verificar.py` checar a sintaxe do JavaScript.

## Primeiro uso

1. Dois cliques em `Prospeccao.cmd`. Ele liga o motor, abre o Docker Desktop, sobe o WAHA e o painel e abre http://localhost:8090.
2. Crie a senha do painel (só no próprio computador).
3. **WhatsApp interno → Conectar** e escaneie o QR (WhatsApp → Dispositivos conectados). O QR vence em ~1 min.
4. **Nova busca**: nicho + cidade. A busca roda na fila; os leads aparecem em **Leads**.
5. **Agente IA**: preencha base de conhecimento e instruções. **Campanhas**: revise segmentos e mensagens. O disparo automático vem desligado.

## Dados

Sem banco. Tudo em `painel/dados/` (JSON, segredos e logs), fora do git. Backup = copiar essa pasta. Para recomeçar do zero, pare o painel e mova a pasta para outro lugar.

## Verificar

```bash
python -X utf8 scripts/verificar.py
```

## Agentes

- Claude Code: abra a pasta do projeto; `CLAUDE.md` importa `AGENTS.md`; MCP `prospecta` em `.mcp.json` (aprove quando o Claude pedir).
- Codex: lê `AGENTS.md`; MCP em `.codex/config.toml` (vale quando o projeto é confiável no Codex).
- Os dois precisam do painel ligado para o MCP funcionar.

## Problemas conhecidos

- Máquina ocupada deixa `docker info` e o Claude CLI lentos (até ~1–2 min). O iniciador espera o Docker pela lista de pipes e tenta o `compose up` de novo.
- Motor `.exe` às vezes fica em "working" depois de terminar: o painel aceita o resultado estável.
- No Git Bash, `curl` com acento manda Latin-1 e quebra o JSON; use a tela ou escape (`é`).
