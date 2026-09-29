import json
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from laboratorio.models import RegistroCoating, RegraTurnoCoating, TratamentoAntiReflexo, TurnoCoating
from maquinas.models import CategoriaMaquina, Maquina
from organization.models import Setor


class CoatingValidacaoHorariosTests(TestCase):
    """Lançamentos que configurariam motivo de auditoria devem ser bloqueados no ato."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="coating.op", password="x", is_staff=True)
        self.client.force_login(self.user)
        regra = RegraTurnoCoating.objects.create(nome="Turno 01", hora_inicio=time(0, 0), hora_fim=time(23, 59))
        self.turno = TurnoCoating.objects.create(data=timezone.localdate(), regra=regra)
        maquina = Maquina.objects.create(
            codigo="DLX1200",
            categoria=CategoriaMaquina.objects.create(nome="Evaporadora"),
            setor=Setor.objects.create(nome="Coating"),
        )
        self.registro = RegistroCoating.objects.create(
            turno_coating=self.turno,
            maquina=maquina,
            lote=13859,
            tratamento=TratamentoAntiReflexo.objects.create(nome="BLUE CUT"),
            lado="CC",
        )
        self.entrada = timezone.localtime() - timedelta(hours=3)

    def _fmt(self, dt):
        return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")

    def _editar(self, entrada, saida, **extra):
        payload = {"id": self.registro.id, "hora_entrada": entrada, "hora_saida": saida, **extra}
        return self.client.post(
            reverse("laboratorio:api_editar_linha_coating"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def _codigos(self, response):
        return [a["codigo"] for a in response.json()["anomalias"]]

    def test_saida_valida_e_salva(self):
        response = self._editar(self._fmt(self.entrada), self._fmt(self.entrada + timedelta(minutes=50)))
        self.assertEqual(response.status_code, 200)
        self.registro.refresh_from_db()
        self.assertIsNotNone(self.registro.hora_saida)

    def test_saida_anterior_a_entrada_bloqueia(self):
        response = self._editar(self._fmt(self.entrada), self._fmt(self.entrada - timedelta(minutes=31)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._codigos(response), ["negative"])
        self.registro.refresh_from_db()
        self.assertIsNone(self.registro.hora_saida)

    def test_saida_igual_a_entrada_bloqueia(self):
        response = self._editar(self._fmt(self.entrada), self._fmt(self.entrada))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._codigos(response), ["negative"])

    def test_duracao_acima_de_24h_bloqueia(self):
        entrada = self.entrada - timedelta(days=2)
        response = self._editar(self._fmt(entrada), self._fmt(entrada + timedelta(hours=25)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._codigos(response), ["over_24h"])

    def test_saida_sem_entrada_bloqueia(self):
        response = self._editar("", self._fmt(self.entrada))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._codigos(response), ["missing"])

    def test_entrada_antiga_sem_saida_bloqueia(self):
        response = self._editar(self._fmt(self.entrada - timedelta(hours=30)), "")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._codigos(response), ["missing"])

    def test_lote_em_andamento_sem_saida_e_permitido(self):
        response = self._editar(self._fmt(self.entrada), "")
        self.assertEqual(response.status_code, 200)

    def test_saida_no_futuro_bloqueia(self):
        response = self._editar(self._fmt(self.entrada), self._fmt(timezone.now() + timedelta(hours=2)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._codigos(response), ["future"])

    def test_bloqueio_nao_altera_dados_do_lote(self):
        response = self._editar(
            self._fmt(self.entrada), self._fmt(self.entrada - timedelta(hours=1)), lote=99999
        )
        self.assertEqual(response.status_code, 400)
        self.registro.refresh_from_db()
        self.assertEqual(self.registro.lote, 13859)

    def test_edicao_rapida_tambem_valida(self):
        entrada = self.entrada - timedelta(days=2)
        self.registro.hora_entrada = entrada
        self.registro.save()
        response = self.client.post(
            reverse("laboratorio:atualizar_celula_coating"),
            data=json.dumps({"id": self.registro.id, "campo": "hora_saida",
                             "valor": self._fmt(entrada + timedelta(hours=26))}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._codigos(response), ["over_24h"])
