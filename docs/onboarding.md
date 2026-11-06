# Onboarding

## Instalar a partir do GitHub (Windows x64)

1. Aceite o convite do repositório privado e clone o projeto na pasta de sua preferência.
2. Na página **Releases** do mesmo repositório, baixe `prospectasith-motores-windows-x64.zip` e extraia na raiz do clone. A pasta `engine/` deverá conter `google-maps-scraper.exe` e `sithia-scraper.exe`.
3. Instale o Python 3.12 e abra `Prospecta SITH.IA.cmd`. No primeiro acesso, crie sua senha. Se quiser usar o WhatsApp, instale também o Docker Desktop e pareie sua sessão.

Cada instalação cria sua própria base local e pode rodar de forma independente. A base, os logins, as configurações e as sessões de WhatsApp não são compartilhados entre computadores.

## Pré-requisitos (Windows 11)

- `uv` com Python 3.12 (`uv python install 3.12`). O `Prospeccao.cmd` usa `%APPDATA%\uv\python\cpython-3.12-windows-x86_64-none\python.exe` e cai em `python` se não achar.
- Motor de busca: `engine/google-maps-scraper.exe` (release oficial gosom v1.18.1, sha256 `c124fab3…f7848f`). Fica fora do git; baixe de https://github.com/gosom/google-maps-scraper/releases se faltar. No primeiro job ele baixa Playwright + Chromium (~150 MB).
- SITH.IA Scraper em `engine/sithia-scraper.exe` ou, para instalações anteriores, em `../../mazyos-scraper/sithia-scraper.exe`. A variável `SITH_SCRAPER_EXE` permite indicar outro caminho. Sua pasta `webdata` é preservada.
- Docker Desktop (para o WhatsApp/WAHA). Na primeira abertura aceite os termos.
- Claude Code instalado e logado (`claude`) para o agente IA, ou uma chave da Anthropic na tela Agente IA.
- Node.js (opcional): só para `scripts/verificar.py` checar a sintaxe do JavaScript.

## Primeiro uso

1. Dois cliques em `Prospecta SITH.IA.cmd`. Ele liga os dois motores e o painel em http://127.0.0.1:8090, e prepara Docker/WAHA em segundo plano.
2. Crie a senha do painel (só no próprio computador).
3. **WhatsApp interno → Conectar** e escaneie o QR (WhatsApp → Dispositivos conectados). O QR vence em ~1 min.
4. **Scraper com mapa**: nicho + bairro/cidade. Quando concluir, clique em **Importar para o CRM**. **Busca avançada** conserva a fila/enriquecimento anteriores e importa automaticamente seus resultados.
5. **Agente IA**: preencha base de conhecimento e instruções. **Campanhas**: revise segmentos e mensagens. O disparo automático vem desligado.

A abertura da nova central não retoma envios automáticos, mesmo se houver campanhas salvas ativas; a interface mostra o modo pausado. Depois de revisar as campanhas e por decisão do operador, execute `& '.\Prospecta SITH.IA.cmd' --automacoes` para usar as rotinas configuradas. O atalho legado mantém a semântica anterior.

As buscas importadas do mapa usam o CSV completo: empresas sem coordenadas também aparecem em Leads. Reimportar atualiza informações de contato e mantém o estado comercial. Se a importação foi para a lixeira, restaure-a antes de reimportar.

## Dados

Sem banco. Tudo em `painel/dados/` (JSON, segredos e logs), fora do git. Backup = copiar essa pasta. Para recomeçar do zero, pare o painel e mova a pasta para outro lugar.

O scraper adicional usa SQLite/CSV em sua própria `webdata`; a central continua usando os JSON originais. Não copie dados pessoais para o Git. Não há sincronização automática destrutiva entre as duas bases.

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
