# Catálogo de serviços e preços — design

Data: 2026-11-01. Sub-projeto 2 de 6 (menu, **catálogo**, propostas, clientes, tarefas, relatórios). Abordagem escolhida: **A, catálogo simples** (sem pacotes).

## Objetivo

Registrar o que o usuário vende, com preço de tabela, para alimentar as **propostas** (sub-projeto 3) e os **clientes** (sub-projeto 4). Os preços são **internos**: a IA do WhatsApp nunca os vê nem os cita (regra da estratégia de vendas: preço só na chamada).

Sucesso = o usuário cadastra, edita, desativa e exclui serviços numa tela, os dados sobrevivem a reiniciar o painel, e um teste prova que nenhum preço do catálogo chega ao prompt da IA.

## Dados

Arquivo `painel/dados/catalogo.json` (fora do git, escrita atômica como os demais): `{"servicos": [...]}`.

| Campo | Regra |
|---|---|
| `id` | texto único gerado (12 hex) |
| `nome` | obrigatório, até 80 caracteres, único entre os serviços (sem diferenciar maiúsculas/acentos) |
| `descricao` | texto livre, até 1000 caracteres (o que está incluído) |
| `cobranca` | `"unico"` ou `"mensal"` |
| `preco` | inteiro em **centavos**, maior que 0 |
| `prazo_dias` | inteiro de 1 a 365 ou `null`; sempre `null` quando `cobranca` é `"mensal"` |
| `entrada_pct` | inteiro de 0 a 100 (sinal); 0 quando `cobranca` é `"mensal"` |
| `ativo` | boolean; desativar tira o serviço das escolhas futuras sem apagar |
| `ordem` | inteiro; a lista aparece ordenada por ele, depois por nome |
| `criado_em`, `atualizado_em` | epoch em segundos |

Decisão para os sub-projetos seguintes: a proposta guarda uma **cópia** do nome, descrição, cobrança e preço no momento em que é criada. Mudar ou excluir um serviço do catálogo nunca altera uma proposta ou cliente existente.

## Comportamento

- Criar, editar, ativar/desativar e excluir. Excluir é definitivo (ainda não há propostas ligadas; quando houver, o sub-projeto 3 passa a bloquear a exclusão de serviço em uso e só permite desativar).
- Validação no servidor com mensagem em português; a tela mostra a mensagem. Dados inválidos nunca são gravados.
- **Uma única conversão de moeda, no servidor** (`catalogo.py`). O campo `preco` recebido como **texto** é lido como reais ("1.500,00", "1500", "R$ 99,9"); recebido como **número inteiro** é lido como centavos. A tela envia o texto digitado; a API sempre devolve inteiro em centavos. A tela só formata para exibir (centavos → "R$ 1.500,00").

## API (mesmas barreiras das demais rotas: login/token, Origin e JSON)

| Método e rota | O que faz |
|---|---|
| `GET /api/catalogo` | lista ordenada, com `ativos` e `total` |
| `POST /api/catalogo` | cria; devolve o serviço (201) |
| `PUT /api/catalogo/<id>` | edita campos enviados; 404 se não existe; 400 se inválido |
| `POST /api/catalogo/<id>/ativo` | corpo `{"ativo": true/false}` |
| `DELETE /api/catalogo/<id>` | exclui |

MCP: ferramenta `catalogo` **somente leitura** (lista os serviços para o agente do usuário). Nenhuma ferramenta de escrita.

## Interface

- Novo grupo **Vendas** no menu (`NAV` em `static/js/base.js`) com o item **Catálogo** (ícone novo). Propostas e Clientes entram nesse grupo nos próximos sub-projetos.
- Tela `#/catalogo`: cartões em grade (nome, selo Único ou Mensal, preço em R$, prazo, entrada, descrição curta). Botão "Novo serviço". Cada cartão edita no próprio lugar (nome, descrição, cobrança, preço, prazo, entrada) com Salvar/Cancelar; menu do cartão: Desativar/Ativar, Excluir (dois cliques para confirmar). Desativado fica esmaecido.
- Tela vazia: mensagem e botão "Novo serviço". Sem exemplos com preço inventado.
- Preço digitado como "1.500,00" ou "1500"; mostrado como "R$ 1.500,00". Cobrança mensal mostra "/mês" e esconde prazo e entrada.
- Largura estreita (painel do Claude, celular): uma coluna; botões nunca cortados.

## Arquivos

`painel/catalogo.py` (regras, conversão de moeda, gravação), `painel/rotas_catalogo.py`, `painel/static/js/vendas.js`, `painel/static/js/base.js` (grupo e ícone), `painel/static/app.css` (cartões), `painel/estado.py` (`ARQ_CATALOGO`, dict em memória), `painel/server.py` (carga e rotas), `painel/mcp_server.py` (leitura), `painel/test_catalogo.py`, `painel/testes_comum.py` (limpar o arquivo entre testes), docs (`architecture.md`, `PRODUCT.md`, `quality.md`, `design.md`).

## Testes (escritos antes do código)

1. Validação: nome vazio, nome repetido (ignora maiúsculas e acento), preço zero/negativo/texto, entrada fora de 0–100, prazo fora de 1–365, cobrança inválida.
2. Mensal zera prazo e entrada.
3. Criar, editar, ativar/desativar, excluir; ordenação.
4. Conversão de moeda: texto "1.500,00", "1500", "1500,5", "R$ 99" viram 150000, 150000, 150050 e 9900 centavos; inteiro 12345 é lido como 12345 centavos; "abc", "", "-5", "1,2,3" e `true` são recusados.
5. Persistência: recarrega do disco após reiniciar.
6. API: 401 sem login; criar/editar/excluir pelo token; 400 com dado inválido; 404 em id inexistente.
7. Preço interno: depois de cadastrar um serviço de preço marcador, `prompt_conversa` e `primeira_mensagem` (modo IA) não contêm o valor nem o nome do serviço.
8. MCP: `tools/list` inclui `catalogo` e não inclui ferramenta de escrita do catálogo.

## Fora do escopo

Pacotes, desconto, impostos, parcelamento (ficam nas propostas), várias moedas, histórico de preços, importação por planilha.

## Riscos e decisões abertas

- Excluir hoje é livre; vira "só desativar quando em uso" no sub-projeto 3 (anotado aqui para não esquecer).
- Preço em centavos exige cuidado na exibição; a leitura do texto fica só em `catalogo.py` (com teste) e `vendas.js` apenas formata para mostrar.
