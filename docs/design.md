# Design do painel

## Direção

Ferramenta de trabalho diário: densa, legível e rápida, com identidade SITH.IA. Tema escuro fixo: preto `#09070f`, superfícies `#17131f`, roxo intenso em ações e seleção. Tipografia de sistema, logo original no menu/login/aba e no cabeçalho móvel. A estrutura e os componentes do Prospecta foram preservados.

## Sistema existente

- Tokens de cor em `:root` (`painel/static/app.css`): `--bg`, `--surface`, `--ink`, `--muted`, `--line`, `--accent`, cores de status (`--green`, `--warn`, `--err`, `--violet`) e `--wa` para WhatsApp; redefinidos no modo escuro.
- A marca vigente está nos overrides de `painel/static/sithia.css`, carregados depois da base: borda `#332641`, texto `#f4efff`, acento `#a456ff`, texto secundário `#bcaacf`. Verde conserva significado para WhatsApp/sucesso; fundos de QR continuam brancos para leitura.
- `scraper.css` organiza formulário + mapa e a tabela paginada, com filtros e importação explícita. No celular a grade vira uma coluna e a tabela rola dentro do seu contêiner.
- Componentes: `.card`, `.btn` (`pri`, `wa`, `sm`, `danger`, `ghost`), `.pill` (status `s-*`, estado de busca `e-*`), `.chip`, `.switch`, `.note` (`info`, `err`, `ok`), `.in` (campos), tabela de leads, quadro do funil (`.kb`), ficha lateral (`.drawer`), bolhas de WhatsApp (`.wa-prev`, `.bubble`, `.msg`), horários (`.slot`).
- Ícones SVG inline no objeto `I` (`static/js/base.js`).
- Navegação por hash (`#/inicio`, `#/leads`, `#/whatsapp/<número>` …); cada tela é uma função em `VIEWS`.
- Menu lateral em grupos que abrem e fecham (`NAV` em `static/js/base.js`): "Início" solto e os grupos Prospecção, Atendimento e Ajustes. O grupo da tela atual fica sempre aberto; os outros lembram a escolha no navegador (`localStorage`). Grupo fechado soma os avisos dos itens (mensagens não lidas, buscas rodando, lixeira). Cada área nova entra como um grupo em `NAV`. Cada grupo é um botão com `aria-expanded`; o conteúdo fechado fica `inert`; `prefers-reduced-motion` desliga a animação.

## Interação e acessibilidade

- Confirmação de ação sensível sem diálogo nativo: primeiro clique arma, segundo (até 4 s) confirma (`confirma()`).
- Avisos curtos por `toast`. Atualização automática a cada 3 s só quando a tela mudou e sem a ficha aberta.
- Todo texto vindo de leads e conversas passa por `esc()` antes de entrar no HTML.
- Pendências conhecidas: botões só com ícone sem `aria-label` em alguns lugares; contraste não auditado formalmente.
- Controles novos têm rótulos, foco visível e mensagens `role=status`. A tela de mapa descarta respostas atrasadas ao navegar, libera o Leaflet ao sair e permite recuperar conexão sem recarregar. Sem conexão, importar é desabilitado e resultados já carregados continuam consultáveis.

## Layout

Barra lateral fixa + conteúdo; abaixo de ~860 px as grades viram uma coluna e a lateral abre pelo botão de menu. Testado na largura do painel do Claude (≈500 px) e em desktop.
