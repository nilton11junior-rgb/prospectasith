# Exclusão completa de buscas

Pedido: remover buscas diretamente do histórico e apagar seus leads de todas as áreas do CRM, individualmente e em lote.

Decisões: botões visíveis junto ao nome, seleção de linhas, excluir selecionadas/todas; resumo com quantidades e confirmação explícita. Leads compartilhados também saem das outras buscas. Conversas locais, reservas, pendências IA e filtros da busca são limpos. Não apaga mensagens no telefone do cliente. Busca ativa exige cancelamento. Backup local antes da gravação. Jobs do motor excluídos são bloqueados contra reimportação; limpeza remota pode ficar pendente se o motor estiver offline.

- [x] Testar cascata, seleção inválida/ativa, confirmação desatualizada, backup, persistência e compartilhamento.
- [x] Implementar módulo e rotas com as barreiras HTTP existentes.
- [x] Implementar confirmação e ações individuais/em lote no histórico e no detalhe.
- [x] Verificar navegador isolado, suíte completa e reiniciar somente o painel identificado em modo sem automações.

Não executar exclusão em dados reais nesta tarefa. A confirmação ocorre na interface quando o operador utilizar a função.

Verificação: 103 testes aprovados (90 painel + 13 scripts), sintaxe Python/JS válida; aviso legado de 451 linhas em `scripts/scrape.py`. Navegador: exclusão individual/em lote/todas, cancelamento, aceite obrigatório, aviso de compartilhamento e celular. Correções de regressão: seleção de todas, confirmação durante progresso de busca não relacionada, conservação dos objetos usados por trabalhadores e bloqueio de gravação atrasada que recriaria uma busca apagada.

Painel real reiniciado em modo sem automações. Comparação com backup confirmou leads, configuração, senha e conversas preservados. Rota nova validada com seleção vazia (400), sem executar exclusão real. Backup pré-atualização: `painel/dados/backups/antes-exclusao-20261105-110112/`.
