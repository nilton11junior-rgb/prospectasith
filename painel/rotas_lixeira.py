"""Rotas HTTP da lixeira de buscas. O handler (server.H) chama atender() antes das demais; True = tratou."""
import re, urllib.parse
import lixeira


def atender(h, metodo, path):
    if path == "/api/buscas" and metodo == "GET":
        h._envia(200, lixeira.ativas())
        return True
    if path == "/api/lixeira" and metodo == "GET":
        h._envia(200, lixeira.lista())
        return True
    if path == "/api/lixeira/esvaziar" and metodo == "POST":
        h._envia(200, {"apagadas": lixeira.esvaziar()})
        return True
    m = re.fullmatch(r"/api/buscas/([\w-]+)/(lixeira|restaurar)", path)
    if m and metodo == "POST":
        try:
            if m.group(2) == "lixeira":
                lixeira.mandar(m.group(1), (h._corpo() or {}).get("motivo", ""))
            else:
                lixeira.restaurar(m.group(1))
        except KeyError:
            h._envia(404, {"erro": "não encontrado"})
        except ValueError as e:
            h._envia(409, {"erro": str(e)})
        else:
            h._envia(200, {"ok": True})
        return True
    m = re.fullmatch(r"/api/buscas/([\w-]+)", path)
    if m and metodo == "DELETE":
        apagar_tudo = urllib.parse.parse_qs(urllib.parse.urlparse(h.path).query).get("leads") == ["apagar"]
        try:
            lixeira.excluir(m.group(1), manter_trabalhados=not apagar_tudo)
        except KeyError:
            h._envia(404, {"erro": "não encontrado"})
        except ValueError as e:
            h._envia(409, {"erro": str(e)})
        else:
            h._envia(200, {"ok": True})
        return True
    return False
