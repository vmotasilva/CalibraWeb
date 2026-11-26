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


class HierarquiaTests(TestCase):
    """Líder, Vice-Líder, Supervisor e Gerente (vínculos do Colaborador) ajustam e vistoriam os liderados."""

    def setUp(self):
        from django.core.cache import cache

        from rh.models import Colaborador

        cache.clear()
        self.cont = 0

        def mk(login, **vinc):
            self.cont += 1
            u = User.objects.create_user(login, password="x", first_name=login.title())
            c = Colaborador.objects.create(
                user_django=u, matricula=f"M{self.cont}", nome_completo=f"Pessoa {login}", grupo="G", **vinc
            )
            return u, c

        self.gerente, cg = mk("gerente")
        self.sup, cs = mk("sup", gerente=cg)
        self.vice, cv = mk("vice", gerente=cg, supervisor=cs)
        self.lider, cl = mk("lider", gerente=cg, supervisor=cs)
        self.ana, _ = mk("ana", lider=cl, vice_lider=cv, supervisor=cs, gerente=cg)
        self.bia, _ = mk("bia", lider=cl, supervisor=cs, gerente=cg)
        self.estranho, _ = mk("estranho")
        self.admin = User.objects.create_superuser("adm", "a@a.com", "x")

    def _post(self, nome, corpo):
        return self.client.post(reverse(nome), json.dumps(corpo), content_type="application/json")

    def _evento_da_ana(self, **extra):
        corpo = {"titulo": "Reunião 1:1", "inicio": "2026-05-04T10:00", "usuario": self.ana.id}
        corpo.update(extra)
        return self._post("agenda:evento_salvar", corpo)

    def test_equipe_e_papeis(self):
        from agenda.hierarquia import equipe_de, papel_sobre

        por_login = lambda u: {m["usuario"].username: m["papel"] for m in equipe_de(u)}  # noqa: E731
        self.assertEqual(por_login(self.lider), {"ana": "Líder", "bia": "Líder"})
        self.assertEqual(por_login(self.vice), {"ana": "Vice-Líder"})
        self.assertEqual(por_login(self.sup)["ana"], "Supervisor")
        g = por_login(self.gerente)
        self.assertEqual(g["ana"], "Gerente")
        self.assertEqual(g["lider"], "Gerente")  # gerente enxerga também quem tem o vínculo direto com ele
        self.assertNotIn("gerente", g)  # não aparece como liderado de si mesmo
        self.assertEqual(por_login(self.estranho), {})
        self.assertEqual(por_login(self.ana), {})
        self.assertEqual(papel_sobre(self.lider, self.ana), "Líder")

    def test_colaborador_inativo_nao_entra_na_equipe(self):
        from agenda.hierarquia import equipe_de
        from rh.models import Colaborador

        Colaborador.objects.filter(user_django=self.bia).update(is_active=False)
        self.assertEqual([m["usuario"].username for m in equipe_de(self.lider)], ["ana"])

    def test_chefia_ve_a_agenda_do_liderado_e_estranho_nao(self):
        self.client.force_login(self.ana)
        self._post("agenda:evento_salvar", {"titulo": "Pessoal da Ana", "inicio": "2026-05-04T09:00"})
        q = {"inicio": "2026-05-01", "fim": "2026-05-31"}
        self.client.force_login(self.lider)
        r = self.client.get(reverse("agenda:api_eventos"), {**q, "usuario": self.ana.id})
        self.assertEqual([(e["titulo"], e["editavel"]) for e in r.json()["eventos"]], [("Pessoal da Ana", True)])
        self.assertEqual(self.client.get(reverse("agenda:api_eventos"), q).json()["eventos"], [])  # a minha segue vazia
        self.client.force_login(self.estranho)
        self.assertEqual(self.client.get(reverse("agenda:api_eventos"), {**q, "usuario": self.ana.id}).status_code, 403)
        self.assertEqual(self.client.get(reverse("agenda:calendario"), {"usuario": self.ana.id}).status_code, 403)

    def test_vice_supervisor_e_gerente_tambem_vistoriam(self):
        for u in (self.vice, self.sup, self.gerente):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("agenda:calendario"), {"usuario": self.ana.id}).status_code, 200, u.username)

    def test_chefia_cria_evento_na_agenda_do_liderado_com_auditoria(self):
        from agenda.models import Evento

        self.client.force_login(self.lider)
        self.assertTrue(self._evento_da_ana().json()["success"])
        ev = Evento.objects.get()
        self.assertEqual(ev.criado_por, self.ana)
        self.assertEqual(ev.ajustado_por, self.lider)
        self.assertIsNotNone(ev.ajustado_em)
        # o próprio liderado vê e, ao editar, a marca de ajuste some
        self.client.force_login(self.ana)
        det = self.client.get(reverse("agenda:api_evento_detalhe", args=[ev.id])).json()["evento"]
        self.assertEqual(det["ajustado_por"], "Lider")
        self._post("agenda:evento_salvar", {"id": ev.id, "titulo": "Reunião 1:1 (ajustada)", "inicio": "2026-05-04T10:00"})
        ev.refresh_from_db()
        self.assertIsNone(ev.ajustado_por)

    def test_chefia_edita_e_exclui_evento_do_liderado_mas_estranho_nao(self):
        from agenda.models import Evento

        self.client.force_login(self.ana)
        self._post("agenda:evento_salvar", {"titulo": "Da Ana", "inicio": "2026-05-04T09:00"})
        ev = Evento.objects.get()
        self.client.force_login(self.estranho)
        self.assertEqual(self._post("agenda:evento_salvar", {"id": ev.id, "titulo": "X", "inicio": "2026-05-04T09:00"}).status_code, 403)
        self.assertEqual(self.client.post(reverse("agenda:evento_excluir", args=[ev.id])).status_code, 404)  # nem sabe que existe
        self.client.force_login(self.lider)
        self.assertTrue(self._post("agenda:evento_salvar", {"id": ev.id, "titulo": "Ajustado pelo líder", "inicio": "2026-05-04T09:30"}).json()["success"])
        ev.refresh_from_db()
        self.assertEqual((ev.titulo, ev.criado_por, ev.ajustado_por), ("Ajustado pelo líder", self.ana, self.lider))
        self.assertTrue(self.client.post(reverse("agenda:evento_excluir", args=[ev.id])).json()["success"])
        self.assertEqual(Evento.objects.count(), 0)

    def test_chefia_cria_e_ajusta_checklist_do_liderado(self):
        from agenda.models import Checklist

        self.client.force_login(self.lider)
        corpo = {"titulo": "Abertura", "usuario": self.ana.id, "itens": [{"texto": "Ligar"}], "diario": True,
                 "dias_semana": [0, 1, 2, 3, 4, 5, 6]}
        self.assertTrue(self._post("agenda:checklist_salvar", corpo).json()["success"])
        c = Checklist.objects.get()
        self.assertEqual((c.criado_por, c.ajustado_por), (self.ana, self.lider))
        # aparece na lista da Ana e na visão da chefia sobre a Ana, mas não na lista da própria chefia
        self.assertContains(self.client.get(reverse("agenda:checklists"), {"usuario": self.ana.id}), "Abertura")
        self.assertNotContains(self.client.get(reverse("agenda:checklists")), "Ligar")
        self.assertTrue(self._post("agenda:checklist_salvar", {**corpo, "id": c.id, "titulo": "Abertura v2"}).json()["success"])
        self.client.force_login(self.estranho)
        self.assertEqual(self.client.get(reverse("agenda:api_checklist_detalhe", args=[c.id])).status_code, 404)
        self.assertEqual(self._post("agenda:checklist_salvar", {**corpo, "id": c.id}).status_code, 404)
        self.assertEqual(self._post("agenda:checklist_salvar", {**corpo, "usuario": self.ana.id}).status_code, 403)

    def test_marcacao_continua_sendo_do_liderado(self):
        from agenda.models import Checklist

        self.client.force_login(self.ana)
        self._post("agenda:checklist_salvar", {"titulo": "Rotina", "itens": [{"texto": "A"}], "diario": True, "dias_semana": [0, 1, 2, 3, 4, 5, 6]})
        c = Checklist.objects.get()
        item = c.itens.first()
        hoje = timezone.localdate().isoformat()
        self.client.force_login(self.lider)
        r = self.client.post(
            reverse("agenda:api_diario_toggle", args=[c.id, item.id]), json.dumps({"data": hoje}), content_type="application/json"
        )
        self.assertEqual(r.status_code, 404)  # a chefia vistoria, mas não marca pelo liderado

    def test_checklist_do_dia_do_liderado_e_somente_leitura_para_a_chefia(self):
        self.client.force_login(self.ana)
        self._post("agenda:checklist_salvar", {"titulo": "Rotina", "itens": [{"texto": "Item A"}], "diario": True, "dias_semana": [0, 1, 2, 3, 4, 5, 6]})
        self.client.force_login(self.lider)
        r = self.client.get(reverse("agenda:checklist"), {"usuario": self.ana.id})
        self.assertContains(r, "Item A")
        self.assertContains(r, "vistoriando")
        self.assertContains(r, "disabled")

    def test_pagina_equipe(self):
        self.client.force_login(self.ana)
        self._post("agenda:checklist_salvar", {"titulo": "Rotina", "itens": [{"texto": "A"}, {"texto": "B"}], "diario": True, "dias_semana": [0, 1, 2, 3, 4, 5, 6]})
        self.client.force_login(self.lider)
        r = self.client.get(reverse("agenda:equipe"))
        self.assertEqual(r.status_code, 200)
        linhas = {l["nome"]: l for l in r.context["linhas"]}
        self.assertEqual(set(linhas), {"Pessoa ana", "Pessoa bia"})
        self.assertEqual((linhas["Pessoa ana"]["total"], linhas["Pessoa ana"]["feitos"], linhas["Pessoa ana"]["situacao"]), (2, 0, "pendente"))
        self.assertEqual(linhas["Pessoa bia"]["situacao"], "sem")
        self.client.force_login(self.estranho)
        self.assertContains(self.client.get(reverse("agenda:equipe")), "Nenhum liderado encontrado")

    def test_superusuario_ve_todos(self):
        from agenda.hierarquia import equipe_de

        logins = {m["usuario"].username for m in equipe_de(self.admin)}
        self.assertTrue({"ana", "bia", "gerente", "estranho"} <= logins)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("agenda:calendario"), {"usuario": self.ana.id}).status_code, 200)
