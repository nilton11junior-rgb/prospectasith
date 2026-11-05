# Entrega local — Central SITH.IA

Data: 05/11/2026. Branch: `codex/central-sith-prospeccao`. Sem publicação externa.

## Abrir

- Central: <http://127.0.0.1:8090/>. Usa a senha já existente no Prospecta.
- Iniciador: `Central SITH.IA.cmd`, na raiz deste projeto.
- Atalho também disponível em `%USERPROFILE%\OneDrive\agenda sith\Abrir Central SITH.IA.cmd`.
- Scraper independente: <http://127.0.0.1:8081/>.

O iniciador da central abre com envios e respostas automáticas pausados. Mantém as campanhas salvas. O operador pode retomar suas rotinas com `Central SITH.IA.cmd --automacoes`.

## Entregue

- Marca SITH.IA, logo original, título/favicon e tema preto/roxo no CRM e no scraper.
- Tela nativa **Prospecção → Scraper com mapa**: busca por nicho/local, raio, idioma, quantidade aproximada e e-mails.
- Mapa, filtros, paginação, exportação para Excel e importação para a base única do CRM.
- Importação inclui empresas sem coordenadas. Reimportação conserva status, notas, histórico, opt-out e conversas.
- Funil, busca avançada, campanhas, agente IA, WhatsApp, agenda, lixeira e demais áreas existentes preservados.
- Motores separados em 8080/8081; painel autenticado em 8090. Serviços locais, sem alteração de senha.
- Backup anterior à inicialização em `painel/dados/backups/central-sith-2026-11-05T07-44-48-848Z/`, fora do Git.

## Evidências

- `python -X utf8 scripts/verificar.py`: **87 testes aprovados** (13 scripts + 74 painel), sintaxe Python/JS válida e dados/segredos fora do Git.
- Único aviso de tamanho: `scripts/scrape.py`, 451 linhas, anterior a esta entrega.
- Navegador com dados sintéticos isolados: 12 áreas anteriores, importação repetida, conservação do histórico, filtro, exportação com BOM, ficha do lead e funil.
- Desktop e celular: sem vazamento horizontal da página; tabela rola dentro do seu contêiner.
- Recuperação após motor indisponível, navegação durante resposta atrasada e conteúdo malicioso sem execução de script.
- Central real: título/assets SITH.IA, senha configurada preservada, novas APIs retornam 401 sem autenticação. Leads e configuração iguais aos valores anteriores à abertura.
- Evidências privadas de teste em `%USERPROFILE%\.codex\visualizations\2026\11\05\01a1a9c7-737e-70b1-a5d1-b95efa94379d\central-qa\`.

## Motor e serviços externos

O teste real encontrou um encerramento prematuro no fork: antes do primeiro resultado, o monitor calculava inatividade usando uma data vazia. Corrigido para contar desde o início da execução. Teste de regressão falhou antes da correção (500 ms em vez de 1 s) e passou depois.

O executável corrigido foi compilado e iniciado em 8081. No reteste isolado, o Google Maps excedeu o tempo de carregamento; não houve captura real confirmada. A integração do CRM foi validada com empresas sintéticas, sem acrescentar leads de teste à base real.

O iniciador tentou abrir o Docker Desktop, mas o daemon não ficou pronto em cinco minutos. A central permanece disponível; o WhatsApp interno fica pendente do Docker/WAHA e do pareamento.

Comandos de testes do motor aprovados: `go test ./runner/webrunner/...`, `go test ./web/... -skip '^TestIndexScrapeFormReplacesPaginatedJobs$'` e, dentro de `third_party/scrapemate`, `go test ./internal/inactivitytest -count=1`. A exclusão explícita do teste legado está explicada abaixo.

O pacote `web` contém um teste anterior do formulário HTMX antigo (`TestIndexScrapeFormReplacesPaginatedJobs`). Ele já exige um elemento ausente no HTML original deste fork MazyOS. Essa falha preexistente foi registrada; o teste não foi alterado para esconder a divergência. A suíte completa da dependência vendorizada também contém `syscall.Kill`, indisponível no Windows; a regressão nova fica em um pacote isolado compatível.

WhatsApp depende do Docker/WAHA e do pareamento da conta. IA depende do provedor configurado. Esta entrega não comprova envio real, pareamento ou resposta real de IA. Nenhuma mensagem foi enviada.

## Skills

41 skills importadas para `%USERPROFILE%\.codex\skills`, sem sobrescrever skills existentes. Nomes, origens, exclusões, ausências e adaptações no relatório `%USERPROFILE%\.codex\skill-import-work\RELATORIO.md`. Todas passaram na validação de frontmatter. Se o catálogo não atualizar numa nova conversa, reinicie o Codex.

## Revisão sequencial

Revisados: barreiras de autenticação/origem, destino loopback, bloqueio de redirecionamentos/proxy, limites de resposta/CSV, deduplicação, conservação do estado comercial e ciclo de vida do mapa. A importação não coloca jobs na fila antiga nem associa sua exclusão ao motor original. Restaurar uma busca da lixeira é obrigatório antes de reimportar.

Não houve publicação, alteração de credenciais nem ativação de envio automático. Os arquivos de dados, logs e executáveis locais ficam fora dos commits.
