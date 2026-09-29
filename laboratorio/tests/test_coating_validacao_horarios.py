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


class CoatingSugestaoCorrecaoTests(TestCase):
    """Correção automática baseada nos lotes vizinhos e na duração típica da máquina."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="coating.sug", password="x", is_staff=True)
        self.client.force_login(self.user)
        self.regra = RegraTurnoCoating.objects.create(nome="Turno 01", hora_inicio=time(0, 0), hora_fim=time(23, 59))
        self.maquina = Maquina.objects.create(
            codigo="DLX1200",
            categoria=CategoriaMaquina.objects.create(nome="Evaporadora"),
            setor=Setor.objects.create(nome="Coating"),
        )
        self.tratamento = TratamentoAntiReflexo.objects.create(nome="BLUE CUT")
        self.dia = timezone.localdate() - timedelta(days=5)
        # Histórico: ciclos de 50 min em dias anteriores (define a duração típica)
        for i in range(12):
            e = self._dt(-3, 8 + i)
            self._criar(10000 + i, "CC", e, e + timedelta(minutes=50))

    def _dt(self, dias, hora, minuto=0):
        return timezone.make_aware(datetime.combine(self.dia + timedelta(days=dias), time(hora, minuto)))

    def _criar(self, lote, lado, entrada, saida):
        turno, _ = TurnoCoating.objects.get_or_create(
            data=timezone.localtime(entrada).date() if entrada else self.dia, regra=self.regra
        )
        return RegistroCoating.objects.create(
            turno_coating=turno, maquina=self.maquina, lote=lote, tratamento=self.tratamento,
            lado=lado, hora_entrada=entrada, hora_saida=saida,
        )

    def _analisar(self, registro, entrada, saida):
        response = self.client.post(
            reverse("laboratorio:api_analisar_horarios_coating"),
            data=json.dumps({"id": registro.id,
                             "hora_entrada": timezone.localtime(entrada).strftime("%Y-%m-%dT%H:%M") if entrada else "",
                             "hora_saida": timezone.localtime(saida).strftime("%Y-%m-%dT%H:%M") if saida else ""}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_hora_digitada_errada_sugere_encaixe_entre_vizinhos(self):
        # Caso da tela: entrada 02:37, saída digitada 02:06 (deveria ser 03:06)
        self._criar(13852, "CC", self._dt(0, 0, 40), self._dt(0, 1, 30))
        self._criar(13852, "CX", self._dt(0, 1, 40), self._dt(0, 2, 30))
        self._criar(13859, "CX", self._dt(0, 3, 40), self._dt(0, 4, 30))
        atual = self._criar(13859, "CC", self._dt(0, 2, 37), None)

        data = self._analisar(atual, self._dt(0, 2, 37), self._dt(0, 2, 6))

        self.assertEqual([a["codigo"] for a in data["anomalias"]], ["negative"])
        melhor = data["sugestoes"][0]
        self.assertEqual(melhor["hora_saida"], timezone.localtime(self._dt(0, 3, 6)).strftime("%Y-%m-%dT%H:%M"))
        self.assertEqual(melhor["campo"], "saida")
        self.assertEqual(melhor["confianca"], "alta")
        self.assertTrue(any("13852 CX" in m and "13859 CX" in m for m in melhor["motivos"]))
        lotes = {(v["lote"], v["lado"]) for v in data["contexto"]["vizinhos"]}
        self.assertTrue({(13852, "CC"), (13852, "CX"), (13859, "CX"), (13859, "CC")} <= lotes)

    def test_virada_de_meia_noite_sugere_apenas_trocar_a_data(self):
        self._criar(13900, "CX", self._dt(1, 1, 0), self._dt(1, 1, 50))
        atual = self._criar(13900, "CC", self._dt(0, 23, 40), None)

        data = self._analisar(atual, self._dt(0, 23, 40), self._dt(0, 0, 30))

        melhor = data["sugestoes"][0]
        self.assertEqual(melhor["hora_saida"], timezone.localtime(self._dt(1, 0, 30)).strftime("%Y-%m-%dT%H:%M"))
        self.assertIn("apenas a data", melhor["titulo"])

    def test_respeita_coluna_data_da_linha(self):
        # Caso da tela: lote 13878 CC na coluna Data 04/09 · Turno 03, entrada 04/09 00:55 e
        # saída digitada 05/09 01:40. A data errada é a da saída, não a da entrada.
        self.regra.ativo = False
        self.regra.save()
        RegraTurnoCoating.objects.create(nome="TURNO 01", hora_inicio=time(6, 0), hora_fim=time(15, 59))
        turno2 = RegraTurnoCoating.objects.create(nome="TURNO 02", hora_inicio=time(16, 0), hora_fim=time(23, 29))
        turno3 = RegraTurnoCoating.objects.create(nome="TURNO 03", hora_inicio=time(23, 30), hora_fim=time(5, 59))

        def criar(lote, lado, regra, entrada, saida):
            turno, _ = TurnoCoating.objects.get_or_create(data=timezone.localtime(entrada).date(), regra=regra)
            return RegistroCoating.objects.create(
                turno_coating=turno, maquina=self.maquina, lote=lote, tratamento=self.tratamento,
                lado=lado, hora_entrada=entrada, hora_saida=saida,
            )

        criar(13876, "CC", turno2, self._dt(0, 21, 0), self._dt(0, 21, 40))
        criar(13877, "CX", turno2, self._dt(0, 22, 40), self._dt(0, 23, 25))
        criar(13879, "CC", turno3, self._dt(1, 1, 51), self._dt(1, 2, 35))
        atual = criar(13878, "CC", turno3, self._dt(0, 0, 55), None)

        data = self._analisar(atual, self._dt(0, 0, 55), self._dt(1, 1, 40))

        self.assertEqual([a["codigo"] for a in data["anomalias"]], ["over_24h"])
        melhor = data["sugestoes"][0]
        self.assertEqual(melhor["campo"], "saida")
        self.assertEqual(melhor["hora_entrada"], timezone.localtime(self._dt(0, 0, 55)).strftime("%Y-%m-%dT%H:%M"))
        self.assertEqual(melhor["hora_saida"], timezone.localtime(self._dt(0, 1, 40)).strftime("%Y-%m-%dT%H:%M"))
        self.assertTrue(any("coerente com a coluna Data" in m for m in melhor["motivos"]))
        linha_atual = next(v for v in data["contexto"]["vizinhos"] if v["atual"])
        self.assertEqual(linha_atual["turno"], "TURNO 03")

    def test_sugestao_sobreposta_aparece_com_confianca_baixa(self):
        # Caso da tela: 13937 CC entrada 15/09 22:37, saída digitada 16/09 23:32. Um vizinho
        # registrado sobre o horário correto não pode fazer a sugestão sumir.
        vizinho = self._criar(13937, "CX", self._dt(0, 23, 0), self._dt(0, 23, 50))
        atual = self._criar(13937, "CC", self._dt(0, 22, 37), None)

        data = self._analisar(atual, self._dt(0, 22, 37), self._dt(1, 23, 32))

        melhor = data["sugestoes"][0]
        self.assertEqual(melhor["hora_saida"], timezone.localtime(self._dt(0, 23, 32)).strftime("%Y-%m-%dT%H:%M"))
        self.assertEqual(melhor["confianca"], "baixa")
        self.assertTrue(any("sobrepõe" in m and "13937 CX" in m for m in melhor["motivos"]))
        self.assertTrue(vizinho.hora_entrada < self._dt(0, 23, 32))

    def test_sugestao_sem_sobreposicao_vence_a_sobreposta(self):
        self._criar(13860, "CC", self._dt(0, 3, 0), self._dt(0, 3, 50))
        atual = self._criar(13859, "CC", self._dt(0, 1, 37), None)

        data = self._analisar(atual, self._dt(0, 1, 37), self._dt(0, 1, 6))

        melhor = data["sugestoes"][0]
        self.assertNotEqual(melhor["confianca"], "baixa")
        self.assertLessEqual(
            timezone.make_aware(datetime.fromisoformat(melhor["hora_saida"])), self._dt(0, 3, 10)
        )

    def test_horario_vazio_nao_gera_sugestao_inventada(self):
        atual = self._criar(13859, "CC", self._dt(0, 2, 37), None)
        data = self._analisar(atual, self._dt(0, 2, 37), None)
        self.assertEqual([a["codigo"] for a in data["anomalias"]], ["missing"])
        self.assertEqual(data["sugestoes"], [])

    def test_horarios_validos_com_sobreposicao_geram_aviso(self):
        self._criar(13859, "CX", self._dt(0, 3, 0), self._dt(0, 3, 50))
        atual = self._criar(13859, "CC", self._dt(0, 2, 37), None)

        data = self._analisar(atual, self._dt(0, 2, 37), self._dt(0, 3, 30))

        self.assertEqual(data["anomalias"], [])
        self.assertEqual([a["codigo"] for a in data["avisos"]], ["overlap"])

    def test_paginas_de_edicao_carregam_validacao(self):
        self.client.force_login(get_user_model().objects.create_superuser(username="coating.admin", password="x"))
        url_analise = reverse("laboratorio:api_analisar_horarios_coating")
        for nome in ("laboratorio:coating_painel", "laboratorio:dashboard_coating"):
            response = self.client.get(reverse(nome))
            self.assertEqual(response.status_code, 200, nome)
            self.assertContains(response, "CoatingValidacao.ligar")
            self.assertContains(response, url_analise)
