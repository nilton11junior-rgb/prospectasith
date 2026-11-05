# Central SITH.IA (Prospecta) — produto

## Problema

Quem vende serviços digitais (sites, automação, atendimento com IA) para empresas locais gasta horas achando contatos e abordando um por um. O Prospecta encontra as empresas no Google Maps, separa por situação (sem site, só Instagram, etc.) e cuida da abordagem e do agendamento pelo WhatsApp.

## Público e papéis

- **Dono do painel** (um usuário, no próprio computador): faz buscas, revisa leads, aprova mensagens, liga/desliga automações e atende as chamadas marcadas.
- **Lead** (empresa encontrada): recebe a mensagem no WhatsApp e responde; não acessa o sistema.

## Fluxos principais (implementados)

0. **Mapa integrado:** buscar pelo SITH.IA Scraper, acompanhar pontos, filtrar e exportar, importar a busca concluída para a base única do CRM. Reimportar preserva o estado comercial e não cria cópias de leads. Resultados sem coordenadas entram na base; as buscas importadas aparecem no histórico e na lixeira do Prospecta.

1. **Buscar:** nicho + cidade (+ bairro) → motor do Google Maps → leads com telefone, WhatsApp provável, site, e-mail e redes (o painel visita o site da empresa).
2. **Organizar:** base única sem duplicar, funil (Novo → Contatado → Respondeu → Reunião marcada → Fechou / Descartado), anotações e histórico. Busca ruim vai para a **lixeira** (com motivo): leads novos que vieram só dela saem da base, os já trabalhados ficam; dá para restaurar por 30 dias, depois é apagada.
3. **Abordar:** WhatsApp interno (WAHA, pareado por QR Code). Primeira mensagem manual, ou disparo automático por **segmento** com rodízio de variações, limite diário, intervalo aleatório e horário comercial. Follow-up automático (2 e 5 dias) para quem não respondeu.
4. **Atender:** agente IA (Claude Code da assinatura ou chave de API) responde leads do CRM seguindo base de conhecimento e estratégia do segmento; marca chamada só em horário livre e só confirma depois de reservar; passa para humano ou encerra quando pedem.
5. **Agendar:** agenda com disponibilidade, sem conflito; reserva move o lead para "Reunião marcada".
6. **Operar por agente:** servidor MCP para Claude Code e Codex consultar e operar o CRM, com confirmação para enviar e agendar.

## Fora do escopo

Multiusuário, nuvem, cobrança, envio em massa sem limite, grupos de WhatsApp, leitura de conversas pessoais, revenda de base, raspagem de redes sociais.

## Requisitos e restrições

- Tudo local (Windows); portas só em 127.0.0.1; dados pessoais em `painel/dados/`, fora do git.
- Só números exatos de leads do CRM recebem mensagem ou entram nas conversas; grupos, status e contatos pessoais são ignorados.
- Quem pede para parar sai da lista na hora (palavras como "sair", "não tenho interesse").
- Login por senha (PBKDF2) para o painel; token local para o MCP; token próprio no webhook do WAHA.
- LGPD: uso comercial B2B, sem revenda; respeitar pedidos de exclusão.

## Decisões

- Identidade SITH.IA: logo original, preto e roxo escuro. Menu e fluxos comerciais do Prospecta preservados.
- Motores separados: busca avançada original em 8080 e SITH.IA Scraper em 8081, com a central autenticada em 8090. Preservam-se dados e ajustes de ambos.
- `Central SITH.IA.cmd` abre com envios automáticos pausados; `--automacoes` é a escolha explícita do operador para retomar as rotinas configuradas. Nenhum ajuste de campanha é apagado.

- Python só com biblioteca padrão e JS sem framework: roda em qualquer máquina sem instalar dependências.
- WAHA (motor GOWS) no Docker Desktop em vez de biblioteca embutida: escolha do usuário; build nativo no Windows travou.
- IA pela assinatura do Claude Code (sem chave) por padrão; chave da Anthropic opcional para resposta em segundos.
- Mensagens seguem `docs/estrategia-vendas.md`: 1ª mensagem = elogio + pergunta (sem link, preço nem pitch), conversa com SPIN, Sim ou Sim para a chamada, preço só na chamada, follow-up nos dias 2, 4 e 7. Sem link e com variações também reduz o risco de bloqueio do número.

## Suposições

- Um único operador por instalação.
- O número de WhatsApp pareado é do próprio usuário e aceita o risco de bloqueio por volume.

## Critérios de aceite

- `python -X utf8 scripts/verificar.py` termina com "Resultado: OK".
- Busca concluída aparece em Buscas/Leads; lead de cada segmento gera mensagem sem variável sobrando.
- Mensagem de número fora do CRM não cria conversa; pedido para parar descarta o lead.
- Reserva em horário ocupado é recusada.

## Próxima entrega

Medir taxa de resposta por segmento/variação no painel e usar isso para escolher as melhores variações.
