from django.test import TestCase
from datetime import date

from .models import Instrumento, HistoricoCalibracao


class HistoricoCalibracaoLogicTests(TestCase):
	def setUp(self):
		self.inst = Instrumento.objects.create(tag='TST-001', descricao='Instrumento Teste')

	def test_result_aprovado_when_eme_leq_ema(self):
		# erro + incerteza = 2, tolerancia -> ema = tol/2 = 2 -> APROVADO
		hist = HistoricoCalibracao(instrumento=self.inst, data_calibracao=date.today(), erro_encontrado=1, incerteza=1, tolerancia_usada=4)
		hist.save()
		self.assertEqual(hist.resultado, 'APROVADO')

	def test_result_reprovado_when_eme_gt_3x_ema(self):
		# erro + incerteza = 10, tolerancia -> ema = 1 -> 10 > 3 -> REPROVADO
		hist = HistoricoCalibracao(instrumento=self.inst, data_calibracao=date.today(), erro_encontrado=9, incerteza=1, tolerancia_usada=2)
		hist.save()
		self.assertEqual(hist.resultado, 'REPROVADO')

	def test_result_condicional_when_between(self):
		# erro + incerteza = 3, ema = 2 -> between -> CONDICIONAL
		hist = HistoricoCalibracao(instrumento=self.inst, data_calibracao=date.today(), erro_encontrado=2, incerteza=1, tolerancia_usada=4)
		hist.save()
		self.assertEqual(hist.resultado, 'CONDICIONAL')


class CeleryTasksTests(TestCase):
	def test_ping_task(self):
		# call apply (synchronous execution) so this passes in regular test runner
		from .tasks import ping_task

		res = ping_task.apply().get()
		self.assertEqual(res, 'pong')

