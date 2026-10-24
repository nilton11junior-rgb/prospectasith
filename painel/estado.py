"""Estado compartilhado do painel: configuração, dados em memória, gravação em disco, segredos e login."""
import hashlib, hmac, json, os, secrets, sys, threading, time


HERE = os.path.dirname(os.path.abspath(__file__))


sys.path.insert(0, os.path.join(HERE, os.pardir, "scripts"))
import scrape as kit  # noqa: E402  (reaproveita req, grid, dedupe, extração de email/redes)


PORT = int(os.environ.get("PAINEL_PORT", "8090"))


DADOS = os.environ.get("PROSPECTA_DADOS") or os.path.join(HERE, "dados")  # testes usam uma pasta temporária


DIR_BUSCAS = os.path.join(DADOS, "buscas")


ARQ_LEADS = os.path.join(DADOS, "leads.json")


ARQ_CONFIG = os.path.join(DADOS, "config.json")


os.makedirs(DIR_BUSCAS, exist_ok=True)


UA = kit.UA


TAMANHOS = {  # depth, grid, max_time (s)
    "rapida":   {"depth": 1,  "grid": 0, "max_time": 600},
    "padrao":   {"depth": 5,  "grid": 0, "max_time": 900},
    "completa": {"depth": 10, "grid": 0, "max_time": 1200},
    "cidade":   {"depth": 5,  "grid": 3, "max_time": 900},
}


STATUS_LEAD = ["novo", "contatado", "respondeu", "reuniao", "fechado", "descartado"]


NOME_STATUS = {"novo": "Novo", "contatado": "Contatado", "respondeu": "Respondeu",
               "reuniao": "Reunião marcada", "fechado": "Fechou negócio", "descartado": "Descartado"}


# campos que vêm do Google/site e podem ser atualizados quando o lead aparece de novo numa busca
CAMPOS_CONTATO = ("nome", "categoria", "telefone", "tel_digitos", "tel_tipo", "whatsapp", "whatsapp_origem",
                  "email", "site", "instagram", "facebook", "linkedin", "endereco", "bairro", "cidade", "uf",
                  "cep", "nota", "avaliacoes", "maps", "fechado")


CONFIG_PADRAO = {"templates": [
    {"id": "apresentacao", "nome": "Primeiro contato",
     "texto": "Olá, tudo bem? Encontrei a {nome} no Google Maps aqui em {cidade} e queria conversar rapidinho "
              "sobre uma ideia para trazer mais clientes para vocês. Posso te mandar?"},
    {"id": "sem_site", "nome": "Para quem não tem site",
     "texto": "Oi! Vi a {nome} no Google com ótimas avaliações, mas não encontrei um site de vocês. "
              "Trabalho justamente ajudando {categoria} de {cidade} a aparecer melhor na internet. Posso te mostrar um exemplo?"},
    {"id": "followup", "nome": "Retomar conversa",
     "texto": "Oi, tudo certo? Passando aqui para retomar nossa conversa sobre a {nome}. Conseguiu dar uma olhada?"},
], "padrao": "apresentacao", "auto_contatado": True,
    # agente de atendimento (IA) que responde os leads no WhatsApp interno
    "agente": {"base": "", "instrucoes": "", "auto_responder": False, "modelo": "sonnet", "espera_s": 25},
    # horários livres para reuniões/chamadas (dias: 0=segunda … 6=domingo)
    "agenda": {"dias": [0, 1, 2, 3, 4], "inicio": "09:00", "fim": "18:00", "duracao": 30, "antecedencia_h": 2},
    # disparo automático da primeira mensagem para leads novos com WhatsApp
    "auto_envio": {"ativo": False, "modo": "template", "template": "apresentacao", "limite_dia": 30,
                   "intervalo_min": 120, "intervalo_max": 300, "hora_ini": "09:00", "hora_fim": "18:00",
                   "dias": [0, 1, 2, 3, 4], "buscas": []}}


ARQ_CONVERSAS = os.path.join(DADOS, "conversas.json")


ARQ_AGENDA = os.path.join(DADOS, "agenda.json")


lock = threading.RLock()


buscas = {}          # id -> busca


leads = {}           # id -> lead


config = {}


conversas = {}       # numero (55DDD…) -> conversa do WhatsApp interno com um lead do CRM


agenda_dados = {}    # {"reservas": [...]}


fila = []            # ids de buscas aguardando


fila_cond = threading.Condition(lock)


def _grava(caminho, obj):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, caminho)


def salvar_busca(b):
    with lock:
        _grava(os.path.join(DIR_BUSCAS, f"{b['id']}.json"), b)


def salvar_leads():
    with lock:
        _grava(ARQ_LEADS, leads)


def salvar_config():
    with lock:
        _grava(ARQ_CONFIG, config)


def _le(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def registrar(l, tipo, txt):
    agora = time.time()
    l.setdefault("historico", []).append({"t": agora, "tipo": tipo, "txt": txt})
    l["atualizado_em"] = agora
    if tipo == "whatsapp":
        l["ultimo_contato"] = agora


def _segredo(nome):
    """Lê (ou cria) um segredo aleatório em painel/dados/<nome>. Compartilhado com os outros serviços."""
    caminho = os.path.join(DADOS, nome)
    try:
        with open(caminho, encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return v
    except OSError:
        pass
    v = secrets.token_hex(32)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(v)
    return v


API_TOKEN = _segredo("api_token")    # MCP e scripts locais (header X-Prospecta-Token)


WA_TOKEN = _segredo("wa_token")      # webhook do WAHA -> painel (header X-WA-Token)


WAHA_KEY = _segredo("waha_key")      # painel -> WAHA (header X-Api-Key)


WAHA_URL = os.environ.get("WAHA_URL", "http://127.0.0.1:3000")


WAHA_SESSAO = "default"


ARQ_AUTH = os.path.join(DADOS, "auth.json")


ARQ_SESSOES = os.path.join(DADOS, "sessoes.json")


sessoes = {}         # token do cookie -> expira_em


def _hash(senha, sal):
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal), 200_000).hex()


def auth_configurado():
    return bool(_le(ARQ_AUTH, {}).get("hash"))


def define_senha(senha):
    sal = secrets.token_hex(16)
    _grava(ARQ_AUTH, {"sal": sal, "hash": _hash(senha, sal)})


def confere_senha(senha):
    a = _le(ARQ_AUTH, {})
    return bool(a.get("hash")) and hmac.compare_digest(a["hash"], _hash(senha, a["sal"]))


def nova_sessao():
    tok = secrets.token_urlsafe(32)
    with lock:
        agora = time.time()
        for t in [t for t, exp in sessoes.items() if exp < agora]:
            del sessoes[t]
        sessoes[tok] = agora + 30 * 86400
        _grava(ARQ_SESSOES, sessoes)
    return tok


pendentes_ia = {}    # numero -> horário em que a IA deve responder


ARQ_ENVIOS = os.path.join(DADOS, "envios.json")


envios = _le(ARQ_ENVIOS, {"dia": "", "n": 0, "proximo": 0, "ultimo_erro": ""})
