"""Regressões da revisão de segurança de 24/10/2026 (relatório privado fora do repositório)."""
import unittest
from datetime import datetime, timedelta
from testes_comum import (HttpBase, TMP, agente, agenda, app, buscas, lead, lixeira, reinicia, rotas_auth, seguranca_http, server)  # noqa: E402,F401


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


class SegurancaHttp(HttpBase):
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
