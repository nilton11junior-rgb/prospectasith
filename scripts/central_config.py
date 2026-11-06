"""Localização do scraper adicional; o motor original do Prospecta continua separado."""
import os


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
