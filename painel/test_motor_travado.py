"""Motor do Google Maps preso em "working": a fila trava e as buscas novas nunca começam.
O painel tem de perceber, destravar o que for registro velho dele e avisar com clareza quando não der."""
import io, json, re, unittest, urllib.error
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from testes_comum import reinicia
import buscas


def job(jid, status, horas_atras=0.0, nome="painel:abc", max_time_s=900):
    quando = datetime.now(timezone.utc) - timedelta(hours=horas_atras)
    return {"ID": jid, "Name": nome, "Status": status, "Date": quando.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Data": {"max_time": max_time_s * 1_000_000_000}}


def erro_http(codigo, texto):
    return urllib.error.HTTPError("http://motor", codigo, texto, {}, io.BytesIO(texto.encode()))


class MotorFalso:
    """Imita a API do gosom: lista, cria, consulta, baixa CSV e apaga jobs."""

    def __init__(self, jobs=(), delete_falha=False, status_novo="pending", csv=None):
        self.jobs = {j["ID"]: j for j in jobs}
        self.delete_falha, self.status_novo, self.csv = delete_falha, status_novo, csv or {}
        self.chamadas = []

    def req(self, metodo, caminho, corpo=None):
        self.chamadas.append((metodo, caminho))
        if caminho == "/api/v1/jobs":
            if metodo == "POST":
                self.jobs["novo"] = job("novo", self.status_novo)
                return 201, json.dumps({"id": "novo"}).encode()
            return 200, json.dumps(list(self.jobs.values())).encode()
        jid, download = re.match(r"/api/v1/jobs/([^/]+)(/download)?$", caminho).groups()
        if metodo == "DELETE":
            if self.delete_falha:
                raise erro_http(500, "file in use")
            self.jobs.pop(jid, None)
            return 200, b""
        if download:
            if jid not in self.csv:
                raise erro_http(404, f"csv file not found for job {jid}")
            return 200, self.csv[jid].encode()
        return 200, json.dumps(self.jobs[jid]).encode()


def nova_busca():
    return {"id": "b1", "cancelar": False, "jobs_motor": [], "avisos": []}


CORPO = {"keywords": ["academias em Santos - SP"], "max_time": 600}


class MotorTravado(unittest.TestCase):
    def setUp(self):
        reinicia()

    def test_registro_velho_do_painel_e_apagado_antes_da_busca(self):
        motor = MotorFalso([job("velho", "working", horas_atras=14)])
        with patch.object(buscas, "kit", motor):
            buscas.liberar_fila()
        self.assertIn(("DELETE", "/api/v1/jobs/velho"), motor.chamadas)
        self.assertNotIn("velho", motor.jobs)

    def test_motor_preso_que_recusa_apagar_gera_aviso_claro(self):
        motor = MotorFalso([job("velho", "working", horas_atras=14)], delete_falha=True)
        with patch.object(buscas, "kit", motor), self.assertRaisesRegex(RuntimeError, "travou.*google-maps-scraper.exe"):
            buscas.rodar_job(nova_busca(), dict(CORPO), "Buscando")
        self.assertNotIn(("POST", "/api/v1/jobs"), motor.chamadas)  # não enfileira atrás do job preso

    def test_job_travado_de_fora_do_painel_nao_e_apagado(self):
        motor = MotorFalso([job("cli", "working", horas_atras=14, nome="minha-busca")])
        with patch.object(buscas, "kit", motor), self.assertRaisesRegex(RuntimeError, "travou"):
            buscas.liberar_fila()
        self.assertFalse([c for c in motor.chamadas if c[0] == "DELETE"])

    def test_job_trabalhando_dentro_do_prazo_nao_e_mexido(self):
        motor = MotorFalso([job("atual", "working", horas_atras=0.05)])
        with patch.object(buscas, "kit", motor):
            buscas.liberar_fila()
        self.assertIn("atual", motor.jobs)

    def test_busca_parada_na_fila_explica_em_vez_de_404(self):
        motor = MotorFalso()
        with patch.object(buscas, "kit", motor), patch.object(buscas, "PENDENTE_MAX", 0), \
             patch.object(buscas, "CHECAGEM_FILA", 0), patch.object(buscas.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "não começou a busca"):
                buscas.rodar_job(nova_busca(), dict(CORPO), "Buscando")

    def test_csv_ainda_nao_criado_conta_como_vazio(self):
        motor = MotorFalso([job("j1", "working")])
        with patch.object(buscas, "kit", motor):
            self.assertEqual(buscas._baixar("j1"), [])

    def test_job_concluido_vazio_nao_e_reaproveitado(self):
        # "Rodar de novo" depois de uma busca vazia seguia o mesmo job e terminava na hora com 0 empresas.
        motor = MotorFalso([job("vazio", "ok")], csv={"vazio": ""})
        with patch.object(buscas, "kit", motor):
            self.assertFalse(buscas.job_reaproveitavel("vazio"))

    def test_job_concluido_com_resultado_e_reaproveitado(self):
        motor = MotorFalso([job("cheio", "ok")], csv={"cheio": "title\nAcademia Mar\n"})
        with patch.object(buscas, "kit", motor):
            self.assertTrue(buscas.job_reaproveitavel("cheio"))

    def test_busca_normal_continua_funcionando(self):
        motor = MotorFalso(status_novo="ok", csv={"novo": "title,phone\nAcademia Mar,1332221111\n"})
        with patch.object(buscas, "kit", motor):
            linhas = buscas.rodar_job(nova_busca(), dict(CORPO), "Buscando")
        self.assertEqual(linhas[0]["title"], "Academia Mar")


if __name__ == "__main__":
    unittest.main()
