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

    def test_lote_em_andamento_com_vizinhos_nao_quebra_analise(self):
        agora = timezone.now().replace(second=0, microsecond=0)
        self._criar(13858, "CC", agora - timedelta(hours=3), agora - timedelta(hours=2))
        atual = self._criar(13859, "CC", agora - timedelta(hours=1), None)

        self.assertEqual(self._analisar(atual, agora - timedelta(hours=1), None)["anomalias"], [])
        self.assertEqual(self._analisar(atual, None, None)["anomalias"], [])

    def test_conflito_de_horario_e_anomalia(self):
        self._criar(13859, "CX", self._dt(0, 3, 0), self._dt(0, 3, 50))
        atual = self._criar(13859, "CC", self._dt(0, 2, 37), None)

        data = self._analisar(atual, self._dt(0, 2, 37), self._dt(0, 3, 30))

        self.assertEqual([a["codigo"] for a in data["anomalias"]], ["overlap"])
        self.assertIn("13859 CX", data["anomalias"][0]["detalhe"])

    def test_conflito_bloqueia_salvar(self):
        self._criar(13859, "CX", self._dt(0, 3, 0), self._dt(0, 3, 50))
        atual = self._criar(13859, "CC", self._dt(0, 2, 37), None)

        response = self.client.post(
            reverse("laboratorio:api_editar_linha_coating"),
            data=json.dumps({"id": atual.id,
                             "hora_entrada": timezone.localtime(self._dt(0, 2, 37)).strftime("%Y-%m-%dT%H:%M"),
                             "hora_saida": timezone.localtime(self._dt(0, 3, 30)).strftime("%Y-%m-%dT%H:%M")}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual([a["codigo"] for a in response.json()["anomalias"]], ["overlap"])
        self.assertTrue(response.json()["requer_confirmacao_mix"])
        atual.refresh_from_db()
        self.assertIsNone(atual.hora_saida)

    def test_conflito_sugere_corrigir_o_vizinho(self):
        # Caso da tela: 13937 CC 22:37 com saída digitada no dia seguinte; o 13938 CC
        # (22:35 → 00:05) ocupa o horário. Provável erro no vizinho: entrada 23:35.
        vizinho = self._criar(13938, "CC", self._dt(0, 22, 35), self._dt(1, 0, 5))
        atual = self._criar(13937, "CC", self._dt(0, 22, 37), None)

        data = self._analisar(atual, self._dt(0, 22, 37), self._dt(1, 23, 32))

        self.assertEqual(data["sugestoes"][0]["confianca"], "baixa")
        correcao = data["correcoes_vizinhos"][0]
        self.assertEqual(correcao["registro_id"], vizinho.id)
        self.assertEqual(correcao["hora_entrada"], timezone.localtime(self._dt(0, 23, 35)).strftime("%Y-%m-%dT%H:%M"))
        self.assertEqual(correcao["hora_saida"], timezone.localtime(self._dt(1, 0, 5)).strftime("%Y-%m-%dT%H:%M"))
        self.assertEqual(correcao["conflitos"], [])
        linha_vizinho = next(v for v in data["contexto"]["vizinhos"] if v["lote"] == 13938)
        self.assertEqual(linha_vizinho["status"], "conflito")

    def test_auditoria_filtra_conflito_de_horarios(self):
        self._criar(13938, "CC", self._dt(0, 22, 35), self._dt(1, 0, 5))
        self._criar(13937, "CC", self._dt(0, 22, 37), self._dt(0, 23, 32))
        self.client.force_login(get_user_model().objects.create_superuser(username="coating.audit", password="x"))

        for filtro in ("overlap", ""):
            response = self.client.get(reverse("laboratorio:coating_painel"), {"audit": "true", "anomaly": filtro})
            lotes = {r.lote for r in response.context["registros"]}
            self.assertTrue({13937, 13938} <= lotes, filtro)
            self.assertNotIn(10005, lotes, filtro)

    def test_paginas_de_edicao_carregam_validacao(self):
        self.client.force_login(get_user_model().objects.create_superuser(username="coating.admin", password="x"))
        url_analise = reverse("laboratorio:api_analisar_horarios_coating")
        for nome in ("laboratorio:coating_painel", "laboratorio:dashboard_coating"):
            response = self.client.get(reverse(nome))
            self.assertEqual(response.status_code, 200, nome)
            self.assertContains(response, "CoatingValidacao.ligar")
            self.assertContains(response, url_analise)


class CoatingMixServicoTests(TestCase):
    """Mix de serviço: lote inserido no meio de outro em andamento — sobreposição confirmada pelo usuário."""

    _dt = CoatingSugestaoCorrecaoTests._dt
    _criar = CoatingSugestaoCorrecaoTests._criar
    _analisar = CoatingSugestaoCorrecaoTests._analisar

    def setUp(self):
        CoatingSugestaoCorrecaoTests.setUp(self)
        # Caso da tela: 13973 CX 23:57 → 00:42 e 13974 CC inserido às 00:00 → 00:56
        self.hospedeiro = self._criar(13973, "CX", self._dt(0, 23, 57), self._dt(1, 0, 42))
        self.atual = self._criar(13974, "CC", self._dt(1, 0, 0), None)

    def _salvar(self, registro, entrada, saida, **extra):
        return self.client.post(
            reverse("laboratorio:api_editar_linha_coating"),
            data=json.dumps({"id": registro.id,
                             "hora_entrada": timezone.localtime(entrada).strftime("%Y-%m-%dT%H:%M"),
                             "hora_saida": timezone.localtime(saida).strftime("%Y-%m-%dT%H:%M"), **extra}),
            content_type="application/json",
        )

    def _lotes_na_auditoria(self):
        self.client.force_login(get_user_model().objects.get_or_create(
            username="coating.mix.audit", defaults={"is_staff": True, "is_superuser": True})[0])
        response = self.client.get(reverse("laboratorio:coating_painel"), {"audit": "true", "anomaly": "overlap"})
        return {r.lote for r in response.context["registros"]}

    def test_confirmacao_de_mix_libera_o_conflito(self):
        response = self._salvar(self.atual, self._dt(1, 0, 0), self._dt(1, 0, 56), confirmar_mix_servico=True)

        self.assertEqual(response.status_code, 200)
        self.atual.refresh_from_db()
        self.assertTrue(self.atual.mix_servico)
        self.assertEqual(self.atual.mix_servico_confirmado_por, self.user)
        self.assertIsNotNone(self.atual.mix_servico_confirmado_em)

    def test_mix_nao_libera_outras_anomalias(self):
        response = self._salvar(self.atual, self._dt(1, 0, 0), self._dt(0, 23, 0), confirmar_mix_servico=True)

        self.assertEqual(response.status_code, 400)
        self.assertEqual([a["codigo"] for a in response.json()["anomalias"]], ["negative"])
        self.assertNotIn("requer_confirmacao_mix", response.json())

    def test_mix_confirmado_vale_enquanto_os_horarios_nao_mudam(self):
        self._salvar(self.atual, self._dt(1, 0, 0), self._dt(1, 0, 56), confirmar_mix_servico=True)

        mesmos = self._salvar(self.atual, self._dt(1, 0, 0), self._dt(1, 0, 56), observacao="ok")
        self.assertEqual(mesmos.status_code, 200)

        outros = self._salvar(self.atual, self._dt(1, 0, 5), self._dt(1, 0, 56))
        self.assertEqual(outros.status_code, 400)
        self.assertTrue(outros.json()["requer_confirmacao_mix"])

    def test_sem_conflito_desfaz_o_mix(self):
        self._salvar(self.atual, self._dt(1, 0, 0), self._dt(1, 0, 56), confirmar_mix_servico=True)
        response = self._salvar(self.atual, self._dt(1, 0, 50), self._dt(1, 1, 40))

        self.assertEqual(response.status_code, 200)
        self.atual.refresh_from_db()
        self.assertFalse(self.atual.mix_servico)
        self.assertIsNone(self.atual.mix_servico_confirmado_por)

    def test_mix_confirmado_sai_da_auditoria_dos_dois_lotes(self):
        self.atual.hora_saida = self._dt(1, 0, 56)
        self.atual.save()
        self.assertTrue({13973, 13974} <= self._lotes_na_auditoria())

        RegistroCoating.objects.filter(pk=self.atual.pk).update(mix_servico=True)
        lotes = self._lotes_na_auditoria()
        self.assertNotIn(13973, lotes)
        self.assertNotIn(13974, lotes)

    def test_lote_hospedeiro_nao_conflita_com_o_mix(self):
        self._salvar(self.atual, self._dt(1, 0, 0), self._dt(1, 0, 56), confirmar_mix_servico=True)

        response = self._salvar(self.hospedeiro, self._dt(0, 23, 57), self._dt(1, 0, 45))
        self.assertEqual(response.status_code, 200)

        data = self._analisar(self.hospedeiro, self._dt(0, 23, 57), self._dt(1, 0, 45))
        self.assertEqual(data["anomalias"], [])
        linha_mix = next(v for v in data["contexto"]["vizinhos"] if v["lote"] == 13974)
        self.assertEqual(linha_mix["status"], "mix")

    def test_analise_informa_mix_ja_confirmado(self):
        self._salvar(self.atual, self._dt(1, 0, 0), self._dt(1, 0, 56), confirmar_mix_servico=True)

        data = self._analisar(self.atual, self._dt(1, 0, 0), self._dt(1, 0, 56))
        self.assertEqual([a["codigo"] for a in data["anomalias"]], ["overlap"])
        self.assertTrue(data["mix_servico"]["confirmado"])
        self.assertEqual(data["mix_servico"]["por"], "coating.sug")

        alterado = self._analisar(self.atual, self._dt(1, 0, 5), self._dt(1, 0, 56))
        self.assertFalse(alterado["mix_servico"]["confirmado"])

    def test_edicao_rapida_pede_confirmacao_de_mix(self):
        self.atual.hora_entrada = self._dt(1, 0, 0)
        self.atual.save()
        url = reverse("laboratorio:atualizar_celula_coating")
        payload = {"id": self.atual.id, "campo": "hora_saida",
                   "valor": timezone.localtime(self._dt(1, 0, 56)).strftime("%Y-%m-%dT%H:%M")}

        response = self.client.post(url, data=json.dumps(payload), content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()["requer_confirmacao_mix"])

        response = self.client.post(url, data=json.dumps({**payload, "confirmar_mix_servico": True}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.atual.refresh_from_db()
        self.assertTrue(self.atual.mix_servico)
