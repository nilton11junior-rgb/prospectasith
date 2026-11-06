"""Rotas HTTP da lixeira de buscas. O handler (server.H) chama atender() antes das demais; True = tratou."""
import re, urllib.parse
import lixeira
import exclusao_buscas


def atender(h, metodo, path):
    lead = re.fullmatch(r'/api/leads/([^/]+)', path)
    if lead and metodo == 'DELETE':
        try:
            h._envia(200, exclusao_buscas.excluir_lead(urllib.parse.unquote(lead[1])))
        except exclusao_buscas.ErroExclusao as e:
            h._envia(e.status, {'erro': str(e)})
        except OSError:
            h._envia(503, {'erro': 'Não foi possível salvar a exclusão. Verifique o disco e tente novamente.'})
        return True
    if path in ('/api/buscas/exclusao/previa', '/api/buscas/exclusao') and metodo == 'POST':
        try:
            d = h._corpo()
            if not isinstance(d, dict):
                raise exclusao_buscas.ErroExclusao(400, 'Envie uma seleção de buscas.')
            r = (exclusao_buscas.previa(d.get('ids')) if path.endswith('/previa') else
                 exclusao_buscas.excluir(d.get('ids'), d.get('confirmacao')))
            h._envia(200, r)
        except exclusao_buscas.ErroExclusao as e:
            h._envia(e.status, {'erro': str(e)})
        except OSError:
            h._envia(503, {'erro': 'Não foi possível salvar a exclusão. Verifique o disco e tente novamente.'})
        return True
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
