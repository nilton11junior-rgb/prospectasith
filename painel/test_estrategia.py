"""Estratégia de vendas nas mensagens (docs/estrategia-vendas.md): primeiro contato com pergunta, sem pitch, sem link
e sem preço; follow-up em 1/3/6 dias com algo novo; IA com SPIN e "Sim ou Sim"; migração que guarda os textos antigos."""
import json, os, unittest
from testes_comum import TMP, app, campanhas, lead, reinicia
import roteiros

LEADS_DE_TESTE = [lead(nota=4.9, avaliacoes=50), lead(nota=4.3, avaliacoes=10), lead(nota=3.5, avaliacoes=30),
                  lead(nome="M.E.R CLIMATIZACAO E INSTALACAO DE AR CONDICIONADO", categoria="Prestador de serviços de climatização")]
PROIBIDO_NA_1A_MENSAGEM = ("http", "www.", "r$", "faço", "faco", "preço", "preco", "orçamento", "proposta", "oferta")


class PrimeiroContato(unittest.TestCase):
    def setUp(self):
        reinicia()

    def test_cada_segmento_tem_tres_variacoes(self):
        for sid, camp in roteiros.CAMPANHAS_PADRAO.items():
            self.assertGreaterEqual(len(camp["variantes"]), 3, sid)

    def test_so_pergunta_curta_sem_pitch_link_ou_preco(self):
        for sid, camp in roteiros.CAMPANHAS_PADRAO.items():
            for v in camp["variantes"]:
                for l in LEADS_DE_TESTE:
                    texto = campanhas.preenche(v, l)
                    baixo = texto.lower()
                    self.assertNotIn("{", texto, f"{sid}: variável sobrando em {v!r}")
                    self.assertTrue(texto.rstrip(" 🙂").endswith("?"), f"{sid}: não termina em pergunta: {texto!r}")
                    self.assertLessEqual(len(texto), 300, f"{sid}: longa demais: {texto!r}")
                    for palavra in PROIBIDO_NA_1A_MENSAGEM:
                        self.assertNotIn(palavra, baixo, f"{sid}: '{palavra}' em {texto!r}")

    def test_gancho_so_elogia_o_que_e_verdade(self):
        self.assertIn("ótimas avaliações no Google", campanhas.preenche("{gancho}", lead(nota=4.9, avaliacoes=50)))
        self.assertIn("boas avaliações no Google", campanhas.preenche("{gancho}", lead(nota=4.3, avaliacoes=10)))
        neutro = campanhas.preenche("{gancho}", lead(nota=3.5, avaliacoes=30))
        self.assertNotIn("avaliações", neutro)
        self.assertIn("Clínica Sorriso", neutro)

    def test_artigo_concorda_com_o_nome(self):
        # "Vi que a Consultório Dr. Wesley" e "o Instagram da Hospital Veterinário" pegam mal com o lead.
        casos = {"Consultório Odontológico Dr. Wesley Affonso": ("o ", "do "), "Hospital Veterinário Casa do Criador": ("o ", "do "),
                 "Espaço Pet": ("o ", "do "), "Instituto Malu Marconatto": ("o ", "do "), "Dr. Robert Ficker": ("o ", "do "),
                 "Clínica Sorriso": ("a ", "da "), "Dra. Sylvia Tiossi": ("a ", "da "), "Odonto Renew": ("a ", "da ")}
        for nome, (art, contr) in casos.items():
            l = lead(nome=nome, nota=4.9, avaliacoes=50)
            self.assertIn(f"Vi que {art}{nome}", campanhas.preenche("{gancho}", l))
            self.assertIn(f"Instagram {contr}{nome},", campanhas.preenche("Vi o Instagram da {nome}, legal?", l))
            self.assertIn(f"Achei {art}{nome} pelo", campanhas.preenche("Achei a {nome} pelo Google?", l))

    def test_segmentos_tem_banco_de_perguntas_spin(self):
        for sid, camp in roteiros.CAMPANHAS_PADRAO.items():
            for letra in ("S —", "P —", "I —", "N —"):
                self.assertIn(letra, camp["estrategia"], f"{sid} sem {letra}")


class FollowUp(unittest.TestCase):
    def test_sequencia_dia_2_4_7(self):
        fu = roteiros.FOLLOWUP_PADRAO
        self.assertEqual(fu["dias"], [1, 3, 6])      # dias depois da 1ª mensagem (dia 1) = dias 2, 4 e 7
        self.assertEqual(len(fu["variantes"]), 3)
        for grupo in fu["variantes"]:
            self.assertGreaterEqual(len(grupo), 2)
            for v in grupo:
                self.assertNotIn("e aí", v.lower())
                self.assertNotIn("e ai", v.lower())
                self.assertNotIn("http", v.lower())


class PromptDaIA(unittest.TestCase):
    def test_regras_do_metodo(self):
        p = roteiros.SISTEMA_IA
        for trecho in ("SPIN", "Sim ou Sim", "pergunta, comentário, pergunta", "Nunca fale de preço", "Nunca pergunte \"quer comprar"):
            self.assertIn(trecho, p)
        self.assertIn('"acao"', p)  # formato JSON de resposta preservado


class Migracao(unittest.TestCase):
    ANTIGO = {"campanhas": {"sem_presenca": {"ativo": False, "estrategia": "estratégia antiga", "variantes": ["texto antigo?"]}},
              "followup": {"ativo": True, "dias": [2, 5], "variantes": [["fu antigo"], ["fu antigo 2"]]}}

    def carrega(self, cfg):
        reinicia()
        with open(os.path.join(TMP, "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        app.config.clear()
        app.carregar()

    def test_troca_textos_guarda_os_antigos_e_preserva_ligado(self):
        self.carrega(self.ANTIGO)
        c = app.config
        self.assertEqual(c["roteiros_versao"], roteiros.ROTEIROS_VERSAO)
        self.assertEqual(c["campanhas"]["sem_presenca"]["variantes"], roteiros.CAMPANHAS_PADRAO["sem_presenca"]["variantes"])
        self.assertFalse(c["campanhas"]["sem_presenca"]["ativo"])                    # o que você ligou/desligou continua
        self.assertEqual(c["followup"]["dias"], [1, 3, 6])
        antes = c["roteiros_anteriores"]
        self.assertEqual(antes["campanhas"]["sem_presenca"]["variantes"], ["texto antigo?"])
        self.assertEqual(antes["followup"]["dias"], [2, 5])

    def test_nao_repete_a_migracao_e_respeita_edicao_depois(self):
        self.carrega(self.ANTIGO)
        app.config["campanhas"]["sem_presenca"]["variantes"] = ["meu texto?"]
        app.salvar_config()
        app.config.clear()
        app.carregar()
        self.assertEqual(app.config["campanhas"]["sem_presenca"]["variantes"], ["meu texto?"])


if __name__ == "__main__":
    unittest.main()
