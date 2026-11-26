import json
from datetime import date, datetime, timedelta

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from agenda.models import Evento, EventoConclusao, EventoParticipante
from agenda.services import datas_do_evento, ocorrencias


def _dt(ano, mes, dia, h=9, m=0):
    return timezone.make_aware(datetime(ano, mes, dia, h, m))


class RecorrenciaTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("a", password="x")

    def _ev(self, **kw):
        base = dict(titulo="T", criado_por=self.u, inicio=_dt(2026, 1, 31))
        base.update(kw)
        return Evento.objects.create(**base)

    def test_sem_recorrencia_multi_dia(self):
        ev = self._ev(inicio=_dt(2026, 3, 10), fim=_dt(2026, 3, 12, 18))
        dias = [d for d, _ in datas_do_evento(ev, date(2026, 3, 1), date(2026, 3, 31))]
        self.assertEqual(dias, [date(2026, 3, 10), date(2026, 3, 11), date(2026, 3, 12)])

    def test_diaria_respeita_ate(self):
        ev = self._ev(recorrencia="diaria", recorrencia_ate=date(2026, 2, 3))
        dias = [d for d, _ in datas_do_evento(ev, date(2026, 1, 1), date(2026, 12, 31))]
        self.assertEqual(dias, [date(2026, 1, 31), date(2026, 2, 1), date(2026, 2, 2), date(2026, 2, 3)])

    def test_semanal(self):
        ev = self._ev(recorrencia="semanal")
        dias = [d for d, _ in datas_do_evento(ev, date(2026, 2, 1), date(2026, 2, 28))]
        self.assertEqual(dias, [date(2026, 2, 7), date(2026, 2, 14), date(2026, 2, 21), date(2026, 2, 28)])

    def test_mensal_ajusta_dia_31(self):
        ev = self._ev(recorrencia="mensal")
        dias = [d for d, _ in datas_do_evento(ev, date(2026, 1, 1), date(2026, 4, 30))]
        self.assertEqual(dias, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)])


class VisibilidadeTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("a", password="x")
        self.b = User.objects.create_user("b", password="x")
        self.c = User.objects.create_user("c", password="x")
        hoje = timezone.now()
        self.pessoal = Evento.objects.create(titulo="P", criado_por=self.a, inicio=hoje)
        self.comum = Evento.objects.create(titulo="C", criado_por=self.a, inicio=hoje, escopo="comum")
        self.convite = Evento.objects.create(titulo="V", criado_por=self.a, inicio=hoje)
        EventoParticipante.objects.create(evento=self.convite, usuario=self.b)

    def test_visibilidade(self):
        self.assertEqual(set(Evento.visiveis_para(self.a).values_list("titulo", flat=True)), {"P", "C", "V"})
        self.assertEqual(set(Evento.visiveis_para(self.b).values_list("titulo", flat=True)), {"C", "V"})
        self.assertEqual(set(Evento.visiveis_para(self.c).values_list("titulo", flat=True)), {"C"})

    def test_pode_editar_so_criador(self):
        self.assertTrue(self.comum.pode_editar(self.a))
        self.assertFalse(self.comum.pode_editar(self.b))


class ViewsTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_superuser("adm", "a@a.com", "x")
        self.b = User.objects.create_user("b", password="x")
        self.client.force_login(self.a)

    def _salvar(self, **extra):
        corpo = {"titulo": "Reunião", "inicio": "2026-05-04T10:00", "fim": "2026-05-04T11:00", "escopo": "pessoal"}
        corpo.update(extra)
        return self.client.post(reverse("agenda:evento_salvar"), json.dumps(corpo), content_type="application/json")

    def test_paginas_renderizam(self):
        self.assertEqual(self.client.get(reverse("agenda:calendario")).status_code, 200)
        self.assertEqual(self.client.get(reverse("agenda:checklist")).status_code, 200)

    def test_criar_com_convidado_e_listar(self):
        r = self._salvar(participantes=[self.b.id], recorrencia="semanal", recorrencia_ate="2026-05-31")
        self.assertTrue(r.json()["success"])
        ev = Evento.objects.get()
        self.assertEqual(ev.convites.count(), 1)
        self.client.force_login(self.b)
        r = self.client.get(reverse("agenda:api_eventos"), {"inicio": "2026-05-01", "fim": "2026-05-31"})
        dias = [e["dia"] for e in r.json()["eventos"]]
        self.assertEqual(dias, ["2026-05-04", "2026-05-11", "2026-05-18", "2026-05-25"])

    def test_pessoal_de_outro_nao_aparece_nem_abre(self):
        self._salvar()
        self.client.force_login(self.b)
        r = self.client.get(reverse("agenda:api_eventos"), {"inicio": "2026-05-01", "fim": "2026-05-31"})
        self.assertEqual(r.json()["eventos"], [])
        self.assertEqual(self.client.get(reverse("agenda:api_evento_detalhe", args=[Evento.objects.get().id])).status_code, 404)

    def test_criar_comum_exige_permissao_especial(self):
        self.client.force_login(self.b)
        self.assertEqual(self._salvar(escopo="comum").status_code, 403)
        self.b.user_permissions.add(Permission.objects.get(content_type__app_label="core", codename="nav_agenda_criar_comum"))
        self.b = User.objects.get(pk=self.b.pk)
        self.client.force_login(self.b)
        self.assertTrue(self._salvar(escopo="comum").json()["success"])

    def test_so_criador_edita_e_exclui(self):
        self._salvar(escopo="comum")
        ev = Evento.objects.get()
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(reverse("agenda:evento_excluir", args=[ev.id])).status_code, 403)
        r = self._salvar(id=ev.id, titulo="Hack")
        self.assertEqual(r.status_code, 403)

    def test_validacoes(self):
        self.assertEqual(self._salvar(titulo=" ").status_code, 400)
        self.assertEqual(self._salvar(fim="2026-05-04T08:00").status_code, 400)
        self.assertEqual(self._salvar(inicio="lixo").status_code, 400)
        r = self.client.get(reverse("agenda:api_eventos"), {"inicio": "2026-01-01", "fim": "2030-01-01"})
        self.assertEqual(r.status_code, 400)

    def test_checklist_toggle_por_usuario_e_dia(self):
        self._salvar(checklist=True, recorrencia="diaria", dia_inteiro=True, inicio="2026-05-04T00:00", fim="")
        ev = Evento.objects.get()
        url = reverse("agenda:api_checklist_toggle", args=[ev.id])
        r = self.client.post(url, json.dumps({"data": "2026-05-06"}), content_type="application/json")
        self.assertTrue(r.json()["feito"])
        self.assertEqual(EventoConclusao.objects.count(), 1)
        itens = ocorrencias(self.a, date(2026, 5, 5), date(2026, 5, 7), so_checklist=True)
        self.assertEqual([i["feito"] for i in itens], [False, True, False])
        r = self.client.post(url, json.dumps({"data": "2026-05-06"}), content_type="application/json")
        self.assertFalse(r.json()["feito"])
        # antes do início do evento não é ocorrência
        r = self.client.post(url, json.dumps({"data": "2026-05-01"}), content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_responder_convite(self):
        self._salvar(participantes=[self.b.id])
        ev = Evento.objects.get()
        self.client.force_login(self.b)
        r = self.client.post(reverse("agenda:api_responder_convite", args=[ev.id]), json.dumps({"resposta": "aceito"}), content_type="application/json")
        self.assertTrue(r.json()["success"])
        self.assertEqual(EventoParticipante.objects.get().resposta, "aceito")


class InboxTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # a inbox é cacheada por pk de usuário (reaproveitado entre testes)

    def test_checklist_pendente_e_convite_na_inbox(self):
        from shared.inbox import get_user_inbox_items

        a = User.objects.create_superuser("adm", "a@a.com", "x")
        b = User.objects.create_superuser("b", "b@a.com", "x")
        agora = timezone.now()
        ev = Evento.objects.create(titulo="Rotina", criado_por=a, inicio=agora - timedelta(hours=1), checklist=True, dia_inteiro=True, recorrencia="diaria")
        EventoParticipante.objects.create(evento=ev, usuario=b)
        titulos = [i.title for i in get_user_inbox_items(a) if i.module == "Agenda"]
        self.assertIn("Checklist: Rotina", titulos)
        titulos_b = [i.title for i in get_user_inbox_items(b) if i.module == "Agenda"]
        self.assertIn("Convite: Rotina", titulos_b)


class ChecklistModeloTests(TestCase):
    def setUp(self):
        from agenda.models import Checklist, ChecklistItem  # noqa: F401

        self.a = User.objects.create_superuser("adm", "a@a.com", "x")
        self.b = User.objects.create_user("b", password="x")
        self.client.force_login(self.a)

    def _criar(self, **extra):
        corpo = {"titulo": "Abertura", "itens": [{"texto": "Ligar equipamentos"}, {"texto": "Conferir EPIs"}, {"texto": "  "}]}
        corpo.update(extra)
        return self.client.post(reverse("agenda:checklist_salvar"), json.dumps(corpo), content_type="application/json")

    def _evento_com_modelo(self, checklist_id, **extra):
        corpo = {
            "titulo": "Rotina de abertura", "inicio": "2026-05-04T08:00", "escopo": "pessoal",
            "recorrencia": "diaria", "checklist_modelo": checklist_id,
        }
        corpo.update(extra)
        return self.client.post(reverse("agenda:evento_salvar"), json.dumps(corpo), content_type="application/json")

    def test_criar_checklist_ignora_itens_vazios_e_exige_item(self):
        from agenda.models import Checklist

        r = self._criar()
        self.assertTrue(r.json()["success"])
        c = Checklist.objects.get()
        self.assertEqual([i.texto for i in c.itens.all()], ["Ligar equipamentos", "Conferir EPIs"])
        self.assertEqual(self._criar(titulo=" ").status_code, 400)
        self.assertEqual(self._criar(itens=[{"texto": ""}]).status_code, 400)

    def test_editar_preserva_itens_existentes_e_remove_os_retirados(self):
        from agenda.models import Checklist

        self._criar()
        c = Checklist.objects.get()
        a, b = list(c.itens.all())
        self._criar(id=c.id, itens=[{"id": b.id, "texto": "EPIs conferidos"}, {"texto": "Novo"}])
        c.refresh_from_db()
        textos = [i.texto for i in c.itens.all()]
        self.assertEqual(textos, ["EPIs conferidos", "Novo"])
        self.assertTrue(c.itens.filter(id=b.id).exists())
        self.assertFalse(c.itens.filter(id=a.id).exists())

    def test_so_o_dono_ve_e_edita_o_checklist(self):
        from agenda.models import Checklist

        self._criar()
        c = Checklist.objects.get()
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse("agenda:api_checklist_detalhe", args=[c.id])).status_code, 404)
        self.assertEqual(self.client.post(reverse("agenda:checklist_excluir", args=[c.id])).status_code, 404)
        self.assertEqual(self._criar(id=c.id).status_code, 404)
        self.assertNotContains(self.client.get(reverse("agenda:checklists")), "Conferir EPIs")

    def test_nao_associa_checklist_de_outro_usuario(self):
        self._criar()
        from agenda.models import Checklist

        cid = Checklist.objects.get().id
        self.client.force_login(self.b)
        self.assertEqual(self._evento_com_modelo(cid).status_code, 400)

    def test_marcar_itens_por_dia_e_progresso(self):
        from agenda.models import Checklist, ItemConclusao

        self._criar()
        c = Checklist.objects.get()
        self.assertTrue(self._evento_com_modelo(c.id).json()["success"])
        ev = Evento.objects.get()
        i1, i2 = list(c.itens.all())
        url = lambda it: reverse("agenda:api_item_toggle", args=[ev.id, it.id])  # noqa: E731
        dia = {"data": "2026-05-06"}
        self.assertTrue(self.client.post(url(i1), json.dumps(dia), content_type="application/json").json()["feito"])
        occ = ocorrencias(self.a, date(2026, 5, 6), date(2026, 5, 7), so_checklist=True)
        self.assertEqual([o["feito"] for o in occ], [False, False])  # só 1 de 2 itens
        self.assertEqual([x["feito"] for x in occ[0]["itens"]], [True, False])
        self.client.post(url(i2), json.dumps(dia), content_type="application/json")
        occ = ocorrencias(self.a, date(2026, 5, 6), date(2026, 5, 7), so_checklist=True)
        self.assertEqual([o["feito"] for o in occ], [True, False])  # completo só no dia 6
        self.assertEqual(ItemConclusao.objects.count(), 2)
        # desmarca
        self.assertFalse(self.client.post(url(i1), json.dumps(dia), content_type="application/json").json()["feito"])
        # data fora da rotina e item de outro checklist
        antes = self.client.post(url(i1), json.dumps({"data": "2026-05-01"}), content_type="application/json")
        self.assertEqual(antes.status_code, 400)

    def test_marcacao_e_por_usuario(self):
        from agenda.models import Checklist

        self._criar()
        c = Checklist.objects.get()
        self._evento_com_modelo(c.id, escopo="comum")
        ev = Evento.objects.get()
        item = c.itens.first()
        self.client.post(
            reverse("agenda:api_item_toggle", args=[ev.id, item.id]), json.dumps({"data": "2026-05-04"}), content_type="application/json"
        )
        itens_b = ocorrencias(self.b, date(2026, 5, 4), date(2026, 5, 4), so_checklist=True)[0]["itens"]
        self.assertEqual([i["feito"] for i in itens_b], [False, False])

    def test_excluir_checklist_mantem_evento(self):
        from agenda.models import Checklist

        self._criar()
        c = Checklist.objects.get()
        self._evento_com_modelo(c.id)
        self.assertTrue(self.client.post(reverse("agenda:checklist_excluir", args=[c.id])).json()["success"])
        ev = Evento.objects.get()
        self.assertIsNone(ev.checklist_modelo_id)

    def test_paginas_e_dia_renderizam_itens(self):
        from agenda.models import Checklist

        self._criar()
        self._evento_com_modelo(Checklist.objects.get().id, inicio="2026-05-04T08:00")
        self.assertEqual(self.client.get(reverse("agenda:checklists")).status_code, 200)
        r = self.client.get(reverse("agenda:checklist"), {"data": "2026-05-04"})
        self.assertContains(r, "Ligar equipamentos")
        self.assertContains(r, '<span id="ckFeitos">0</span> de 2 concluídos')

    def test_inbox_mostra_progresso_do_checklist_associado(self):
        from django.core.cache import cache

        from agenda.models import Checklist
        from shared.inbox import get_user_inbox_items

        cache.clear()
        self._criar()
        c = Checklist.objects.get()
        corpo = {"titulo": "Rotina", "inicio": (timezone.localtime() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
                 "recorrencia": "diaria", "dia_inteiro": True, "checklist_modelo": c.id}
        self.client.post(reverse("agenda:evento_salvar"), json.dumps(corpo), content_type="application/json")
        itens = [i for i in get_user_inbox_items(self.a) if i.module == "Agenda" and i.title == "Checklist: Rotina"]
        self.assertEqual(len(itens), 1)
        self.assertEqual(itens[0].description, "0 de 2 itens")


class ChecklistDiarioTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.a = User.objects.create_superuser("adm", "a@a.com", "x")
        self.b = User.objects.create_user("b", password="x")
        self.client.force_login(self.a)

    def _criar(self, **extra):
        corpo = {
            "titulo": "Abertura", "itens": [{"texto": "Ligar equipamentos"}, {"texto": "Conferir EPIs"}],
            "diario": True, "dias_semana": [0, 1, 2, 3, 4], "hora": "08:00", "na_agenda": True,
        }
        corpo.update(extra)
        return self.client.post(reverse("agenda:checklist_salvar"), json.dumps(corpo), content_type="application/json")

    def test_diario_aparece_nos_dias_validos_sem_evento(self):
        from agenda.models import Checklist
        from agenda.services import checklists_diarios

        self.assertTrue(self._criar().json()["success"])
        c = Checklist.objects.get()
        self.assertEqual(c.diario_desde, timezone.localdate())
        self.assertEqual(Evento.objects.count(), 0)  # independe da agenda
        hoje = timezone.localdate()
        seg = hoje + timedelta(days=(7 - hoje.weekday()) % 7 or 7)  # próxima segunda
        occ = checklists_diarios(self.a, seg, seg + timedelta(days=6))
        self.assertEqual([o["dia"].weekday() for o in occ], [0, 1, 2, 3, 4])  # sem sáb/dom
        self.assertEqual(occ[0]["tipo"], "checklist_diario")
        self.assertEqual(len(occ[0]["itens"]), 2)

    def test_nao_retroage_antes_de_diario_desde(self):
        from agenda.services import checklists_diarios

        self._criar(dias_semana=[0, 1, 2, 3, 4, 5, 6])
        ontem = timezone.localdate() - timedelta(days=1)
        self.assertEqual(checklists_diarios(self.a, ontem, ontem), [])

    def test_na_agenda_controla_o_calendario_mas_nao_o_checklist_do_dia(self):
        hoje = timezone.localdate()
        self._criar(na_agenda=False, dias_semana=[0, 1, 2, 3, 4, 5, 6])
        r = self.client.get(reverse("agenda:api_eventos"), {"inicio": hoje.isoformat(), "fim": hoje.isoformat()})
        self.assertEqual(r.json()["eventos"], [])  # fora do calendário
        self.assertContains(self.client.get(reverse("agenda:checklist")), "Ligar equipamentos")  # mas no checklist do dia
        from agenda.models import Checklist

        c = Checklist.objects.get()
        self._criar(id=c.id, na_agenda=True, dias_semana=[0, 1, 2, 3, 4, 5, 6])
        r = self.client.get(reverse("agenda:api_eventos"), {"inicio": hoje.isoformat(), "fim": hoje.isoformat()})
        ev = r.json()["eventos"]
        self.assertEqual([(e["tipo"], e["titulo"]) for e in ev], [("checklist_diario", "Abertura")])

    def test_marcar_itens_do_diario(self):
        from agenda.models import Checklist, ChecklistDiarioConclusao

        self._criar(dias_semana=[0, 1, 2, 3, 4, 5, 6])
        c = Checklist.objects.get()
        i1, i2 = list(c.itens.all())
        hoje = timezone.localdate().isoformat()
        url = lambda it: reverse("agenda:api_diario_toggle", args=[c.id, it.id])  # noqa: E731
        self.assertTrue(self.client.post(url(i1), json.dumps({"data": hoje}), content_type="application/json").json()["feito"])
        self.client.post(url(i2), json.dumps({"data": hoje}), content_type="application/json")
        self.assertEqual(ChecklistDiarioConclusao.objects.count(), 2)
        self.assertContains(self.client.get(reverse("agenda:checklist")), '<span id="ckFeitos">2</span> de 2 concluídos')
        self.assertFalse(self.client.post(url(i1), json.dumps({"data": hoje}), content_type="application/json").json()["feito"])
        # data antes de começar a valer
        antes = (timezone.localdate() - timedelta(days=3)).isoformat()
        self.assertEqual(self.client.post(url(i1), json.dumps({"data": antes}), content_type="application/json").status_code, 400)

    def test_marcacao_e_por_usuario_e_so_do_dono(self):
        from agenda.models import Checklist

        self._criar(dias_semana=[0, 1, 2, 3, 4, 5, 6])
        c = Checklist.objects.get()
        item = c.itens.first()
        self.client.force_login(self.b)
        r = self.client.post(
            reverse("agenda:api_diario_toggle", args=[c.id, item.id]),
            json.dumps({"data": timezone.localdate().isoformat()}), content_type="application/json",
        )
        self.assertEqual(r.status_code, 404)  # checklist é do outro usuário

    def test_validacoes_do_diario(self):
        self.assertEqual(self._criar(dias_semana=[]).status_code, 400)
        self.assertEqual(self._criar(hora="25:99").status_code, 400)
        self.assertTrue(self._criar(diario=False, dias_semana=[]).json()["success"])  # sem diário, dias são ignorados

    def test_inbox_tem_checklist_diario_pendente(self):
        from shared.inbox import get_user_inbox_items

        self._criar(dias_semana=[0, 1, 2, 3, 4, 5, 6])
        itens = [i for i in get_user_inbox_items(self.a) if i.module == "Agenda"]
        self.assertEqual([(i.title, i.description) for i in itens], [("Checklist: Abertura", "0 de 2 itens")])
