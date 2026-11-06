"""Consulta cadastral e associação de contatos publicados ao quadro societário."""
import json
import re
from urllib.parse import unquote
from auditoria_http import FalhaHTTP, obter
from auditoria_site import cnpj_valido, host, normal

FONTE = 'https://brasilapi.com.br/api/cnpj/v1/'


def _campo(valor, limite=180):
    return str(valor or '').strip()[:limite]


def _consulta(cnpj):
    resposta = obter(FONTE + cnpj, hosts={'brasilapi.com.br'}, limite=350_000)
    if resposta['status'] == 404:
        return None
    if resposta['status'] != 200:
        raise FalhaHTTP('Cadastro temporariamente indisponível.')
    try:
        dados = json.loads(resposta['texto'])
    except ValueError as e:
        raise FalhaHTTP('Resposta de cadastro inválida.') from e
    if not isinstance(dados, dict) or cnpj_valido(str(dados.get('cnpj', ''))) != cnpj:
        raise FalhaHTTP('A fonte devolveu um CNPJ diferente.')
    return dados


def _nome_empresa(nome):
    sufixos = {'ltda', 'limitada', 'eireli', 'mei', 'me', 'epp', 'sa'}
    return ' '.join(t for t in normal(nome).split() if t not in sufixos)


def _compativel(lead, dados):
    nome = _nome_empresa(lead.get('nome'))
    if not nome:
        return False
    nomes = [_nome_empresa(dados.get(k)) for k in ('nome_fantasia', 'razao_social')]
    nome_ok = nome in nomes or (len(nome.split()) >= 2 and any(
        ' ' + nome + ' ' in ' ' + n + ' ' for n in nomes if n))
    local_ok = all(not lead.get(l) or not dados.get(d) or normal(lead[l]) == normal(dados[d])
                   for l, d in (('uf', 'uf'), ('cidade', 'municipio')))
    return nome_ok and local_ok


def _contatos_socio(nome, paginas):
    nome_normal = normal(nome)
    if len(nome_normal.split()) < 2:
        return []
    evidencias = []
    for pagina in paginas:
        pessoas = [p for p in pagina.pessoas if normal(p.get('name')) == nome_normal]
        for href, rotulos in pagina.contatos_nomeados:
            if nome_normal not in {normal(x) for x in rotulos + [' '.join(rotulos)]}:
                continue
            esquema, valor = href.split(':', 1)
            campo = 'email' if esquema.lower() == 'mailto' else 'telephone'
            pessoas.append({campo: unquote(valor.split('?', 1)[0])})
        for pessoa in pessoas:
            email = _campo(pessoa.get('email'), 160).removeprefix('mailto:').lower()
            if not re.fullmatch(r'[^\s@,]+@[^\s@,]+\.[a-z]{2,}', email) or host('https://' + email.rsplit('@', 1)[-1]) != host(pagina.url):
                email = ''
            telefone = re.sub(r'\D', '', _campo(pessoa.get('telephone'), 40))
            if not 8 <= len(telefone) <= 15:
                telefone = ''
            if email or telefone:
                registro = {'email': email, 'telefone': telefone, 'fonte': pagina.url}
                if registro not in evidencias:
                    evidencias.append(registro)
    return evidencias[:5]


def _cadastro(cnpj, dados, paginas, informado):
    qsa = dados.get('qsa')
    socios = []
    if isinstance(qsa, list):
        for s in qsa[:100]:
            if not isinstance(s, dict) or not s.get('nome_socio'):
                continue
            nome = _campo(s['nome_socio'])
            socios.append({'nome': nome, 'qualificacao': _campo(s.get('qualificacao_socio')),
                           'contatos': _contatos_socio(nome, paginas)})
    telefone = re.sub(r'\D', '', _campo(dados.get('ddd_telefone_1'), 30))
    return {'estado': 'informado' if informado else 'identificado', 'cnpj': cnpj, 'fonte': FONTE + cnpj,
            'razao_social': _campo(dados.get('razao_social')), 'nome_fantasia': _campo(dados.get('nome_fantasia')),
            'cidade': _campo(dados.get('municipio')), 'uf': _campo(dados.get('uf'), 2),
            'situacao': _campo(dados.get('descricao_situacao_cadastral')), 'socios': socios,
            'email': _campo(dados.get('email'), 160), 'telefone': telefone if 8 <= len(telefone) <= 15 else ''}


def consultar(lead, paginas, cnpj_informado=''):
    candidatos = {}
    for pagina in paginas:
        for cnpj in pagina.cnpjs():
            candidatos.setdefault(cnpj, {'cnpj': cnpj, 'publicado_em': pagina.url})
    if cnpj_informado:
        alvo = cnpj_informado
    elif len(candidatos) == 1:
        alvo = next(iter(candidatos))
    else:
        return {'estado': 'ambiguo' if candidatos else 'nao_encontrado', 'candidatos': list(candidatos.values())[:20]}
    candidatos.setdefault(alvo, {'cnpj': alvo})
    try:
        dados = _consulta(alvo)
    except FalhaHTTP:
        return {'estado': 'indisponivel', 'candidatos': list(candidatos.values())[:20]}
    if not dados:
        return {'estado': 'sem_cadastro', 'candidatos': list(candidatos.values())[:20]}
    compatibilidade = _compativel(lead, dados)
    if not cnpj_informado and not compatibilidade:
        candidatos[alvo].update(razao_social=_campo(dados.get('razao_social')),
                                 cidade=_campo(dados.get('municipio')), uf=_campo(dados.get('uf'), 2))
        return {'estado': 'revisar', 'candidatos': list(candidatos.values())[:20]}
    resultado = _cadastro(alvo, dados, paginas, bool(cnpj_informado))
    resultado.update(candidatos=list(candidatos.values())[:20], compativel=compatibilidade)
    return resultado
