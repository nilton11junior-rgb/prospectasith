# Estratégia de vendas (fonte das mensagens)

Método do usuário, em 7 etapas: encontrar, abordar, criar conexão, descobrir o problema, conduzir, apresentar, fechar, fazer follow-up e pós-venda. É a fonte dos textos em `painel/roteiros.py` e das regras do prompt da IA. Se este documento mudar, atualize `roteiros.py`, suba `ROTEIROS_VERSAO` e rode os testes (`painel/test_estrategia.py`).

## 1. Primeiro contato (o que o painel envia sozinho)

- Onde achar: Google Maps, Instagram, comércio local. Canais, em ordem: WhatsApp, DM do Instagram, ligação. (O painel só envia por WhatsApp.)
- Abertura: elogio + algo específico do negócio + uma **pergunta**.
- 1ª mensagem: curta, **sem link, sem preço, sem pitch**.
- Não falar "faço sites", preço nem proposta pronta.
- Interesse se desperta com pergunta, não com oferta.
- Exemplo do método: "Oi, pessoal! Vi que o Aroma Café está bem posicionado no Google. Vocês têm um site próprio ou o link ainda direciona apenas para o Instagram?"
- No painel: `{gancho}` faz o elogio sem inventar (cita avaliações só com nota 4,2+); cada segmento tem 3 variações em rodízio.

## 2. Relacionamento (a IA)

- Conversa humana, sem script decorado. Pergunta, comentário, pergunta; sem interrogatório.
- Confiança: mostrar trabalho feito, nunca prometer. Entender o negócio: o que vende e de onde vem cliente.
- Objetivo: o cliente gostar de falar com você.

## 3. SPIN (a IA e o banco de perguntas por segmento)

Situação (como funciona hoje), Problema (o que incomoda ou falta), Implicação (quanto isso custa), Necessidade (a pessoa diz a solução). O banco de perguntas de cada segmento está em `estrategia` (linhas `S —`, `P —`, `I —`, `N —`) e a IA o recebe junto do lead.

## 4. Sim ou Sim

Nunca perguntar "você quer comprar?". Quem conduz controla o próximo passo: com interesse, a IA oferece **dois horários** da agenda para uma chamada de 15 minutos. Só confirma depois que a reserva entra na agenda.

## 5. Apresentar e vender (na chamada, com o humano)

Mostrar na tela, não descrever. Valor: site = mais cliente. Falar preço com segurança, sem pedir desculpa. Proposta: escopo + prazo + forma de pagamento. Justificar R$ 1.000 / R$ 2.000+ (retorno x custo). "Está caro": comparar com o que ele ganha. "Vou pensar": achar a objeção real. Fechar: próximo passo + entrada/sinal.

**A IA nunca fala de preço, valor ou prazo.** Se perguntarem, diz que depende do negócio e oferece os dois horários da chamada.

## 6. Follow-up

Sequência: dia 1 apresentação, dia 2 follow-up, dia 4 novo contato, dia 7 última tentativa. Sempre algo novo, nunca "e aí?". Para quando o lead responde, pede para parar ou muda de etapa. No painel: `dias = [1, 3, 6]` depois da 1ª mensagem; a última tentativa usa Sim ou Sim com saída fácil. Ainda não existe: follow-up depois da proposta enviada, "visualizou e não respondeu" e recuperar cliente que sumiu.

## 7. Pós-venda (vai para Clientes e Tarefas)

Entrega como experiência, manter contato depois do site no ar, pedir indicação no momento certo, novos projetos do mesmo cliente (upsell), virar recorrência (manutenção/mensalidade) e montar a carteira de clientes. Alimenta o design de **Clientes fechados** (recorrência, indicações) e **Tarefas e retornos** (pedir indicação, oferecer manutenção).
