"""Localização do scraper adicional; o motor original do Prospecta continua separado."""
import os


def caminhos_scraper(raiz):
    configured = os.environ.get('SITH_SCRAPER_EXE')
    folder = os.path.abspath(os.path.join(raiz, os.pardir, os.pardir, 'mazyos-scraper'))
    exe = os.path.abspath(configured) if configured else os.path.join(folder, 'sithia-scraper.exe')
    if not os.path.isfile(exe):
        return None
    data = os.environ.get('SITH_SCRAPER_DATA') or os.path.join(os.path.dirname(exe), 'webdata')
    return exe, os.path.abspath(data)
