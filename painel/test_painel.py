"""Testes do painel Prospecta (só biblioteca padrão).

Rodam numa pasta de dados temporária (PROSPECTA_DADOS): nunca leem nem gravam painel/dados/ e nunca
falam com WhatsApp, Google ou IA.

    python -X utf8 -m unittest discover -s painel -p "test_*.py"
"""
import json, os, sys, tempfile, threading, time, unittest, urllib.error, urllib.request
from datetime import datetime, timedelta

TMP = tempfile.mkdtemp(prefix="prospecta-teste-")
os.environ["PROSPECTA_DADOS"] = TMP
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import types  # noqa: E402
import agente, agenda, buscas, campanhas, disparo, estado, normaliza, rotas_auth, seguranca_http, server, whatsapp  # noqa: E402

# um só namespace com os módulos do painel: os testes não dependem de onde cada função mora
app = types.SimpleNamespace(**{k: v for m in (estado, normaliza, campanhas, agenda, whatsapp, disparo, server)
                               for k, v in vars(m).items() if not k.startswith("__")})


def lead(**kw):
    base = {"id": kw.pop("id", "L1"), "nome": "Clínica Sorriso", "categoria": "Dentista", "cidade": "Guarujá",
            "bairro": "Centro", "uf": "SP", "status": "novo", "whatsapp": "5513988887777", "tel_digitos": "5513988887777",
            "site": "", "instagram": "", "nota": 4.8, "avaliacoes": 120, "historico": [], "buscas": ["b1"], "obs": ""}
    base.update(kw)
    return base


def reinicia():
    """Estado limpo e config padrão a cada teste."""
    with app.lock:
        app.leads.clear(); app.conversas.clear(); app.config.clear(); app.agenda_dados.clear()
        app.pendentes_ia.clear()
        for nome in os.listdir(TMP):  # carregar() relê os JSON: apaga o que o teste anterior gravou
            if nome.endswith(".json"):
                os.remove(os.path.join(TMP, nome))
    app.carregar()


class Normalizacao(unittest.TestCase):
    def test_telefone_celular_e_fixo(self):
        self.assertEqual(app.telefone_br("(13) 98888-7777"), ("5513988887777", "celular"))
        self.assertEqual(app.telefone_br("+55 13 3333-4444"), ("551333334444", "fixo"))
        self.assertEqual(app.telefone_br("0800 123 4567")[1], "0800")

    def test_chave_ignora_55_e_nono_digito(self):
        self.assertEqual(app.chave_num("5513988887777"), app.chave_num("1388887777"))
        self.assertEqual(app.chave_num("abc"), "")


class Mensagens(unittest.TestCase):
    def setUp(self):
        reinicia()

    def test_nome_curto(self):
        self.assertEqual(app.nome_curto("Litoral Tec Ar - Vendas, Instalação e Manutenção"), "Litoral Tec Ar")
        self.assertEqual(app.nome_curto("RD AR CONDICIONADO"), "RD Ar Condicionado")
        self.assertEqual(app.nome_curto("Lavô Guarujá | Astúrias"), "Lavô Guarujá")

    def test_elogio_so_quando_verdade(self):
        self.assertIn("ótimas avaliações", app.preenche("x{elogio}", lead(nota=4.9, avaliacoes=50)))
        self.assertIn("boas avaliações", app.preenche("x{elogio}", lead(nota=4.3, avaliacoes=10)))
        self.assertEqual(app.preenche("x{elogio}", lead(nota=3.9, avaliacoes=10)), "x")

    def test_sem_variavel_sobrando(self):
        for seg, camp in app.config["campanhas"].items():
            for v in camp["variantes"]:
                self.assertNotIn("{", app.preenche(v, lead()), f"{seg}: {v}")

    def test_rodizio_nao_repete_seguido(self):
        seq = [app.escolhe_variante("t", ["a", "b", "c"]) for _ in range(40)]
        self.assertFalse(any(a == b for a, b in zip(seq, seq[1:])))


class Segmentos(unittest.TestCase):
    def setUp(self):
        reinicia()

    def test_segmentos_por_situacao(self):
        self.assertEqual(app.segmento_de(lead()), "sem_presenca")
        self.assertEqual(app.segmento_de(lead(site="https://instagram.com/x")), "so_instagram")
        self.assertEqual(app.segmento_de(lead(site="https://x.com.br")), "site_sem_instagram")
        self.assertEqual(app.segmento_de(lead(site="https://x.com.br", instagram="https://instagram.com/x")), "site_e_instagram")

    def test_segmento_desligado_cai_no_proximo(self):
        ruim = lead(nota=3.2, avaliacoes=30)
        self.assertEqual(app.segmento_de(ruim), "sem_presenca")  # "reputacao" vem desligado
        app.config["campanhas"]["reputacao"]["ativo"] = True
        self.assertEqual(app.segmento_de(ruim), "reputacao")
        app.config["campanhas"]["sem_presenca"]["ativo"] = False
        self.assertIsNone(app.segmento_de(lead()))

    def test_elegiveis_exclui_optout_e_conversa(self):
        app.leads.update({"a": lead(id="a"), "b": lead(id="b", optout=True), "c": lead(id="c", status="contatado")})
        app.conversas["5513900000000"] = {"numero": "5513900000000", "lead_id": "a", "msgs": []}
        self.assertEqual(app.elegiveis(), [])


class Followup(unittest.TestCase):
    def setUp(self):
        reinicia()
        app.leads["a"] = lead(id="a", status="contatado")
        self.c = app.conversas["5513988887777"] = {"numero": "5513988887777", "lead_id": "a", "followups": 0,
                                                    "msgs": [{"t": time.time() - 3 * 86400, "de": "auto", "txt": "oi"}]}

    def test_vence_no_prazo(self):
        _, l, k = app.proximo_followup()
        self.assertEqual((l["id"], k), ("a", 0))

    def test_nao_antes_do_prazo(self):
        self.c["msgs"][0]["t"] = time.time() - 3600
        self.assertIsNone(app.proximo_followup())

    def test_para_quando_responde(self):
        self.c["msgs"].append({"t": time.time(), "de": "lead", "txt": "oi"})
        self.assertIsNone(app.proximo_followup())

    def test_para_depois_do_ultimo(self):
        self.c["followups"] = len(app.config["followup"]["dias"])
        self.assertIsNone(app.proximo_followup())


class Agenda(unittest.TestCase):
    def setUp(self):
        reinicia()
        app.config["agenda"].update(dias=[0, 1, 2, 3, 4, 5, 6], inicio="09:00", fim="12:00", duracao=30, antecedencia_h=0)
        self.dia = (datetime.now(app.BR) + timedelta(days=2)).date()
        app.leads["a"] = lead(id="a")

    def test_reserva_tira_horario_e_marca_funil(self):
        slots = app.slots_do_dia(self.dia)
        self.assertEqual(len(slots), 6)
        app.reservar(app.leads["a"], slots[0])
        self.assertNotIn(slots[0], app.slots_do_dia(self.dia))
        self.assertEqual(app.leads["a"]["status"], "reuniao")

    def test_conflito_e_horario_invalido(self):
        s = app.slots_do_dia(self.dia)[0]
        app.reservar(app.leads["a"], s)
        with self.assertRaises(ValueError):
            app.reservar(app.leads["a"], s)
        with self.assertRaises(ValueError):
            app.reservar(app.leads["a"], "amanhã cedo")


class WhatsAppEventos(unittest.TestCase):
    def setUp(self):
        reinicia()
        app.leads["a"] = lead(id="a", status="contatado")

    def ev(self, de, texto, from_me=False, mid="m1"):
        app.wa_evento({"event": "message.any", "payload": {"id": mid, "from": de, "to": "551300000000@c.us",
                                                         "fromMe": from_me, "body": texto, "timestamp": time.time()}})

    def test_numero_fora_do_crm_e_grupo_sao_ignorados(self):
        self.ev("5511912345678@c.us", "oi pessoal")
        self.ev("1203630@g.us", "grupo")
        self.assertEqual(app.conversas, {})

    def test_resposta_do_lead_move_funil(self):
        self.ev("5513988887777@c.us", "Oi, quanto custa?")
        self.assertEqual(app.leads["a"]["status"], "respondeu")
        self.assertEqual(app.conversas["5513988887777"]["nao_lidas"], 1)

    def test_pedido_para_parar_descarta(self):
        self.ev("5513988887777@c.us", "não tenho interesse")
        self.assertTrue(app.leads["a"]["optout"])
        self.assertEqual(app.leads["a"]["status"], "descartado")

    def test_mensagem_duplicada_nao_conta_duas_vezes(self):
        self.ev("5513988887777@c.us", "oi")
        self.ev("5513988887777@c.us", "oi")
        self.assertEqual(len(app.conversas["5513988887777"]["msgs"]), 1)


class Login(unittest.TestCase):
    def test_senha(self):
        app.define_senha("segredo123")
        self.assertTrue(app.confere_senha("segredo123"))
        self.assertFalse(app.confere_senha("outra"))


class Http(unittest.TestCase):
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

    def test_api_exige_login(self):
        self.assertEqual(self.req("/api/leads")[0], 401)
        self.assertEqual(self.req("/api/leads", token="errado")[0], 401)

    def test_token_local_libera(self):
        st, campanhas = self.req("/api/campanhas", token=app.API_TOKEN)
        self.assertEqual(st, 200)
        self.assertEqual([s["id"] for s in campanhas["segmentos"]], list(app.SEGMENTOS))

    def test_webhook_exige_token_do_whatsapp(self):
        self.assertEqual(self.req("/api/wa/evento", metodo="POST", corpo={})[0], 401)

    def test_estatico_serve_css_js_e_bloqueia_fuga(self):
        for caminho in ("/static/app.css", "/static/js/base.js"):
            with urllib.request.urlopen(self.base + caminho, timeout=10) as r:
                self.assertEqual(r.status, 200)
        for caminho in ("/static/../server.py", "/static/..%2Fdados%2Fapi_token", "/static/js/nao-existe.js"):
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(self.base + caminho, timeout=10)
            self.assertEqual(e.exception.code, 404, caminho)

    def test_envio_so_para_lead_do_crm(self):
        st, r = self.req("/api/wa/enviar", token=app.API_TOKEN, metodo="POST", corpo={"numero": "5511999999999", "texto": "oi"})
        self.assertEqual(st, 400)


class Seguranca(unittest.TestCase):
    """Regressões da revisão de segurança de 24/10/2026 (relatório privado fora do repositório)."""

    def setUp(self):
        reinicia()
        app.leads.update({"a": lead(id="a"), "b": lead(id="b", whatsapp="5513977776666", tel_digitos="5513977776666")})

    def test_nao_envia_para_numero_de_outro_lead(self):
        with self.assertRaises(ValueError):
            app.wa_enviar(app.leads["a"], "oi", numero="5513977776666")

    def test_optout_vale_pelo_numero_mesmo_em_lead_duplicado(self):
        app.leads["dup"] = lead(id="dup", optout=True)  # mesmo telefone do lead "a"
        with self.assertRaises(ValueError):
            app.wa_enviar(app.leads["a"], "oi")

    def test_numero_estrangeiro_nao_vira_ddd(self):
        app.leads["ddd79"] = lead(id="ddd79", whatsapp="5579991234567", tel_digitos="5579991234567")
        self.assertEqual(app.chave_num("79991234567", internacional=True), "")  # +7 999… (Rússia)
        self.assertIsNone(app.lead_por_numero("79991234567", internacional=True))
        self.assertEqual(app.lead_por_numero("5579991234567", internacional=True)["id"], "ddd79")

    def test_ia_reserva_no_maximo_um_horario_futuro(self):
        app.config["agenda"].update(dias=list(range(7)), inicio="09:00", fim="12:00", duracao=30, antecedencia_h=0)
        dia = (datetime.now(app.BR) + timedelta(days=2)).date()
        s1, s2 = app.slots_do_dia(dia)[:2]
        app.reservar(app.leads["a"], s1, "ia")
        with self.assertRaises(ValueError):
            app.reservar(app.leads["a"], s2, "ia")
        app.reservar(app.leads["a"], s2, "manual")  # você ainda pode marcar à mão

    def test_anotacao_privada_nao_vai_para_a_ia(self):
        self.assertNotIn("segredo interno", agente.contexto_lead(lead(obs="segredo interno")))

    def test_teto_diario_de_respostas_da_ia(self):
        app.conversas["5513988887777"] = {"numero": "5513988887777", "lead_id": "a", "ia": True, "msgs": [{"t": 1, "de": "lead", "txt": "oi"}],
                                          "ia_dia": datetime.now(app.BR).strftime("%Y-%m-%d"), "ia_n": agente.LIMITE_IA_DIA}
        original, agente.ia_decide = agente.ia_decide, lambda *a: self.fail("não devia chamar a IA")
        try:
            agente.ia_responder("5513988887777")
        finally:
            agente.ia_decide = original
        self.assertFalse(app.conversas["5513988887777"]["ia"])

    def test_enriquecimento_so_em_endereco_publico(self):
        for url in ("http://127.0.0.1/", "localhost:3000", "http://10.0.0.5", "http://192.168.0.1", "file:///c:/x",
                    "http://8.8.8.8:3000/", "http://169.254.169.254/latest"):
            self.assertFalse(buscas.url_publica(url), url)
        self.assertTrue(buscas.url_publica("http://8.8.8.8/"))


class SegurancaHttp(Http):
    def bruto(self, caminho, metodo="GET", corpo=b"", **h):
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.srv.server_address[1], timeout=10)
        c.putrequest(metodo, caminho, skip_host=True)
        for k, v in h.items():
            c.putheader(k.replace("_", "-"), v)
        c.putheader("Content-Length", str(len(corpo)))
        c.endheaders(corpo)
        r = c.getresponse()
        return r.status, r.getheader("X-Frame-Options")

    def test_host_estranho_bloqueado_dns_rebinding(self):
        self.assertEqual(self.bruto("/", Host="evil.example:8090")[0], 403)
        self.assertEqual(self.bruto("/", Host="localhost:8090")[0], 200)

    def test_post_do_navegador_exige_origem_e_json(self):
        porta = self.srv.server_address[1]
        host = f"127.0.0.1:{porta}"
        corpo = b'{"senha":"x"}'
        # outra porta do localhost (n8n, motor…) não pode postar
        self.assertEqual(self.bruto("/api/auth/entrar", "POST", corpo, Host=host, Origin="http://127.0.0.1:5678",
                                    Content_Type="application/json")[0], 403)
        # form/text-plain sem preflight
        self.assertEqual(self.bruto("/api/auth/entrar", "POST", corpo, Host=host, Origin=f"http://{host}",
                                    Content_Type="text/plain")[0], 403)
        # sem Origin
        self.assertEqual(self.bruto("/api/auth/entrar", "POST", corpo, Host=host, Content_Type="application/json")[0], 403)

    def test_corpo_grande_recusado(self):
        self.assertEqual(self.bruto("/api/auth/entrar", "POST", b"x" * 1_000_001, Host=f"127.0.0.1:{self.srv.server_address[1]}")[0], 413)

    def test_cabecalhos_de_seguranca(self):
        self.assertEqual(self.bruto("/", Host="localhost")[1], "DENY")

    def test_senha_so_criada_pelo_nome_local_e_login_bloqueia(self):
        porta = self.srv.server_address[1]
        ts = "meu-pc.tail1234.ts.net"
        st, _ = self.bruto("/api/auth/criar", "POST", b'{"senha":"abcdef"}', Host=ts, Origin=f"https://{ts}",
                           Content_Type="application/json")
        self.assertEqual(st, 403)
        app.define_senha("certa123")
        original, rotas_auth.time.sleep = rotas_auth.time.sleep, lambda s: None
        try:
            for _ in range(10):
                self.bruto("/api/auth/entrar", "POST", b'{"senha":"errada"}', Host=f"localhost:{porta}",
                           Origin=f"http://localhost:{porta}", Content_Type="application/json")
            st, _ = self.bruto("/api/auth/entrar", "POST", b'{"senha":"certa123"}', Host=f"localhost:{porta}",
                               Origin=f"http://localhost:{porta}", Content_Type="application/json")
            self.assertEqual(st, 429)
        finally:
            rotas_auth.time.sleep = original
            seguranca_http._falhas_login.clear()


if __name__ == "__main__":
    unittest.main()
