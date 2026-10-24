# Prospecta

CRM local de prospecção para quem vende serviços digitais a empresas locais. Encontra empresas no Google Maps, separa por situação (sem site, só Instagram, site sem Instagram, site e Instagram, nota baixa), aborda pelo WhatsApp com mensagens estratégicas por segmento, faz follow-up e deixa um agente IA atender e marcar chamadas na agenda. Tudo roda no seu computador.

## Rodar

```bash
Prospeccao.cmd
```

Dois cliques no `Prospeccao.cmd` ligam o motor de busca (porta 8080), o WhatsApp/WAHA no Docker Desktop (porta 3000) e o painel em http://localhost:8090. Na primeira vez, crie a senha do painel e pareie o WhatsApp em **WhatsApp interno** (QR Code).

Verificar o projeto:

```bash
python -X utf8 scripts/verificar.py
```

## Documentos

| Documento | Para quê |
|---|---|
| [PRODUCT.md](PRODUCT.md) | problema, fluxos, escopo, decisões e critérios de aceite |
| [docs/onboarding.md](docs/onboarding.md) | preparar a máquina e o primeiro uso |
| [docs/architecture.md](docs/architecture.md) | mapa do código, fronteiras e dados |
| [docs/design.md](docs/design.md) | interface do painel |
| [docs/quality.md](docs/quality.md) | checagens, testes, revisão de segurança e do harness |
| [docs/setup.md](docs/setup.md) | registro do setup do Vibe Coding Toolkit e pendências |
| [AGENTS.md](AGENTS.md) / [CLAUDE.md](CLAUDE.md) | instruções para agentes (Codex, Claude Code e outros) |
| [KIT-README.md](KIT-README.md) | README original do Google Maps Scraper Kit (motor e CLI) |

## Próxima entrega

Medir a taxa de resposta por segmento e por variação de mensagem no painel.

Créditos do motor de busca e licença: [CREDITS.md](CREDITS.md), [LICENSE](LICENSE).
