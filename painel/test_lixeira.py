"""Lixeira de buscas: mandar, restaurar, excluir de vez e limpeza em 30 dias."""
import time, unittest
from testes_comum import (HttpBase, TMP, agente, agenda, app, buscas, lead, lixeira, reinicia, rotas_auth, seguranca_http, server)  # noqa: E402,F401


class Lixeira(unittest.TestCase):
    def setUp(self):
        reinicia()
        self.b = {"id": "b1", "estado": "concluida", "etapa": "Concluída", "criado_em": time.time(), "jobs_motor": [],
                  "avisos": [], "progresso": None, "parametros": {"nichos": ["barbearia"], "cidade": "Macaé", "uf": "RJ"},
                  "lead_ids": ["novo", "trab", "comum"]}
        app.buscas["b1"] = self.b
        app.leads.update({
            "novo": lead(id="novo", buscas=["b1"]),                                    # só desta busca, nunca trabalhado
            "trab": lead(id="trab", buscas=["b1"], status="contatado"),                # já trabalhado
            "comum": lead(id="comum", buscas=["b1", "b2"]),                            # também veio de outra busca
        })

    def test_manda_para_lixeira_e_tira_so_lead_nao_trabalhado_exclusivo(self):
        lixeira.mandar("b1", "nicho errado")
        self.assertIn("lixeira_em", self.b)
        self.assertEqual(self.b["lixeira_motivo"], "nicho errado")
        self.assertNotIn("novo", app.leads)
        self.assertIn("trab", app.leads)
        self.assertIn("comum", app.leads)

    def test_nao_manda_busca_rodando(self):
        self.b["estado"] = "rodando"
        with self.assertRaises(ValueError):
            lixeira.mandar("b1")

    def test_busca_na_lixeira_sai_da_lista_e_aparece_na_lixeira(self):
        lixeira.mandar("b1")
        self.assertEqual([x["id"] for x in lixeira.ativas()], [])
        self.assertEqual([x["id"] for x in lixeira.lista()], ["b1"])
        self.assertEqual(lixeira.lista()[0]["leads_guardados"], 1)

    def test_restaura_busca_e_leads(self):
        lixeira.mandar("b1")
        lixeira.restaurar("b1")
        self.assertNotIn("lixeira_em", self.b)
        self.assertIn("novo", app.leads)
        self.assertEqual([x["id"] for x in lixeira.ativas()], ["b1"])

    def test_exclusao_definitiva_so_na_lixeira(self):
        with self.assertRaises(ValueError):
            lixeira.excluir("b1")
        lixeira.mandar("b1")
        lixeira.excluir("b1")
        self.assertNotIn("b1", app.buscas)
        self.assertNotIn("novo", app.leads)
        self.assertIn("trab", app.leads)                    # trabalhado sobrevive
        self.assertEqual(app.leads["trab"]["buscas"], [])   # sem referência à busca apagada
        self.assertEqual(app.leads["comum"]["buscas"], ["b2"])

    def test_exclusao_pode_apagar_trabalhados(self):
        lixeira.mandar("b1")
        lixeira.excluir("b1", manter_trabalhados=False)
        self.assertNotIn("trab", app.leads)
        self.assertIn("comum", app.leads)                   # veio de outra busca: fica

    def test_limpeza_automatica_depois_de_30_dias(self):
        lixeira.mandar("b1")
        self.assertEqual(lixeira.limpar_vencidas(30), 0)
        self.b["lixeira_em"] = time.time() - 31 * 86400
        self.assertEqual(lixeira.limpar_vencidas(30), 1)
        self.assertNotIn("b1", app.buscas)

    def test_esvaziar(self):
        lixeira.mandar("b1")
        self.assertEqual(lixeira.esvaziar(), 1)
        self.assertEqual(lixeira.lista(), [])

    def test_lixeira_sobrevive_a_reinicio(self):
        lixeira.mandar("b1")
        app.buscas.clear(); app.leads.clear()
        app.carregar()
        self.assertIn("lixeira_em", app.buscas["b1"])
        lixeira.restaurar("b1")
        self.assertIn("novo", app.leads)


class LixeiraHttp(HttpBase):
    def setUp(self):
        reinicia()
        app.buscas["b1"] = {"id": "b1", "estado": "concluida", "etapa": "Concluída", "criado_em": time.time(), "jobs_motor": [],
                            "avisos": [], "progresso": None, "parametros": {"nichos": ["x"], "cidade": "Macaé", "uf": "RJ"},
                            "lead_ids": []}

    def j(self, caminho, metodo="GET", corpo=None):
        return self.req(caminho, token=app.API_TOKEN, metodo=metodo, corpo=corpo)

    def test_fluxo_pela_api(self):
        self.assertEqual(self.j("/api/buscas/b1/lixeira", "POST", {"motivo": "resultado ruim"})[0], 200)
        self.assertEqual(self.j("/api/buscas")[1], [])
        st, lx = self.j("/api/lixeira")
        self.assertEqual((st, lx[0]["id"], lx[0]["lixeira_motivo"]), (200, "b1", "resultado ruim"))
        self.assertEqual(self.j("/api/buscas/b1/restaurar", "POST", {})[0], 200)
        self.assertEqual(len(self.j("/api/buscas")[1]), 1)

    def test_excluir_direto_recusado_e_definitivo_na_lixeira(self):
        self.assertEqual(self.j("/api/buscas/b1", "DELETE")[0], 409)
        self.j("/api/buscas/b1/lixeira", "POST", {})
        self.assertEqual(self.j("/api/buscas/b1", "DELETE")[0], 200)
        self.assertNotIn("b1", app.buscas)

    def test_esvaziar_pela_api(self):
        self.j("/api/buscas/b1/lixeira", "POST", {})
        self.assertEqual(self.j("/api/lixeira/esvaziar", "POST", {})[1]["apagadas"], 1)


if __name__ == "__main__":
    unittest.main()


if __name__ == "__main__":
    unittest.main()
