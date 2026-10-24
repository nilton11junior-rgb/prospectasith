"""Segmentos por situação digital da empresa e montagem das mensagens (variáveis e rodízio)."""
import random, re
from datetime import datetime
from estado import config
from agenda import BR


REDES = ("instagram.com", "facebook.com", "wa.me", "whatsapp.com", "linktr.ee")


def tem_site(l):
    s = (l.get("site") or "").lower()
    return bool(s) and not any(h in s for h in REDES)


def tem_instagram(l):
    return bool(l.get("instagram")) or "instagram.com" in (l.get("site") or "").lower()


def reputacao_baixa(l):
    return 0 < (l.get("nota") or 0) < 4.0 and (l.get("avaliacoes") or 0) >= 5


# ordem = prioridade: o lead cai no primeiro segmento LIGADO cuja regra bate
SEGMENTOS = {
    "reputacao": {"nome": "Nota baixa no Google", "regra": reputacao_baixa,
                  "descricao": "Nota abaixo de 4,0 com 5+ avaliações. Abordagem sobre atendimento e reputação, sem citar a nota."},
    "sem_presenca": {"nome": "Sem site e sem Instagram", "regra": lambda l: not tem_site(l) and not tem_instagram(l),
                     "descricao": "Só aparece no Google Maps. Quem procura não acha mais nada sobre a empresa."},
    "so_instagram": {"nome": "Só Instagram, sem site", "regra": lambda l: not tem_site(l) and tem_instagram(l),
                     "descricao": "Tem Instagram mas nenhum site: depende do algoritmo e perde quem pesquisa no Google."},
    "site_sem_instagram": {"nome": "Tem site, sem Instagram", "regra": lambda l: tem_site(l) and not tem_instagram(l),
                           "descricao": "Tem site, mas sem rede social ativa encontrada. Oportunidade de conteúdo e captação."},
    "site_e_instagram": {"nome": "Tem site e Instagram", "regra": lambda l: tem_site(l) and tem_instagram(l),
                         "descricao": "Presença completa. Foco em converter mais: automação, atendimento com IA, landing page."},
}


def segmento_de(l, so_ativos=True):
    for sid, s in SEGMENTOS.items():
        if so_ativos and not config["campanhas"].get(sid, {}).get("ativo"):
            continue
        try:
            if s["regra"](l):
                return sid
        except Exception:
            continue
    return None


def saudacao():
    h = datetime.now(BR).hour
    return "Bom dia" if h < 12 else "Boa tarde" if h < 18 else "Boa noite"


def nome_curto(nome):
    """'Litoral Tec Ar - Vendas, Instalação e Manutenção' -> 'Litoral Tec Ar'; nomes em CAIXA ALTA viram Título."""
    n = re.split(r"\s+[-|–—:]\s+|\s*\|\s*", nome or "")[0].strip() or (nome or "")
    if n.isupper() and len(n) > 4:
        # 1ª palavra curta costuma ser sigla da marca (RD, IMS, M.E.R): mantém
        n = " ".join(p if i == 0 and len(p) <= 5 else p.capitalize() for i, p in enumerate(n.split()))
        n = re.sub(r"(?<= )(De|Da|Do|Das|Dos|E)(?= )", lambda m: m.group(0).lower(), n)
    return n


def preenche(texto, l):
    nota, aval = l.get("nota") or 0, l.get("avaliacoes") or 0
    # {elogio}: só elogia o que é verdade; vazio para nota mediana (o texto continua natural sem ele)
    elogio = (" com ótimas avaliações" if nota >= 4.6 and aval >= 15 else
              " com boas avaliações" if nota >= 4.2 and aval >= 5 else "")
    cidade = l.get("cidade") or "sua cidade"
    out = (texto.replace("{nome}", nome_curto(l.get("nome"))).replace("{cidade}", cidade).replace("{bairro}", l.get("bairro") or cidade)
           .replace("{categoria}", (l.get("categoria") or "empresas").lower()).replace("{nota}", str(nota).replace(".", ","))
           .replace("{avaliacoes}", str(aval)).replace("{elogio}", elogio).replace("{saudacao}", saudacao()))
    return re.sub(r"[ \t]+", " ", out).strip()


_ultima_variante = {}


def escolhe_variante(chave, variantes):
    """Rodízio: nunca repete a mesma variação seguida (textos idênticos em massa chamam atenção do WhatsApp)."""
    i = _ultima_variante.get(chave, -1)
    opcoes = [j for j in range(len(variantes)) if j != i] or [0]
    j = random.choice(opcoes)
    _ultima_variante[chave] = j
    return variantes[j]
