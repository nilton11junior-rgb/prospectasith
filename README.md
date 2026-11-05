# Central de Prospecção SITH.IA

CRM local de prospecção para quem vende serviços digitais a empresas locais. Encontra empresas no Google Maps, separa por situação (sem site, só Instagram, site sem Instagram, site e Instagram, nota baixa), aborda pelo WhatsApp com mensagens estratégicas por segmento, faz follow-up e deixa um agente IA atender e marcar chamadas na agenda. Tudo roda no seu computador.

A central reúne o CRM Prospecta e o SITH.IA Scraper, com a logo original, tema preto/roxo e uma base única de leads. A aplicação e os arquivos ficam locais; Google Maps, WhatsApp e IA dependem dos serviços correspondentes.

## Rodar

```powershell
& '.\Central SITH.IA.cmd'
```

Dois cliques em `Central SITH.IA.cmd` ligam o painel em **http://127.0.0.1:8090**, o motor original (8080), o scraper adicional (8081) e preparam o WhatsApp/WAHA (3000) em segundo plano. A senha e os dados do Prospecta são os mesmos. Na primeira instalação, crie sua senha e pareie o WhatsApp em **WhatsApp interno**.

Essa abertura pausa as rotinas de envio automático sem alterar as campanhas salvas. Para retomar as rotinas configuradas, por escolha do operador: `& '.\Central SITH.IA.cmd' --automacoes`. O atalho legado `Prospeccao.cmd` mantém o comportamento anterior.

## Do mapa ao funil

1. Abra **Prospecção → Scraper com mapa** e informe nicho, bairro/cidade, quantidade e raio.
2. Acompanhe empresas e filtros no mapa. A quantidade é aproximada; buscar e-mails leva mais tempo.
3. Quando concluir, clique em **Importar para o CRM**. Reimportar atualiza contatos sem duplicar leads, status, notas ou histórico.
4. Continue em **Leads**, **Funil de vendas**, **WhatsApp interno** e **Agenda**. A **Busca avançada** e a lixeira anteriores continuam disponíveis.

Empresas sem coordenadas também são importadas. Uma busca na lixeira precisa ser restaurada antes de reimportar.

Em **Buscas**, use **Excluir busca e leads**, **Excluir selecionadas** ou **Excluir todas**. A confirmação mostra quantos leads, conversas locais e reservas serão removidos. Leads compartilhados também saem das outras buscas; isso inclui os que já foram trabalhados. A operação não passa pela lixeira e cria backup local antes de salvar. Buscas em andamento precisam ser canceladas primeiro. Jobs excluídos ficam bloqueados contra reimportação; se o motor estiver offline, a limpeza dele é retomada em segundo plano.

O iniciador localiza `../../mazyos-scraper/sithia-scraper.exe` em relação à pasta deste projeto. Para outra localização, configure `SITH_SCRAPER_EXE` e, opcionalmente, `SITH_SCRAPER_DATA`. A API usa `SITH_SCRAPER_URL` (padrão `http://127.0.0.1:8081`), sempre uma porta loopback.

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
| [docs/exclusao-buscas.md](docs/exclusao-buscas.md) | exclusão individual/em lote e remoção dos leads vinculados |
| [docs/estrategia-vendas.md](docs/estrategia-vendas.md) | método de vendas que gera as mensagens e o comportamento da IA |
| [docs/quality.md](docs/quality.md) | checagens, testes, revisão de segurança e do harness |
| [docs/setup.md](docs/setup.md) | registro do setup do Vibe Coding Toolkit e pendências |
| [AGENTS.md](AGENTS.md) / [CLAUDE.md](CLAUDE.md) | instruções para agentes (Codex, Claude Code e outros) |
| [KIT-README.md](KIT-README.md) | README original do Google Maps Scraper Kit (motor e CLI) |

## Próxima entrega

Medir a taxa de resposta por segmento e por variação de mensagem no painel.

Créditos do motor de busca e licença: [CREDITS.md](CREDITS.md), [LICENSE](LICENSE).
