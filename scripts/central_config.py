"""Localização do scraper adicional; o motor original do Prospecta continua separado."""
import os


def comando_motor(raiz):
    """Motor da busca avançada (8080), com a pasta de dados de sempre. O google-maps-scraper.exe
    original encerra a busca no 1º ciclo do monitor de inatividade (1 min) quando a 1ª página do
    Google demora: termina "ok" com 0 empresas, e o modo web ignora -exit-on-inactivity. O
    sithia-scraper.exe tem essa correção (mesma API), então o motor usa ele quando existe."""
    scraper = caminhos_scraper(raiz)
    exe = scraper[0] if scraper else os.path.join(raiz, 'engine', 'google-maps-scraper.exe')
    return [exe, '-web', '-addr', '127.0.0.1:8080', '-data-folder', os.path.join(raiz, 'engine', 'gmapsdata')]


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
