# Arquitetura

## Stack real

- Python 3.12, só biblioteca padrão (sem `requirements.txt`). Executado pelo Python do `uv`.
- Interface: `painel/index.html` + `painel/static/app.css` + scripts clássicos em `painel/static/js/` (sem framework, sem build).
- Motor de busca: `engine/google-maps-scraper.exe` (gosom/google-maps-scraper v1.18.1, nativo Windows), API em 127.0.0.1:8080.
- WhatsApp: WAHA (`devlikeapro/waha`, motor GOWS) no Docker Desktop, 127.0.0.1:3000, via `whatsapp/docker-compose.yml`.
- IA: Claude Code CLI da assinatura (`claude -p`, sem ferramentas, em pasta temporária fora do projeto) ou API da Anthropic se houver chave.
- Dados: JSON em `painel/dados/` (fora do git). Sem banco de dados.

## Mapa do código

| Arquivo | Responsabilidade |
|---|---|
| `scripts/iniciar.py` (+ `Prospeccao.cmd`) | liga motor, Docker/WAHA e painel; não duplica serviço já no ar |
| `painel/server.py` | carga dos dados, handler HTTP (buscas, leads, config, estáticos) e `main` |
| `painel/seguranca_http.py` | Hosts/origens permitidos, limite de corpo, bloqueio de login, cabeçalhos de segurança |
| `painel/rotas_auth.py` | criar senha (só local), entrar, sair |
| `painel/rotas_atendimento.py` | rotas de WhatsApp, conversas, agente, campanhas e agenda |
| `painel/estado.py` | config padrão, estado em memória, gravação atômica em disco, segredos, senha, `registrar` |
| `painel/normaliza.py` | municípios IBGE, geocodificação OSM, telefone/WhatsApp BR, lead a partir da linha do motor, mescla na base |
| `painel/buscas.py` | fila de buscas (uma por vez), jobs no motor, enriquecimento visitando o site da empresa |
| `painel/whatsapp.py` | cliente WAHA, envio com "digitando…", conversas, eventos do webhook (só leads do CRM) |
| `painel/agente.py` | chamada à IA, prompt com base/estratégia/agenda, ações (agendar, humano, encerrar), primeira mensagem |
| `painel/campanhas.py` + `painel/roteiros.py` | segmentos por situação, variáveis, rodízio; textos padrão e prompt de sistema |
| `painel/disparo.py` | disparo automático e follow-up com limites; respondedor da IA com espera |
| `painel/agenda.py` | horários livres e reservas sem conflito (UTC-3) |
| `painel/visoes.py` | resumos devolvidos à tela |
| `painel/lixeira.py` + `painel/rotas_lixeira.py` | lixeira de buscas: mandar, restaurar, excluir de vez, esvaziar e limpeza em 30 dias; rotas `/api/lixeira*` e `/api/buscas/<id>/lixeira|restaurar` |
| `painel/mcp_server.py` | servidor MCP stdio que usa a API do painel com token local |
| `scripts/scrape.py`, `scripts/scrape.sh` | CLI original do kit (usada pelo painel para HTTP, grade e extração de e-mail/redes) |

## Fronteiras e fluxo

```
navegador ──cookie──▶ painel :8090 ──▶ motor :8080 ──▶ Google Maps
MCP (Claude/Codex) ──X-Prospecta-Token──▶ painel
painel ──X-Api-Key──▶ WAHA :3000 ──▶ WhatsApp
WAHA ──webhook X-WA-Token──▶ host.docker.internal:8090/api/wa/evento
painel ──subprocess──▶ claude -p   (ou HTTPS api.anthropic.com com chave)
painel ──HTTP──▶ sites das empresas (enriquecimento) e nominatim.openstreetmap.org
```

- Toda rota `/api/*` exige login (cookie `HttpOnly`, `SameSite=Strict`) ou o token local, exceto `/api/auth/*` e o webhook (token próprio). `/static/` é público e só serve `.css/.js/.svg/.png` de dentro de `painel/static/`.
- Criar a senha só é aceito de 127.0.0.1/::1 com Host local (não pelo nome do Tailscale).
- Host fora da lista (localhost, 127.0.0.1, ::1, `*.ts.net`; `host.docker.internal` só no webhook) recebe 403 (DNS rebinding). Pedido do navegador que muda algo precisa de `Origin` igual ao Host e JSON (CSRF de outra porta do localhost). Corpo acima de 1 MB: 413. CSP `script-src 'self'`.
- Enriquecimento só visita sites em IP público, portas 80/443, conferindo cada redirecionamento (SSRF).
- Opt-out vale pelo número em qualquer registro; a IA não recebe as anotações privadas, reserva no máximo 1 horário futuro por lead e responde no máximo 30 vezes por dia por conversa. O MCP não liga o disparo automático.
- Mensagem só sai para número que bate com um lead (DDD + 8 dígitos, ignorando 55 e o 9º dígito).

## Dados (`painel/dados/`)

`leads.json` (base, chave `place_id`), `buscas/<id>.json`, `config.json` (modelos, agente, agenda, disparo, campanhas, follow-up), `conversas.json`, `agenda.json`, `envios.json` (contador diário), `auth.json` (hash da senha), `sessoes.json`, segredos `api_token`, `wa_token`, `waha_key`, `anthropic_key` (opcional), `logs/`. Escrita atômica (`.tmp` + `os.replace`). A pasta pode ser trocada por `PROSPECTA_DADOS` (testes).

## Decisões

- Estado compartilhado em `estado.py` (objetos mutáveis importados pelos módulos); `server.py` não é importado pelos módulos, para não duplicar o estado quando roda como `__main__`.
- Motor `.exe` às vezes fica preso em "working": `buscas.rodar_job` aceita o CSV estável por 3 min e dá folga de `max_time + 900 s`.
- Pasta de trabalho da IA fora do projeto: dentro dele o Claude Code encontraria `.mcp.json`/`.claude` e travaria pedindo aprovação.

## Manutenção

- Mudou rota, dado ou comando: atualize este arquivo e `docs/onboarding.md`.
- Mantenha arquivos abaixo de ~400 linhas (`scripts/verificar.py` avisa). `scripts/scrape.py` (451) é do kit original e ficou como está.
