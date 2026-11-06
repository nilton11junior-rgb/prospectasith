"""Seleção do scraper adicional sem alterar a localização do motor original."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class ConfigCentral(unittest.TestCase):
    def test_localiza_scraper_do_pacote_windows_no_clone(self):
        from central_config import caminhos_scraper

        with tempfile.TemporaryDirectory(prefix='sith-config-') as tmp, patch.dict(os.environ):
            os.environ.pop('SITH_SCRAPER_EXE', None)
            os.environ.pop('SITH_SCRAPER_DATA', None)
            engine = Path(tmp) / 'engine'
            engine.mkdir()
            exe = engine / 'sithia-scraper.exe'
            exe.write_bytes(b'fixture-nao-executavel')
            self.assertEqual(caminhos_scraper(tmp), (str(exe), str(engine / 'webdata')))

    def test_localiza_sithia_instalado_ao_lado_dos_projetos(self):
        # Importado dentro do teste para que a ausência da interface apareça como falha descritiva.
        import importlib.util
        module_path = Path(__file__).with_name('central_config.py')
        self.assertTrue(module_path.exists(), 'Falta configurar a localização do scraper SITH.IA')
        spec = importlib.util.spec_from_file_location('central_config', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='sith-config-') as tmp, patch.dict(os.environ, {}, clear=False):
            os.environ.pop('SITH_SCRAPER_EXE', None)
            os.environ.pop('SITH_SCRAPER_DATA', None)
            projetos = Path(tmp)
            crm = projetos / 'gmaps-crm' / 'kit'
            crm.mkdir(parents=True)
            scraper = projetos / 'mazyos-scraper'
            scraper.mkdir()
            exe = scraper / 'sithia-scraper.exe'
            exe.write_bytes(b'fixture-nao-executavel')
            self.assertEqual(module.caminhos_scraper(str(crm)), (str(exe), str(scraper / 'webdata')))
            self.assertFalse((crm / 'engine' / 'google-maps-scraper.exe').exists())

    def test_ausencia_do_scraper_nao_escolhe_binario_arbitrario(self):
        import importlib.util
        module_path = Path(__file__).with_name('central_config.py')
        self.assertTrue(module_path.exists(), 'Falta a configuração da central')
        spec = importlib.util.spec_from_file_location('central_config', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='sith-config-') as tmp, patch.dict(os.environ, {'SITH_SCRAPER_EXE': str(Path(tmp) / 'inexistente.exe')}):
            self.assertIsNone(module.caminhos_scraper(tmp))

    def test_motor_tolera_pagina_lenta_do_google(self):
        # Com a saída por inatividade padrão (1 min), a 1ª página do Google às vezes demora mais,
        # o motor sai antes de abrir as fichas e a busca termina "ok" com 0 empresas.
        from central_config import comando_motor
        cmd = comando_motor(r'C:\crm')
        self.assertEqual(cmd[:4], [os.path.join(r'C:\crm', 'engine', 'google-maps-scraper.exe'), '-web', '-addr', '127.0.0.1:8080'])
        self.assertEqual(cmd[cmd.index('-data-folder') + 1], os.path.join(r'C:\crm', 'engine', 'gmapsdata'))
        self.assertEqual(cmd[cmd.index('-exit-on-inactivity') + 1], '5m')


if __name__ == '__main__':
    unittest.main()
