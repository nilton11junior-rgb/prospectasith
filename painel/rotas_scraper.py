"""Rotas da integração SITH.IA, sempre chamadas depois das barreiras do handler principal."""
import json
import re
import scraper_importacao
import scraper_motor


def atender(h, metodo, path):
    if not path.startswith('/api/scraper/'):
        return False
    try:
        if path == '/api/scraper/jobs' and metodo == 'GET':
            h._envia(200, scraper_motor.listar())
        elif path == '/api/scraper/jobs' and metodo == 'POST':
            h._envia(201, scraper_motor.criar(h._corpo()))
        else:
            match = re.fullmatch(r'/api/scraper/jobs/([^/]+)/(resultados|importar)', path)
            if match and match[2] == 'resultados' and metodo == 'GET':
                h._envia(200, scraper_importacao.resultados(match[1]))
            elif match and match[2] == 'importar' and metodo == 'POST':
                h._corpo()  # consome/valida JSON, sem aceitar dados do lead vindos do navegador
                h._envia(200, scraper_importacao.importar(match[1]))
            else:
                h._envia(404, {'erro': 'Rota do scraper não encontrada.'})
    except scraper_motor.ScraperError as error:
        h._envia(error.status, {'erro': str(error)})
    except (json.JSONDecodeError, UnicodeError):
        h._envia(400, {'erro': 'Envie os parâmetros em JSON válido.'})
    except OSError:
        h._envia(503, {'erro': 'Não foi possível salvar a importação. Verifique o espaço em disco e tente novamente.'})
    return True
