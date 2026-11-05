# Lixeira no histórico de buscas

Pedido: descartar buscas que deram errado diretamente em **Buscas**.

Decisão: manter a lixeira existente; acesso sempre visível no cabeçalho e botão em cada linha. Busca em andamento exige cancelamento antes. Usar a confirmação já adotada pelo CRM, permitir restauração e preservar leads trabalhados.

- [x] Reproduzir no navegador isolado a ausência dos botões.
- [x] Acrescentar as ações na lista e reutilizar o fluxo do detalhe.
- [x] Validar confirmação, descarte, restauração, preservação de leads, erro de API e busca ativa.
- [x] Rodar verificação do projeto e atualizar a documentação.

Navegador: reprodução inicial sem os dois acessos; após a alteração, descarte e restauração funcionam com backend real e dados fictícios. Primeiro clique não altera dados nem abre detalhes; falha HTTP mantém a linha; ação do detalhe continua funcionando. Celular 390 px sem transbordamento e nenhum erro JavaScript.

Nenhuma busca real será excluída durante a validação.

Verificação: `scripts/verificar.py`, 87 testes aprovados, sintaxe Python/JS válida, dados fora do Git. Mantido somente o aviso anterior de 451 linhas em `scripts/scrape.py`. `git diff --check` sem erros.
