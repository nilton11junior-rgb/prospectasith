"""Planejamento comercial por evidência e etapa do funil."""
import re

from campanhas import SEGMENTOS, preenche, reputacao_baixa, segmento_de, tem_instagram, tem_site

GRUPOS = {
    'conversao': {'nome': 'Captação e atendimento', 'oferta': 'Corrigir o caminho até o contato',
                  'pergunta': 'Como vocês recebem os pedidos que chegam pelo site hoje?'},
    'presenca': {'nome': 'Presença digital', 'oferta': 'Site ou página para captar pedidos',
                 'pergunta': 'Vocês têm uma página própria para apresentar os serviços e receber pedidos?'},
    'performance': {'nome': 'Velocidade do site', 'oferta': 'Melhorar a experiência no celular',
                    'pergunta': 'Vocês já acompanharam como o site abre no celular dos clientes?'},
    'mensuracao': {'nome': 'Mensuração de campanhas', 'oferta': 'Revisar o rastreamento de contatos',
                   'pergunta': 'Como vocês identificam quais anúncios viram pedidos de orçamento?'},
    'reputacao': {'nome': 'Reputação e atendimento', 'oferta': 'Organizar resposta e acompanhamento',
                  'pergunta': 'Como vocês acompanham as avaliações e os retornos dos clientes hoje?'},
    'crescimento': {'nome': 'Crescimento', 'oferta': 'Melhorar a conversão dos canais existentes',
                    'pergunta': 'Qual canal traz mais pedidos de orçamento para vocês hoje?'},
    'qualificar': {'nome': 'Qualificação', 'oferta': 'Entender a estrutura e o canal de captação',
                   'pergunta': 'Por onde os clientes costumam chegar até vocês hoje?'},
}

PRIORIDADES = {
    'reuniao': 'Preparar reunião',
    'responder': 'Retomar conversa',
    'acompanhar': 'Acompanhar contato',
    'priorizar': 'Priorizar abordagem',
    'qualificar': 'Qualificar lead',
}


def prospectavel(lead):
    return not (lead.get('optout') or lead.get('fechado') or lead.get('status') in ('fechado', 'descartado'))


def _grupo(lead, relatorio, anuncios):
    site = relatorio.get('site') or {}
    wa = relatorio.get('whatsapp') or {}
    velocidade = relatorio.get('velocidade') or {}
    if wa.get('estado') in ('erro_http', 'numero_invalido'):
        codigo = wa.get('status')
        evidencia = f'O link do WhatsApp retornou HTTP {codigo}.' if codigo else 'O link retornou um número inválido.'
        return 'conversao', evidencia
    if site.get('estado') == 'erro_http':
        return 'conversao', f'O site retornou HTTP {site.get("status")}.'
    nota = velocidade.get('nota')
    if velocidade.get('estado') == 'medido' and isinstance(nota, (int, float)) and nota < 50:
        return 'performance', f'Lighthouse móvel registrou {nota}/100.'
    if site.get('estado') == 'respondendo' and (site.get('ttfb_ms') or 0) > 1800:
        return 'performance', f'Resposta inicial medida em {site["ttfb_ms"]} ms.'
    if site.get('estado') in ('sem_site', 'somente_perfil') and not tem_site(lead):
        return 'presenca', 'O cadastro aponta para um perfil social.' if tem_instagram(lead) else 'Site próprio não localizado no cadastro.'
    if site.get('estado') == 'respondendo':
        tags = {t['nome'] for t in relatorio.get('tags', [])}
        for plataforma, tag in (('meta', 'Meta Pixel'), ('google', 'Google Ads')):
            if (anuncios.get(plataforma) or {}).get('estado') == 'encontrado' and tag not in tags:
                return 'mensuracao', f'Anúncio registrado na biblioteca. {tag} não apareceu no HTML analisado.'
    if reputacao_baixa(lead):
        return 'reputacao', f'Google Maps registra {lead["nota"]}/5 em {lead["avaliacoes"]} avaliações.'
    if tem_site(lead) and site.get('estado') == 'respondendo':
        return 'crescimento', 'O site respondeu à coleta.'
    if not tem_site(lead):
        return 'qualificar', 'Site próprio ainda não confirmado.'
    return 'qualificar', 'A estrutura digital ainda precisa de revisão.'


def oportunidade(lead, estado_auditoria):
    auditoria = lead.get('auditoria') or {}
    relatorio = auditoria.get('relatorio') or {}
    grupo, evidencia = _grupo(lead, relatorio, auditoria.get('anuncios') or {})
    status = lead.get('status') or 'novo'
    canal = ('WhatsApp' if lead.get('whatsapp') and not lead.get('sem_whatsapp') else
             'E-mail' if lead.get('email') else 'Instagram' if lead.get('instagram') else '')
    if status == 'reuniao':
        prioridade, acao = 'reuniao', 'Leve a evidência para a chamada e confirme onde a empresa perde contatos.'
    elif status == 'respondeu':
        prioridade, acao = 'responder', 'Retome a conversa e faça uma pergunta sobre o problema observado.'
    elif status == 'contatado' or lead.get('ultimo_contato'):
        prioridade, acao = 'acompanhar', 'Revise a conversa e escolha o próximo passo da campanha.'
    elif canal and grupo not in ('qualificar', 'crescimento'):
        prioridade, acao = 'priorizar', 'Revise a evidência e personalize a primeira pergunta.'
    else:
        prioridade = 'qualificar'
        acao = 'Confirme o canal profissional da empresa.' if not canal else 'Confira o relatório antes de abordar.'
    segmento = segmento_de(lead)
    evidencias = [evidencia]
    tags = [t['nome'] for t in relatorio.get('tags', [])]
    if tags:
        evidencias.append('Tags detectadas no HTML: ' + ', '.join(tags) + '.')
    cadastro = relatorio.get('cadastro') or {}
    if cadastro.get('cnpj'):
        evidencias.append('Cadastro empresarial consultado na BrasilAPI.')
    abordagem = ''
    if prospectavel(lead) and status == 'novo' and not lead.get('ultimo_contato') and canal:
        gancho = preenche('{gancho}', lead)
        if re.search(r'https?://|www\.|\?|[\r\n]|\b[\w.-]+\.(?:com|br|net|org|io)\b', gancho, re.I):
            gancho = 'Encontrei a empresa no Google.'
        abordagem = 'Oi, pessoal! ' + gancho + ' ' + GRUPOS[grupo]['pergunta']
    return {
        'id': lead['id'], 'nome': lead.get('nome') or 'Empresa', 'cidade': lead.get('cidade') or '',
        'status': status, 'grupo': grupo, 'prioridade': prioridade, 'canal': canal, 'acao': acao,
        'segmento': segmento or '', 'campanha': SEGMENTOS[segmento]['nome'] if segmento else '',
        'evidencias': evidencias, 'abordagem': abordagem, 'auditoria': estado_auditoria,
        'auditado_em': relatorio.get('atualizado_em'),
    }
