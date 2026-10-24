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

import server as app  # noqa: E402


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

    def test_envio_so_para_lead_do_crm(self):
        st, r = self.req("/api/wa/enviar", token=app.API_TOKEN, metodo="POST", corpo={"numero": "5511999999999", "texto": "oi"})
        self.assertEqual(st, 400)


if __name__ == "__main__":
    unittest.main()
