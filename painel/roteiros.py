"""Textos padrão: estratégia e variações por segmento, follow-ups e o prompt de sistema da IA."""


SISTEMA_IA = """Você é um agente de pré-atendimento comercial por WhatsApp, em português do Brasil.
Regras:
- Use SOMENTE as informações da BASE DE CONHECIMENTO. Se não souber, diga que confirma na chamada.
- Mensagens curtas (1 a 3 frases), naturais, sem parecer robô, no máximo 1 emoji. Uma pergunta por vez.
- Objetivo: entender a necessidade e marcar uma chamada. Ofereça só horários da lista HORÁRIOS LIVRES
  (2 ou 3 opções). Quando o lead aceitar um horário da lista, use acao "agendar" com esse horário exato.
- Se pedirem algo que exige uma pessoa (negociação, reclamação, assunto fora da base), use acao "humano".
- Se a pessoa disser que não tem interesse ou pedir para parar, despeça-se educadamente e use acao "encerrar".
- Nunca invente preços, prazos ou promessas. Nunca diga que é humano se perguntarem.
Responda APENAS um objeto JSON, sem texto fora dele:
{"mensagem": "texto para enviar (vazio se não for responder)", "acao": "responder|agendar|humano|encerrar|nada",
 "horario": "AAAA-MM-DD HH:MM ou null", "resumo": "uma linha para o CRM"}"""


CAMPANHAS_PADRAO = {
    # Princípios de todos os roteiros: 1) gancho específico (algo real que vimos da empresa),
    # 2) a perda que ela tem hoje (cliente pesquisa e vai pro concorrente), 3) quem somos em 1 linha,
    # 4) pergunta de sim/não com pouco compromisso ("posso te mostrar?"), sem link, sem preço.
    "reputacao": {"ativo": False, "estrategia": (
        "Nunca cite a nota nem críticas: a empresa sabe e fica na defensiva. Fale de bastidores do atendimento: "
        "resposta rápida no WhatsApp, cliente que não fica sem retorno, pedido automático de avaliação para quem saiu "
        "satisfeito. Objeções: 'quanto custa' -> depende do volume, mostro na chamada de 15 min; 'já respondemos' -> "
        "pergunte quanto tempo leva no fim de semana. Objetivo: marcar a chamada."),
        "variantes": [
            "{saudacao}! Encontrei a {nome} pesquisando {categoria} em {cidade}. Trabalho ajudando empresas a responder todo cliente no WhatsApp na hora e a transformar quem saiu satisfeito em avaliação no Google. Posso te mostrar como funciona na prática?",
            "Olá, tudo bem? Vi a {nome} no Google. Uma coisa que mais pesa na escolha do cliente hoje é a rapidez da resposta e as avaliações recentes. Eu automatizo essas duas coisas. Faz sentido eu te mandar um exemplo?",
            "{saudacao}! Ajudo empresas de {cidade} a nunca deixar cliente sem resposta e a receber mais avaliações positivas, tudo pelo WhatsApp. Vi a {nome} e acho que encaixa bem. Você teria interesse em ver?",
        ]},
    "sem_presenca": {"ativo": True, "estrategia": (
        "A empresa só existe no Google Maps: quem pesquisa não acha site nem Instagram e fica com o concorrente que "
        "aparece melhor. Valorize o que ela já tem (avaliações, tempo de mercado) e mostre que está deixando cliente na "
        "mesa. Ofereça mostrar um exemplo ou um esboço da página dela, nunca o preço por mensagem. Objeções: 'já tenho "
        "muito cliente' -> site traz o cliente que paga melhor e pesquisa antes; 'não tenho tempo' -> nós fazemos tudo, "
        "ela só aprova; 'quanto custa' -> depende do que precisa, mostro na chamada de 15 min. Objetivo: marcar a chamada."),
        "variantes": [
            "{saudacao}! Vi a {nome} no Google{elogio}, mas não encontrei um site de vocês. Trabalho justamente ajudando empresas como a de vocês a aparecer melhor na internet e receber mais contatos pelo WhatsApp. Você teria interesse em ver como ficaria?",
            "Olá, tudo bem? Pesquisei {categoria} em {cidade} e a {nome} apareceu{elogio}. Só senti falta de um site: hoje o cliente pesquisa antes de chamar e, sem site, acaba indo para quem aparece mais completo. Posso te mostrar um exemplo do que eu faria para vocês?",
            "{saudacao}! Encontrei a {nome} no Google Maps{elogio}. Vocês já têm o mais difícil, que é a confiança dos clientes. O que falta é uma página que mostre isso para quem ainda não conhece vocês. Posso te mandar uma ideia de como ficaria?",
        ]},
    "so_instagram": {"ativo": True, "estrategia": (
        "Tem Instagram mas não tem site. Elogie o perfil de forma específica. Explique que o Instagram depende do "
        "algoritmo e só alcança quem já segue, enquanto quem pesquisa no Google nunca chega até o perfil. O site "
        "trabalha 24h, aparece no Google e leva direto ao WhatsApp. Objeções: 'o Instagram já basta' -> Instagram é para "
        "quem já conhece, o Google é para quem está procurando agora; 'quanto custa' -> mostro na chamada de 15 min."),
        "variantes": [
            "{saudacao}! Vi o Instagram da {nome}, trabalho muito bonito. Só não encontrei um site: quem pesquisa {categoria} em {cidade} no Google não chega até o perfil de vocês. Você teria interesse em ver como um site ligado ao Instagram e ao WhatsApp ficaria?",
            "Olá, tudo bem? Achei a {nome} pelo Google e fui parar no Instagram de vocês. O Instagram fala com quem já segue; o site pega quem está pesquisando agora e ainda não conhece. Posso te mostrar um exemplo?",
            "{saudacao}! O Instagram da {nome} está ótimo, mas ele depende do algoritmo. Eu ajudo empresas como a de vocês a ter um site que aparece no Google e leva o cliente direto para o WhatsApp de vocês. Faz sentido conversarmos 10 minutinhos?",
        ]},
    "site_sem_instagram": {"ativo": True, "estrategia": (
        "Tem site, mas não encontramos Instagram ativo. Não critique o site. Pergunte de onde vêm os clientes hoje e "
        "ofereça aumentar o retorno do que já existe: página de oferta para campanha, botão e atendimento automático "
        "no WhatsApp, conteúdo que gera procura. Objeções: 'já tenho site' -> a ideia é fazer o site trazer mais "
        "contato, não trocar; 'quanto custa' -> mostro na chamada de 15 min."),
        "variantes": [
            "{saudacao}! Vi o site da {nome}{elogio}, bem apresentado. Fiquei curioso: hoje a maioria dos clientes chega pelo Google ou por indicação? Ajudo empresas de {cidade} a fazer o site gerar mais conversas no WhatsApp.",
            "Olá, tudo bem? Encontrei a {nome} e o site de vocês pesquisando {categoria} em {cidade}. Trabalho com páginas e automações que fazem quem visita o site virar contato no WhatsApp. Você teria interesse em ver um exemplo?",
            "{saudacao}! O site da {nome} já faz a parte dele, mas notei que vocês não estão no Instagram, onde muita gente de {cidade} descobre empresas do seu ramo. Posso te mostrar como juntar os dois para trazer mais clientes?",
        ]},
    "site_e_instagram": {"ativo": True, "estrategia": (
        "Presença digital completa: NÃO venda site. Fale de conversão e velocidade: atendimento com IA no WhatsApp que "
        "responde em segundos, inclusive à noite e no fim de semana, qualifica e já marca horário; landing page para "
        "campanhas. Pergunte sobre volume de mensagens e quanto tempo levam para responder. Objeções: 'já temos "
        "atendente' -> a IA cobre fora do horário e o pico, o atendente fecha; 'quanto custa' -> mostro na chamada de 15 min."),
        "variantes": [
            "{saudacao}! Vi o site e o Instagram da {nome}{elogio}, tudo muito bem feito. Pergunta rápida: quando alguém chama no WhatsApp à noite ou no fim de semana, vocês conseguem responder na hora? Eu automatizo esse atendimento com IA.",
            "Olá, tudo bem? Acompanhei a {nome} pelo Google e pelo Instagram. Trabalho com um atendente de IA no WhatsApp que responde em segundos, tira dúvidas e já agenda com o cliente. Você teria interesse em ver funcionando?",
            "{saudacao}! A {nome} já tem uma presença online forte. O próximo passo costuma ser não perder ninguém no WhatsApp: resposta imediata, 24h, com agendamento automático. Posso te mostrar como ficaria para vocês?",
        ]},
}


FOLLOWUP_PADRAO = {"ativo": True, "dias": [2, 5], "variantes": [
    # 1º: retomada leve, oferece algo concreto
    ["{saudacao}! Passando só para saber se você viu minha mensagem sobre a {nome} 🙂 Se quiser, monto um exemplo rápido para você ver sem compromisso.",
     "Oi! Retomando por aqui: ainda faz sentido eu te mostrar a ideia para a {nome}? É coisa de 10 minutinhos.",
     "{saudacao}! Sei que a rotina é corrida. Posso te mandar o exemplo por aqui mesmo, aí você vê quando tiver um tempinho?"],
    # 2º: despedida (quebra o padrão e costuma gerar resposta)
    ["Última mensagem, prometo! Se não for o momento, sem problema. Quando fizer sentido, é só responder aqui. Sucesso para a {nome}!",
     "Vou parar de insistir 🙂 Fica o contato salvo: quando quiser melhorar a presença da {nome} na internet, é só me chamar.",
     "Imagino que agora não seja prioridade, tudo certo. Se mudar, é só responder esta mensagem. Um abraço!"],
]}
