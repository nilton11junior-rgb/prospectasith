"""Apoio dos testes do painel (só biblioteca padrão): pasta de dados temporária, namespace `app`, modelo de lead,
reinício de estado e base para testes HTTP. Não é um teste (o nome não começa com test_)."""
import json, os, sys, tempfile, threading, unittest, urllib.error, urllib.request

TMP = tempfile.mkdtemp(prefix="prospecta-teste-")
os.environ["PROSPECTA_DADOS"] = TMP
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import types  # noqa: E402
import agente, agenda, buscas, campanhas, disparo, estado, lixeira, normaliza, rotas_auth, seguranca_http, server, whatsapp  # noqa: E402,F401

# um só namespace com os módulos do painel: os testes não dependem de onde cada função mora
app = types.SimpleNamespace(**{k: v for m in (estado, normaliza, campanhas, agenda, whatsapp, disparo, server)
                               for k, v in vars(m).items() if not k.startswith("__")})


def lead(**kw):
    base = {"id": kw.pop("id", "L1"), "nome": "Clínica Sorriso", "categoria": "Dentista", "cidade": "Guarujá",
            "bairro": "Centro", "uf": "SP", "status": "novo", "whatsapp": "5513988887777", "tel_digitos": "5513988887777",
            "site": "", "email": "", "instagram": "", "nota": 4.8, "avaliacoes": 120, "historico": [], "buscas": ["b1"], "obs": ""}
    base.update(kw)
    return base


def reinicia():
    """Estado limpo e config padrão a cada teste."""
    with app.lock:
        app.leads.clear(); app.conversas.clear(); app.config.clear(); app.agenda_dados.clear()
        app.pendentes_ia.clear(); app.buscas.clear(); app.fila.clear()
        for nome in os.listdir(app.DIR_BUSCAS):
            os.remove(os.path.join(app.DIR_BUSCAS, nome))
        for nome in os.listdir(TMP):  # carregar() relê os JSON: apaga o que o teste anterior gravou
            if nome.endswith(".json"):
                os.remove(os.path.join(TMP, nome))
    app.carregar()


class HttpBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reinicia()
        cls.srv = app.ThreadingHTTPServer(("127.0.0.1", 0), app.H)
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, caminho, token=None, metodo="GET", corpo=None):
        h = {"Content-Type": "application/json"}
        if token:
            h["X-Prospecta-Token"] = token
        r = urllib.request.Request(self.base + caminho, method=metodo, headers=h,
                                   data=json.dumps(corpo).encode() if corpo is not None else None)
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
