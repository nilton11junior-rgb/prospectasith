# Exclusão de buscas e leads

O operador pode apagar uma busca ou várias diretamente no histórico. O resumo autenticado calcula buscas, leads únicos, conversas e reservas; a confirmação usa a assinatura desse escopo. Alterações nos registros afetados exigem conferir um novo resumo. Progresso de uma busca sem relação não invalida a confirmação.

## Código e API

- `painel/exclusao_buscas.py`: validação, resumo, backup, remoção em cascata, persistência, bloqueio de reimportação e limpeza pendente dos motores.
- `painel/rotas_lixeira.py`: `POST /api/buscas/exclusao/previa` recebe `ids`; `POST /api/buscas/exclusao` recebe `ids` e `confirmacao` do resumo. Ambas usam as barreiras de login/token, origem, Host e JSON do servidor.
- `painel/static/js/buscas-exclusao.js` e `painel/static/exclusao.css`: seleção persistente durante atualização da lista, diálogo e atualização das áreas após salvar.
- `painel/test_exclusao_buscas.py`: 16 casos de cascata, confirmação, falhas, persistência e concorrência.

## Alcance

Remove o registro da busca e todos os leads encontrados por ela, inclusive compartilhados e trabalhados. Limpa referências nas outras buscas e em cópias guardadas na lixeira, conversas locais, pendências IA e reservas. Atualiza o filtro de buscas das campanhas; se ele perder sua última busca, o envio automático é desligado para não ampliar o público para toda a base. Não apaga mensagens no aplicativo WhatsApp.

Busca em andamento, ou outra busca em andamento que compartilhe os leads afetados, exige cancelamento prévio. Objetos de buscas/leads não relacionados são mantidos para os trabalhadores que ainda os utilizem. Uma gravação atrasada não recria a busca removida.

Um snapshot anterior fica em `painel/dados/backups/exclusoes/`, fora do Git. Falha ao criar o backup impede a exclusão. Em falha de gravação, o snapshot anterior é regravado. Os arquivos continuam usando as gravações individuais atômicas do projeto.

`painel/dados/exclusoes_buscas.json` registra IDs excluídos dos motores. Um job do scraper marcado não aparece na central nem pode ser reimportado. O trabalhador de limpeza tenta remover os jobs remotos a cada 30 segundos, tolerando motor offline e tratando 404 como já removido. Enquanto isso, os dados permanecem excluídos no CRM. Esse trabalhador não envia mensagens.
