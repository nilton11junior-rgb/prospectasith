# Central de Prospecção SITH.IA

## Pedido e autorização

Nilton pediu reunir o SITH.IA Scraper ao Prospecta, preservar todos os ajustes do CRM, usar sua logo e um visual preto/roxo escuro. Autorizou executar e validar autonomamente enquanto dorme, sem aprovações intermediárias. Isso não autoriza enviar mensagens, ligar disparos, publicar na internet ou apagar dados.

## Resultado esperado

Uma central local em `http://127.0.0.1:8090`, com autenticação existente, tela de mapa e buscas do scraper, importação para a base única de leads e acesso ao funil, WhatsApp, campanhas, IA, agenda, mensagens e lixeira existentes.

## Decisões de implementação

- Manter Python 3.12 com biblioteca padrão e HTML/CSS/JS sem framework. Usar o código atual do Prospecta, em branch `codex/central-sith-prospeccao`.
- Criar uma tela nativa **Scraper com mapa** dentro do CRM. O servidor conversa com o motor SITH.IA já instalado em `127.0.0.1:8081`. Não há iframe, proxy aberto, credenciais no navegador ou envio de dados a uma nova plataforma.
- Manter a busca avançada atual. O iniciador mantém o motor original em 8080 e o motor SITH.IA em 8081, cada um com seu armazenamento. Nenhuma busca existente é migrada/apagada.
- Importar somente buscas concluídas. Ler o CSV completo do motor, incluindo empresas sem coordenadas; o mapa usa apenas coordenadas válidas. Preservar `place_id`, normalização brasileira e deduplicação do CRM.
- Importar de novo a mesma busca não duplica empresas nem histórico. Status, observações, opt-out e conversas continuam no Prospecta. Uma busca na lixeira precisa ser restaurada pelo fluxo existente.
- O importador não envia mensagens, não marca contatos e não muda automações. A execução durante o desenvolvimento usa modo sem automações de saída.

## Limites e segurança

Novas rotas `/api/scraper/*` usam o mesmo login/token, checagem de origem, JSON e limite de corpo do CRM. O usuário informa somente parâmetros de busca ou UUID de job, nunca URL, caminho local ou credencial. Requisições ao motor têm destino loopback fixo, timeout, limite de resposta e não seguem redirecionamentos. Campos de terceiros são escapados na interface. O CSP permite somente o domínio de tiles necessário ao mapa, mantendo scripts locais e autenticação intacta.

Testes usam uma pasta temporária dentro do scratchpad da tarefa. Nenhum teste importa dados reais ou envia mensagens.

## Direção visual

Preservar o menu e a densidade de trabalho do Prospecta. Base `#09070f`, superfície `#17131f`, borda `#332641`, texto `#f4efff`, destaque `#9b4dff` e contraste secundário `#bcaacf`. Logo original transparente em cabeçalho, login e aba. Roxo intenso em ações/seleção; verde permanece significativo para WhatsApp e sucesso. Fundo com luz estática discreta. Tipografia de sistema, foco visível, redução de movimento, formulários rotulados e responsividade para celular.

## Aceite

1. Testes existentes e novos passam, inclusive importação repetida, conflitos com lixeira, upstream indisponível, UUID inválido, CSV defeituoso e acessos sem autenticação.
2. Mapa e filtros funcionam com fixtures locais; importar mostra os leads no funil e mantém alterações comerciais após nova importação e recarga.
3. A central e o scraper independente usam logo/tema SITH.IA. Desktop e celular sem sobreposição de controles.
4. Serviço real iniciado apenas em loopback, com base original preservada. Automação de envio não é iniciada por este trabalho.
5. Relatório das skills e instruções de abertura disponíveis em arquivos locais. Não declarar pareamento do WhatsApp ou resposta real de IA como validados se dependerem da conta do usuário.
