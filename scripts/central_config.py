"""Localização do scraper adicional; o motor original do Prospecta continua separado."""
import os


def comando_motor(raiz):
    """Motor original (busca avançada). A saída por inatividade padrão é 1 min: quando a 1ª página
    do Google demora mais que isso, o motor sai antes de abrir as fichas e a busca vem vazia."""
    return [os.path.join(raiz, 'engine', 'google-maps-scraper.exe'), '-web', '-addr', '127.0.0.1:8080',
            '-data-folder', os.path.join(raiz, 'engine', 'gmapsdata'), '-exit-on-inactivity', '5m']


def caminhos_scraper(raiz):
    configured = os.environ.get('SITH_SCRAPER_EXE')
    folder = os.path.abspath(os.path.join(raiz, os.pardir, os.pardir, 'mazyos-scraper'))
    candidatos = [os.path.abspath(configured)] if configured else [
        os.path.join(folder, 'sithia-scraper.exe'),
        os.path.join(raiz, 'engine', 'sithia-scraper.exe'),
    ]
    for exe in candidatos:
        if os.path.isfile(exe):
            data = os.environ.get('SITH_SCRAPER_DATA') or os.path.join(os.path.dirname(exe), 'webdata')
            return exe, os.path.abspath(data)
    return None
