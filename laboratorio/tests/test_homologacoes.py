import os
import tempfile
from datetime import date

import openpyxl
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from laboratorio.models import ETAPAS_HOMOLOGACAO, PlanoHomologacao, TratamentoAntiReflexo
from maquinas.models import Maquina


class HomologacoesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser("adm_homol", "a@a.com", "x")
        self.client.force_login(self.user)
        self.trat = TratamentoAntiReflexo.objects.create(nome="CRIZAL TESTE")
        self.maq = Maquina.objects.create(codigo="MC-T1")

    def _criar_plano(self):
        resp = self.client.post(
            reverse("laboratorio:homologacao_plano_create"),
            {"tratamento": self.trat.pk, "maquina": self.maq.pk, "data_plano": "2025-03-28"},
        )
        plano = PlanoHomologacao.objects.get()
        self.assertRedirects(resp, reverse("laboratorio:homologacao_plano_detail", args=[plano.pk]))
        return plano

    def test_criar_plano_gera_17_etapas_nao_iniciado(self):
        plano = self._criar_plano()
        self.assertEqual(plano.etapas.count(), len(ETAPAS_HOMOLOGACAO))
        self.assertEqual(plano.status, PlanoHomologacao.STATUS_NAO_INICIADO)
        self.assertEqual(plano.etapa_atual.ordem, 1)

    def test_atualizar_etapas_e_resultado(self):
        plano = self._criar_plano()
        dados = {f"data_{e.pk}": "2025-10-01" for e in plano.etapas.all()[:3]}
        resp = self.client.post(reverse("laboratorio:homologacao_plano_detail", args=[plano.pk]), dados)
        self.assertEqual(resp.status_code, 302)
        plano = PlanoHomologacao.objects.get(pk=plano.pk)
        self.assertEqual(plano.status, PlanoHomologacao.STATUS_EM_ANDAMENTO)
        self.assertEqual(plano.etapa_atual.ordem, 4)

        dados = {f"data_{e.pk}": "2025-10-01" for e in plano.etapas.all()}
        dados["resultado"] = "APROVADO"
        self.client.post(reverse("laboratorio:homologacao_plano_detail", args=[plano.pk]), dados)
        plano = PlanoHomologacao.objects.get(pk=plano.pk)
        self.assertEqual(plano.status, PlanoHomologacao.RESULTADO_APROVADO)
        self.assertEqual(plano.progresso_pct, 100)

    def test_telas_renderizam_e_excluir(self):
        plano = self._criar_plano()
        resp = self.client.get(reverse("laboratorio:homologacoes_resumo"))
        self.assertContains(resp, "CRIZAL TESTE")
        self.assertContains(resp, "MC-T1")
        self.assertEqual(self.client.get(reverse("laboratorio:homologacao_plano_detail", args=[plano.pk])).status_code, 200)
        self.client.post(reverse("laboratorio:homologacao_plano_delete", args=[plano.pk]))
        self.assertFalse(PlanoHomologacao.objects.exists())

    def test_importar_planilha(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Dados"
        ws.append([None] * 8)
        for _ in range(8):
            ws.append([None] * 8)
        for i, nome in enumerate(ETAPAS_HOMOLOGACAO, start=1):
            ultimo = i == len(ETAPAS_HOMOLOGACAO)
            ws.append([i, date(2025, 3, 28), "CRIZAL TESTE", "MC-T1", f"{i:02d} - {nome}", date(2025, 10, 1),
                       "Aprovado" if ultimo else None, "ok" if i == 1 else None])
        with tempfile.TemporaryDirectory() as tmp:
            caminho = os.path.join(tmp, "plano.xlsx")
            wb.save(caminho)
            call_command("importar_homologacoes", caminho, verbosity=0)
            call_command("importar_homologacoes", caminho, verbosity=0)  # idempotente
        plano = PlanoHomologacao.objects.get()
        self.assertEqual(plano.status, PlanoHomologacao.RESULTADO_APROVADO)
        self.assertEqual(plano.etapas.count(), len(ETAPAS_HOMOLOGACAO))
        self.assertEqual(plano.observacoes, "ok")
