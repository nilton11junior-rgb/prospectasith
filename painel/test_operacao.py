"""A abertura supervisionada não retoma envios automáticos sem autorização do operador."""
from unittest.mock import patch
from testes_comum import HttpBase, app, server


class OperacaoSegura(HttpBase):
    def test_modo_pausado_nao_inicia_disparo_nem_respostas_automaticas(self):
        with patch.object(server.sys, 'argv', ['server.py', '--sem-automacoes', '--sem-navegador']), \
             patch.object(server, 'carregar'), patch.object(server.threading, 'Thread') as threads, \
             patch.object(server, 'ThreadingHTTPServer', side_effect=RuntimeError('fim do teste')):
            with self.assertRaisesRegex(RuntimeError, 'fim do teste'):
                server.main()
            targets = [c.kwargs.get('target') for c in threads.call_args_list]
        self.assertIn(server.trabalhador, targets)
        self.assertNotIn(server.disparador, targets)
        self.assertNotIn(server.respondedor, targets)

    def test_abertura_normal_preserva_as_rotinas_existentes(self):
        with patch.object(server.sys, 'argv', ['server.py', '--sem-navegador']), \
             patch.object(server, 'carregar'), patch.object(server.threading, 'Thread') as threads, \
             patch.object(server, 'ThreadingHTTPServer', side_effect=RuntimeError('fim do teste')):
            with self.assertRaisesRegex(RuntimeError, 'fim do teste'):
                server.main()
            targets = [c.kwargs.get('target') for c in threads.call_args_list]
        self.assertIn(server.disparador, targets)
        self.assertIn(server.respondedor, targets)

    def test_status_informa_automacoes_pausadas_sem_mudar_configuracao(self):
        original = dict(app.config['auto_envio'])
        with patch.object(server.sys, 'argv', ['server.py', '--sem-automacoes']), patch.object(server, 'motor_ok', return_value=True):
            status, data = self.req('/api/status', app.API_TOKEN)
        self.assertEqual(status, 200)
        self.assertTrue(data.get('automacoes_pausadas'))
        self.assertEqual(app.config['auto_envio'], original)
