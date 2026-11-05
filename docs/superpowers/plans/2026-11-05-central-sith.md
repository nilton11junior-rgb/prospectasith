# Plano de implementação — Central SITH.IA

> Execução sequencial nesta conversa, conforme autorização explícita do usuário. Plano durável substitui update_plan, indisponível nesta sessão.

**Objetivo:** integrar mapa/buscas do SITH.IA Scraper ao Prospecta e preservar a operação comercial existente.

**Arquitetura:** serviço Python de integração com destino loopback; rotas autenticadas do CRM; tela nativa Leaflet; importação pelo normalizador atual. Tema SITH.IA compartilhado visualmente entre os dois projetos.

**Stack:** Python 3.12 padrão, JavaScript clássico, CSS, Leaflet 1.9.4 local, motor Go existente.

**Spec:** `docs/superpowers/specs/2026-11-05-central-sith-design.md`.

## Restrições globais

- Não substituir/apagar dados, senha, credenciais ou ajustes de campanhas.
- Não enviar mensagens, ligar disparo automático ou publicar.
- Portas só em loopback. Rotas protegidas pela autenticação existente.
- Arquivos novos por responsabilidade, até aproximadamente 400 linhas.
- Usar a logo original, tema preto/roxo e testar com dados sintéticos isolados.

## Foco da revisão

- Reimportação não perde status, observações, histórico e opt-out.
- Resultados sem coordenadas ainda entram no CRM.
- Jobs inexistentes, UUIDs/caminhos maliciosos e redirecionamento do motor não geram acesso arbitrário.
- Navegação/timer assíncronos não recriam mapa em uma tela já fechada.
- Indisponibilidade de motor/WhatsApp preserva navegação e mostra estado recuperável.

## Etapas

- [x] Inventariar e importar skills sem sobrescrever; relatório próprio em ~/.codex/skill-import-work.
- [x] Ler arquitetura, normalização, rotas, testes, startup e autorização de mensagens.
- [x] Escrever testes HTTP e de importação usando um motor fake local e estado temporário; rodar e observar falhas por ausência das rotas.
- [x] Implementar `painel/scraper_motor.py` (cliente e criação de jobs), `painel/scraper_importacao.py` (CSV/deduplicação), `painel/rotas_scraper.py` (API autenticada) e conectá-los ao handler. Rodar testes novos e existentes.
- [x] Criar a tela `painel/static/js/scraper.js` e apresentação/mapa em arquivo separado, com importação, filtros, estados vazios/erro, atualização e entrada no menu.
- [x] Aplicar logo/favicon e tema `painel/static/sithia.css`, preservar cores de status e revisar telas existentes.
- [x] Adaptar `scripts/iniciar.py` e atalho da central para subir o motor disponível e a interface, com modo de saída automática suspensa por padrão de abertura desta tarefa.
- [x] Escurecer o scraper independente, compilar e trocar somente o processo identificado, sem apagar sua base.
- [x] Verificar funcionalidade desktop/celular com fixtures, persistência/reimportação, sintaxe, suíte completa, diff e segredos. Registrar resultados e limitações reais.
- [x] Atualizar produto, arquitetura, design, onboarding e relatório final. Deixar a central pronta para abrir localmente.

## Resultado e pendências externas

Central real em 8090, dados/configuração/senha preservados, backup local e automações pausadas. Verificações finais em docs/entrega-central-sith.md. O reteste público do Google Maps excedeu o tempo de carregamento. WhatsApp ainda reporta serviço desligado; nenhum envio foi efetuado. Esses serviços externos não foram declarados validados.
