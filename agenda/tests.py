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


class _Base(TestCase):
    """Pessoas com cadeia de liderança para os testes de compartilhamento."""

    def setUp(self):
        from django.core.cache import cache

        from rh.models import Colaborador

        cache.clear()
        self.cont = 0

        def mk(login, **vinc):
            self.cont += 1
            u = User.objects.create_user(login, password="x", first_name=login.title())
            c = Colaborador.objects.create(user_django=u, matricula=f"S{self.cont}", nome_completo=f"Pessoa {login}", grupo="G", **vinc)
            return u, c

        self.lider, cl = mk("lider")
        self.ana, _ = mk("ana", lider=cl)
        self.bia, _ = mk("bia", lider=cl)
        self.outro, _ = mk("outro")  # fora da equipe do líder

        # como no painel de permissões: acesso ao módulo Agenda (sem a especial "criar na Agenda Comum")
        from django.contrib.auth.models import Permission

        perms = Permission.objects.filter(content_type__app_label="core", codename__startswith="nav_").filter(
            codename__regex=r"^nav_(mod_agenda|mod_gestao|gestao_ferramentas|agenda_(?!criar_comum))"
        )
        for u in (self.lider, self.ana, self.bia, self.outro):
            u.user_permissions.add(*perms)
        self.lider, self.ana, self.bia, self.outro = (User.objects.get(pk=u.pk) for u in (self.lider, self.ana, self.bia, self.outro))

    def post(self, nome, corpo, args=None):
        return self.client.post(reverse(nome, args=args or []), json.dumps(corpo), content_type="application/json")


class ChecklistEnviadoALideradosTests(_Base):
    def _enviar(self, para, **extra):
        corpo = {"titulo": "Abertura", "itens": [{"texto": "Ligar"}, {"texto": "Conferir"}, {"texto": "Registrar"}],
                 "diario": True, "dias_semana": [0, 1, 2, 3, 4, 5, 6], "compartilhar_com": [u.id for u in para], "incluir_dono": False}
        corpo.update(extra)
        return self.post("agenda:checklist_salvar", corpo)

    def test_chefia_envia_e_cada_liderado_preenche_a_sua_folha(self):
        from agenda.models import Checklist, ChecklistDiarioConclusao
        from agenda.services import checklist_do_dia

        self.client.force_login(self.lider)
        self.assertTrue(self._enviar([self.ana, self.bia]).json()["success"])
        c = Checklist.objects.get()
        hoje = timezone.localdate()
        self.assertEqual(checklist_do_dia(self.lider, hoje), [])  # não preenche (incluir_dono=False)
        for u in (self.ana, self.bia):
            occ = checklist_do_dia(u, hoje)
            self.assertEqual((len(occ), len(occ[0]["itens"]), occ[0]["origem"]), (1, 3, "Lider"))
            self.assertFalse(occ[0]["editavel"])
        # a Ana marca; a folha da Bia continua vazia
        item = c.itens.first()
        self.client.force_login(self.ana)
        r = self.post("agenda:api_diario_toggle", {"data": hoje.isoformat()}, [c.id, item.id])
        self.assertTrue(r.json()["feito"])
        self.assertEqual(ChecklistDiarioConclusao.objects.filter(usuario=self.ana).count(), 1)
        self.assertEqual(sum(1 for x in checklist_do_dia(self.bia, hoje)[0]["itens"] if x["feito"]), 0)
        # a chefia vê o andamento de cada um na tela Equipe
        self.client.force_login(self.lider)
        linhas = {l["nome"]: l for l in self.client.get(reverse("agenda:equipe")).context["linhas"]}
        self.assertEqual((linhas["Pessoa ana"]["feitos"], linhas["Pessoa ana"]["total"]), (1, 3))
        self.assertEqual((linhas["Pessoa bia"]["feitos"], linhas["Pessoa bia"]["total"]), (0, 3))

    def test_nao_retroage_antes_do_envio(self):
        from agenda.services import checklists_diarios

        self.client.force_login(self.lider)
        self._enviar([self.ana])
        ontem = timezone.localdate() - timedelta(days=1)
        self.assertEqual(checklists_diarios(self.ana, ontem, ontem), [])

    def test_so_envia_para_liderados(self):
        self.client.force_login(self.lider)
        self.assertEqual(self._enviar([self.outro]).status_code, 403)  # fora da equipe
        self.client.force_login(self.ana)  # quem não é chefia de ninguém
        self.assertEqual(self._enviar([self.bia]).status_code, 403)

    def test_enviar_exige_checklist_diario_e_dono_recebe_se_nao_ha_destinatario(self):
        from agenda.models import Checklist

        self.client.force_login(self.lider)
        self.assertEqual(self._enviar([self.ana], diario=False).status_code, 400)
        self.assertTrue(self._enviar([], incluir_dono=False).json()["success"])
        self.assertTrue(Checklist.objects.get().incluir_dono)  # sem destinatários, volta a ser do dono

    def test_retirar_destinatario_e_recebido_na_tela(self):
        from agenda.models import Checklist, ChecklistCompartilhamento

        self.client.force_login(self.lider)
        self._enviar([self.ana, self.bia])
        c = Checklist.objects.get()
        self._enviar([self.ana], id=c.id)
        self.assertEqual(list(ChecklistCompartilhamento.objects.values_list("usuario__username", flat=True)), ["ana"])
        self.client.force_login(self.ana)
        r = self.client.get(reverse("agenda:checklists"))
        self.assertContains(r, "Recebidos de chefias")
        self.assertContains(r, "Enviado por Lider")
        # quem recebeu não edita a proposta da chefia
        self.assertEqual(self.client.get(reverse("agenda:api_checklist_detalhe", args=[c.id])).status_code, 404)
        self.assertEqual(self.post("agenda:checklist_salvar", {"id": c.id, "titulo": "X", "itens": [{"texto": "a"}]}).status_code, 404)

    def test_inbox_do_liderado_mostra_a_proposta_em_acoes(self):
        from shared.inbox import get_user_inbox_items

        self.client.force_login(self.lider)
        self._enviar([self.ana])
        itens = [(i.title, i.description) for i in get_user_inbox_items(self.ana) if i.module == "Agenda"]
        self.assertEqual(itens, [("Checklist: Abertura", "0 de 3 itens")])


class ChecklistCompartilhadoTests(_Base):
    def _criar(self, membros=None, **extra):
        corpo = {
            "titulo": "Preparar auditoria",
            "membros": [u.id for u in (membros if membros is not None else [self.ana, self.bia])],
            "tarefas": [
                {"texto": "Reunir evidências", "responsavel": self.ana.id, "prazo": "2026-01-10"},
                {"texto": "Revisar procedimentos", "responsavel": self.bia.id, "prazo": ""},
                {"texto": "Sem dono"},
            ],
        }
        corpo.update(extra)
        return self.post("agenda:compartilhado_salvar", corpo)

    def test_criar_com_varias_acoes_e_membros(self):
        from agenda.models import ChecklistCompartilhado

        self.client.force_login(self.lider)
        self.assertTrue(self._criar().json()["success"])
        lista = ChecklistCompartilhado.objects.get()
        self.assertEqual(lista.tarefas.count(), 3)
        self.assertEqual(set(lista.membros.values_list("usuario__username", flat=True)), {"lider", "ana", "bia"})  # criador é membro
        self.assertEqual(self.post("agenda:compartilhado_salvar", {"titulo": "x", "tarefas": []}).status_code, 400)  # sem itens
        self.assertEqual(self.post("agenda:compartilhado_salvar", {"titulo": " ", "tarefas": [{"texto": "a"}]}).status_code, 400)

    def test_responsavel_precisa_ser_membro(self):
        self.client.force_login(self.lider)
        r = self._criar(membros=[self.ana])  # a Bia é responsável de uma item mas não é membro
        self.assertEqual(r.status_code, 400)

    def test_visibilidade(self):
        from agenda.models import ChecklistCompartilhado

        self.client.force_login(self.lider)
        self._criar(membros=[self.ana])  # tarefa da Bia vai dar erro; ajusta
        ChecklistCompartilhado.objects.all().delete()
        self._criar(membros=[self.ana, self.bia])
        lista = ChecklistCompartilhado.objects.get()
        for u, esperado in ((self.lider, 200), (self.ana, 200), (self.bia, 200), (self.outro, 404)):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("agenda:compartilhado_detalhe", args=[lista.id])).status_code, esperado, u.username)
        self.client.force_login(self.outro)
        self.assertNotContains(self.client.get(reverse("agenda:compartilhados")), "Preparar auditoria")

    def test_qualquer_membro_conclui_e_fica_registrado_quem(self):
        from agenda.models import CompartilhadoTarefa

        self.client.force_login(self.lider)
        self._criar()
        t = CompartilhadoTarefa.objects.get(texto="Reunir evidências")  # responsável: Ana
        self.client.force_login(self.bia)  # a Bia (não é a responsável) conclui para o grupo
        self.assertTrue(self.post("agenda:api_tarefa_toggle", {}, [t.id]).json()["concluida"])
        t.refresh_from_db()
        self.assertEqual((t.concluida, t.concluida_por), (True, self.bia))
        self.assertIsNotNone(t.concluida_em)
        self.assertContains(self.client.get(reverse("agenda:compartilhado_detalhe", args=[t.lista_id])), "Bia")
        self.assertFalse(self.post("agenda:api_tarefa_toggle", {}, [t.id]).json()["concluida"])  # reabre
        t.refresh_from_db()
        self.assertIsNone(t.concluida_por)
        self.client.force_login(self.outro)
        self.assertEqual(self.post("agenda:api_tarefa_toggle", {}, [t.id]).status_code, 404)  # de fora não conclui

    def test_cobrar_gera_aviso_no_sino_do_responsavel(self):
        from agenda.models import CompartilhadoCobranca, CompartilhadoTarefa
        from shared.inbox import get_user_inbox_items

        self.client.force_login(self.lider)
        self._criar()
        t = CompartilhadoTarefa.objects.get(texto="Reunir evidências")  # responsável: Ana
        self.client.force_login(self.bia)
        self.assertTrue(self.post("agenda:api_tarefa_cobrar", {}, [t.id]).json()["success"])
        self.assertEqual(self.post("agenda:api_tarefa_cobrar", {}, [t.id]).status_code, 429)  # uma cobrança por dia
        self.assertEqual(CompartilhadoCobranca.objects.count(), 1)
        titulos = [i.title for i in get_user_inbox_items(self.ana) if i.module == "Agenda"]
        self.assertIn("Cobrança: Reunir evidências", titulos)
        # a Ana abre o checklist: a cobrança sai do sino
        self.client.force_login(self.ana)
        self.client.get(reverse("agenda:compartilhado_detalhe", args=[t.lista_id]))
        self.assertNotIn("Cobrança: Reunir evidências", [i.title for i in get_user_inbox_items(self.ana)])

    def test_regras_de_cobranca(self):
        from agenda.models import CompartilhadoTarefa

        self.client.force_login(self.lider)
        self._criar()
        propria = CompartilhadoTarefa.objects.get(texto="Reunir evidências")  # da Ana
        sem_dono = CompartilhadoTarefa.objects.get(texto="Sem dono")
        self.client.force_login(self.ana)
        self.assertEqual(self.post("agenda:api_tarefa_cobrar", {}, [propria.id]).status_code, 400)  # não cobra a si mesma
        self.assertEqual(self.post("agenda:api_tarefa_cobrar", {}, [sem_dono.id]).status_code, 400)  # sem responsável
        self.post("agenda:api_tarefa_toggle", {}, [propria.id])
        self.client.force_login(self.bia)
        self.assertEqual(self.post("agenda:api_tarefa_cobrar", {}, [propria.id]).status_code, 400)  # já concluída
        self.client.force_login(self.outro)
        self.assertEqual(self.post("agenda:api_tarefa_cobrar", {}, [propria.id]).status_code, 404)  # de fora

    def test_aviso_automatico_de_acao_atrasada_e_do_dia(self):
        from shared.inbox import get_user_inbox_items

        hoje = timezone.localdate()
        self.client.force_login(self.lider)
        self.post("agenda:compartilhado_salvar", {"titulo": "L", "membros": [self.ana.id], "tarefas": [
            {"texto": "Vencida", "responsavel": self.ana.id, "prazo": (hoje - timedelta(days=2)).isoformat()},
            {"texto": "Hoje", "responsavel": self.ana.id, "prazo": hoje.isoformat()},
            {"texto": "Futura", "responsavel": self.ana.id, "prazo": (hoje + timedelta(days=5)).isoformat()},
        ]})
        itens = {i.title: i.is_urgent for i in get_user_inbox_items(self.ana) if i.module == "Agenda"}
        self.assertEqual(itens, {"Item atrasado: Vencida": True, "Item para hoje: Hoje": False})

    def test_so_criador_ou_chefia_edita_e_exclui(self):
        from agenda.models import ChecklistCompartilhado

        self.client.force_login(self.ana)  # a Ana cria; o líder dela é chefia dela; a Bia é só membro
        self.post("agenda:compartilhado_salvar", {"titulo": "Da Ana", "membros": [self.bia.id], "tarefas": [{"texto": "A"}]})
        lista = ChecklistCompartilhado.objects.get()
        self.client.force_login(self.bia)
        self.assertEqual(self.post("agenda:compartilhado_salvar", {"id": lista.id, "titulo": "Hack", "tarefas": [{"texto": "x"}]}).status_code, 403)
        self.assertEqual(self.post("agenda:compartilhado_excluir", {}, [lista.id]).status_code, 403)
        self.assertEqual(self.client.get(reverse("agenda:api_compartilhado_detalhe", args=[lista.id])).status_code, 404)
        self.client.force_login(self.lider)  # chefia da criadora ajusta
        self.assertTrue(self.post("agenda:compartilhado_salvar", {"id": lista.id, "titulo": "Ajustado", "membros": [self.bia.id], "tarefas": [{"texto": "A"}]}).json()["success"])
        self.assertTrue(self.post("agenda:compartilhado_excluir", {}, [lista.id]).json()["success"])
        self.assertEqual(ChecklistCompartilhado.objects.count(), 0)

    def test_editar_preserva_acoes_existentes_e_remove_retiradas(self):
        from agenda.models import CompartilhadoTarefa

        self.client.force_login(self.lider)
        self._criar()
        lista_id = CompartilhadoTarefa.objects.first().lista_id
        a, b, c = list(CompartilhadoTarefa.objects.all())
        self.post("agenda:compartilhado_salvar", {"id": lista_id, "titulo": "T", "membros": [self.ana.id, self.bia.id], "tarefas": [
            {"id": b.id, "texto": "Revisar (ajustada)", "responsavel": self.bia.id}, {"texto": "Novo item"}]})
        self.assertEqual(sorted(CompartilhadoTarefa.objects.values_list("texto", flat=True)), ["Novo item", "Revisar (ajustada)"])
        self.assertTrue(CompartilhadoTarefa.objects.filter(id=b.id).exists())

    def test_retirar_membro_limpa_responsavel_e_paginas_renderizam(self):
        from agenda.models import CompartilhadoTarefa

        self.client.force_login(self.lider)
        self._criar()
        lista_id = CompartilhadoTarefa.objects.first().lista_id
        self.post("agenda:compartilhado_salvar", {"id": lista_id, "titulo": "T", "membros": [self.bia.id], "tarefas": [
            {"texto": "X", "responsavel": self.bia.id}]})
        self.assertEqual(self.client.get(reverse("agenda:compartilhados")).status_code, 200)
        r = self.client.get(reverse("agenda:compartilhado_detalhe", args=[lista_id]))
        self.assertContains(r, "Pendências por pessoa")
        self.assertEqual(self.client.get(reverse("agenda:api_compartilhado_detalhe", args=[lista_id])).json()["lista"]["criador"]["id"], self.lider.id)

    def test_equipe_mostra_acoes_pendentes_do_liderado(self):
        hoje = timezone.localdate()
        self.client.force_login(self.lider)
        self.post("agenda:compartilhado_salvar", {"titulo": "L", "membros": [self.ana.id], "tarefas": [
            {"texto": "Atrasada", "responsavel": self.ana.id, "prazo": (hoje - timedelta(days=1)).isoformat()},
            {"texto": "No prazo", "responsavel": self.ana.id}]})
        linhas = {l["nome"]: l for l in self.client.get(reverse("agenda:equipe")).context["linhas"]}
        self.assertEqual((linhas["Pessoa ana"]["acoes_pendentes"], linhas["Pessoa ana"]["acoes_atrasadas"]), (2, 1))


class AgrupamentosTests(_Base):
    """Checklists têm agrupamentos e, dentro deles, os itens que são acompanhados e marcados."""

    def _checklist(self, **extra):
        corpo = {
            "titulo": "Abertura do laboratório", "diario": True, "dias_semana": [0, 1, 2, 3, 4, 5, 6],
            "itens": [
                {"texto": "Ligar equipamentos", "grupo": "Equipamentos"},
                {"texto": "Calibrar balança", "grupo": "Equipamentos"},
                {"texto": "Conferir EPIs", "grupo": "Segurança"},
                {"texto": "Item solto", "grupo": ""},
            ],
        }
        corpo.update(extra)
        return self.post("agenda:checklist_salvar", corpo)

    def test_salva_e_devolve_agrupamentos_na_ordem(self):
        from agenda.models import Checklist

        self.client.force_login(self.ana)
        self.assertTrue(self._checklist().json()["success"])
        c = Checklist.objects.get()
        self.assertEqual([(i.grupo, i.texto) for i in c.itens.all()],
                         [("Equipamentos", "Ligar equipamentos"), ("Equipamentos", "Calibrar balança"), ("Segurança", "Conferir EPIs"), ("", "Item solto")])
        det = self.client.get(reverse("agenda:api_checklist_detalhe", args=[c.id])).json()["checklist"]
        self.assertEqual([i["grupo"] for i in det["itens"]], ["Equipamentos", "Equipamentos", "Segurança", ""])

    def test_checklist_do_dia_agrupa_e_conta_por_agrupamento(self):
        from agenda.models import Checklist
        from agenda.services import checklist_do_dia

        self.client.force_login(self.ana)
        self._checklist()
        c = Checklist.objects.get()
        hoje = timezone.localdate()
        for it in list(c.itens.all())[:2]:  # conclui os dois itens de "Equipamentos"
            self.post("agenda:api_diario_toggle", {"data": hoje.isoformat()}, [c.id, it.id])
        grupos = checklist_do_dia(self.ana, hoje)[0]["grupos"]
        self.assertEqual([(g["nome"], g["feitos"], g["total"]) for g in grupos], [("Equipamentos", 2, 2), ("Segurança", 0, 1), ("", 0, 1)])
        r = self.client.get(reverse("agenda:checklist"))
        self.assertContains(r, "Equipamentos")
        self.assertContains(r, "Segurança")
        self.assertContains(r, '<span id="ckFeitos">2</span> de 4 concluídos')

    def test_renomear_agrupamento_preserva_marcacoes(self):
        from agenda.models import Checklist, ChecklistDiarioConclusao

        self.client.force_login(self.ana)
        self._checklist()
        c = Checklist.objects.get()
        item = c.itens.first()
        self.post("agenda:api_diario_toggle", {"data": timezone.localdate().isoformat()}, [c.id, item.id])
        itens = [{"id": i.id, "texto": i.texto, "grupo": "Máquinas" if i.grupo == "Equipamentos" else i.grupo} for i in c.itens.all()]
        self._checklist(id=c.id, itens=itens)
        self.assertEqual(ChecklistDiarioConclusao.objects.count(), 1)  # a marcação do item continua valendo
        self.assertEqual(set(c.itens.values_list("grupo", flat=True)), {"Máquinas", "Segurança", ""})

    def test_agrupamento_longo_e_cortado(self):
        from agenda.models import Checklist

        self.client.force_login(self.ana)
        self._checklist(itens=[{"texto": "a", "grupo": "x" * 500}])
        self.assertEqual(len(Checklist.objects.get().itens.get().grupo), 120)

    def test_checklist_enviado_a_liderados_leva_os_agrupamentos(self):
        from agenda.services import checklist_do_dia

        self.client.force_login(self.lider)
        self._checklist(compartilhar_com=[self.ana.id], incluir_dono=False)
        grupos = checklist_do_dia(self.ana, timezone.localdate())[0]["grupos"]
        self.assertEqual([g["nome"] for g in grupos], ["Equipamentos", "Segurança", ""])

    def test_compartilhado_com_agrupamentos(self):
        from agenda.models import ChecklistCompartilhado, CompartilhadoTarefa

        self.client.force_login(self.lider)
        corpo = {"titulo": "Auditoria", "membros": [self.ana.id], "tarefas": [
            {"texto": "Reunir registros", "grupo": "Documentos", "responsavel": self.ana.id},
            {"texto": "Revisar POPs", "grupo": "Documentos"},
            {"texto": "Preparar sala", "grupo": "Logística", "responsavel": self.lider.id},
        ]}
        self.assertTrue(self.post("agenda:compartilhado_salvar", corpo).json()["success"])
        lista = ChecklistCompartilhado.objects.get()
        self.assertEqual([(t.grupo, t.texto) for t in lista.tarefas.all()],
                         [("Documentos", "Reunir registros"), ("Documentos", "Revisar POPs"), ("Logística", "Preparar sala")])
        det = self.client.get(reverse("agenda:api_compartilhado_detalhe", args=[lista.id])).json()["lista"]
        self.assertEqual([t["grupo"] for t in det["tarefas"]], ["Documentos", "Documentos", "Logística"])
        # conclui um item de "Documentos" e confere o progresso por agrupamento na página
        t1 = CompartilhadoTarefa.objects.get(texto="Reunir registros")
        self.post("agenda:api_tarefa_toggle", {}, [t1.id])
        r = self.client.get(reverse("agenda:compartilhado_detalhe", args=[lista.id]))
        self.assertEqual([(g["nome"], g["feitas"], g["total"]) for g in r.context["grupos"]], [("Documentos", 1, 2), ("Logística", 0, 1)])
        self.assertContains(r, "Logística")


class ChecklistPeriodicidadeTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.a = User.objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(self.a)

    def _ck(self, **kw):
        from agenda.models import Checklist, ChecklistItem

        base = dict(titulo="P", criado_por=self.a, diario=True, diario_desde=date(2026, 1, 5))  # segunda
        base.update(kw)
        c = Checklist.objects.create(**base)
        ChecklistItem.objects.create(checklist=c, texto="x")
        return c

    def _dias(self, c, de, ate):
        from agenda.services import checklists_diarios

        return [o["dia"] for o in checklists_diarios(self.a, de, ate) if o["checklist_id"] == c.id]

    def test_semanal_so_no_dia_escolhido(self):
        c = self._ck(periodicidade="semanal", dias_semana="2")
        self.assertEqual(self._dias(c, date(2026, 1, 5), date(2026, 1, 25)), [date(2026, 1, 7), date(2026, 1, 14), date(2026, 1, 21)])

    def test_quinzenal_a_cada_duas_semanas(self):
        c = self._ck(periodicidade="quinzenal", dias_semana="0,4")
        self.assertEqual(
            self._dias(c, date(2026, 1, 5), date(2026, 2, 1)),
            [date(2026, 1, 5), date(2026, 1, 9), date(2026, 1, 19), date(2026, 1, 23)],
        )

    def test_mensal_usa_ultimo_dia_em_mes_curto(self):
        c = self._ck(periodicidade="mensal", dia_mes=31)
        self.assertEqual(
            self._dias(c, date(2026, 1, 5), date(2026, 4, 30)),
            [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)],
        )

    def test_trimestral_e_anual(self):
        c = self._ck(periodicidade="trimestral", dia_mes=10)
        self.assertEqual(self._dias(c, date(2026, 1, 5), date(2026, 12, 31)), [date(2026, 1, 10), date(2026, 4, 10), date(2026, 7, 10), date(2026, 10, 10)])
        a = self._ck(periodicidade="anual", dia_mes=5)
        self.assertEqual(self._dias(a, date(2026, 1, 1), date(2028, 12, 31)), [date(2026, 1, 5), date(2027, 1, 5), date(2028, 1, 5)])

    def test_salvar_e_detalhe(self):
        from agenda.models import Checklist

        corpo = {"titulo": "Mensal", "itens": [{"texto": "a"}], "diario": True, "periodicidade": "mensal", "dia_mes": 15}
        r = self.client.post(reverse("agenda:checklist_salvar"), json.dumps(corpo), content_type="application/json")
        self.assertTrue(r.json()["success"])
        c = Checklist.objects.get()
        self.assertEqual((c.periodicidade, c.dia_mes), ("mensal", 15))
        d = self.client.get(reverse("agenda:api_checklist_detalhe", args=[c.id])).json()["checklist"]
        self.assertEqual((d["periodicidade"], d["dia_mes"]), ("mensal", 15))
        for ruim in ({"dia_mes": 40}, {"dia_mes": None}, {"periodicidade": "x"}):
            r = self.client.post(reverse("agenda:checklist_salvar"), json.dumps({**corpo, **ruim}), content_type="application/json")
            self.assertEqual(r.status_code, 400)
        quinz = {**corpo, "periodicidade": "quinzenal", "dias_semana": []}
        self.assertEqual(self.client.post(reverse("agenda:checklist_salvar"), json.dumps(quinz), content_type="application/json").status_code, 400)


class RegrasTests(TestCase):
    """Regras de condição especial dos agrupamentos (agenda.regras)."""

    def test_dia_do_mes_com_clamp_e_intervalo_de_meses(self):
        from agenda.regras import aplica

        r = {"tipo": "dia_mes", "dia": 5, "n": 1}
        self.assertTrue(aplica(r, date(2026, 3, 5), date(2026, 1, 1)))
        self.assertFalse(aplica(r, date(2026, 3, 6), date(2026, 1, 1)))
        # dia 31 em mês curto cai no último dia
        r31 = {"tipo": "dia_mes", "dia": 31, "n": 1}
        self.assertTrue(aplica(r31, date(2026, 2, 28), date(2026, 1, 1)))
        self.assertFalse(aplica(r31, date(2026, 2, 27), date(2026, 1, 1)))
        # a cada 2 meses a partir de janeiro: jan, mar, mai...
        r2 = {"tipo": "dia_mes", "dia": 10, "n": 2}
        self.assertEqual([aplica(r2, date(2026, m, 10), date(2026, 1, 15)) for m in (1, 2, 3, 4, 5)], [True, False, True, False, True])

    def test_ultimo_dia_do_mes(self):
        from agenda.regras import aplica

        r = {"tipo": "ultimo_dia_mes", "n": 1}
        self.assertTrue(aplica(r, date(2026, 2, 28), date(2026, 1, 1)))
        self.assertTrue(aplica(r, date(2024, 2, 29), date(2024, 1, 1)))  # bissexto
        self.assertFalse(aplica(r, date(2026, 2, 27), date(2026, 1, 1)))

    def test_dias_da_semana_e_cada_n_dias(self):
        from agenda.regras import aplica

        seg_qua = {"tipo": "dias_semana", "dias": [0, 2]}
        self.assertEqual([aplica(seg_qua, date(2026, 1, d), None) for d in (5, 6, 7)], [True, False, True])  # seg, ter, qua
        c3 = {"tipo": "cada_dias", "n": 3}
        ref = date(2026, 1, 1)
        self.assertEqual([aplica(c3, date(2026, 1, d), ref) for d in (1, 2, 3, 4, 7)], [True, False, False, True, True])
        self.assertFalse(aplica(c3, date(2025, 12, 29), ref))  # antes da referência

    def test_enesima_semana_do_mes(self):
        from agenda.regras import aplica

        seg1 = {"tipo": "semana_mes", "nth": 1, "dia": 0, "n": 1}  # 1ª segunda
        self.assertTrue(aplica(seg1, date(2026, 1, 5), date(2026, 1, 1)))
        self.assertFalse(aplica(seg1, date(2026, 1, 12), date(2026, 1, 1)))
        ult_sex = {"tipo": "semana_mes", "nth": -1, "dia": 4, "n": 1}  # última sexta
        self.assertTrue(aplica(ult_sex, date(2026, 1, 30), date(2026, 1, 1)))
        self.assertFalse(aplica(ult_sex, date(2026, 1, 23), date(2026, 1, 1)))

    def test_sempre_e_vazio(self):
        from agenda.regras import aplica

        self.assertTrue(aplica(None, date(2026, 1, 1), None))
        self.assertTrue(aplica({"tipo": "sempre"}, date(2026, 1, 1), None))

    def test_normaliza_valida(self):
        from agenda.regras import normaliza

        self.assertEqual(normaliza(None), {"tipo": "sempre"})
        self.assertEqual(normaliza({"tipo": "dia_mes", "dia": "5", "n": "2", "lixo": 1}), {"tipo": "dia_mes", "n": 2, "dia": 5})
        for ruim in ({"tipo": "x"}, {"tipo": "dia_mes", "dia": 40}, {"tipo": "dia_mes"}, {"tipo": "dias_semana", "dias": []},
                     {"tipo": "cada_dias", "n": 0}, {"tipo": "semana_mes", "dia": 1, "nth": 0}, {"tipo": "semana_mes", "dia": 9, "nth": 1}, "texto"):
            with self.assertRaises(ValueError):
                normaliza(ruim)

    def test_descrever(self):
        from agenda.regras import descrever

        self.assertEqual(descrever({"tipo": "dia_mes", "dia": 5, "n": 1}), "no dia 5 do mês")
        self.assertEqual(descrever({"tipo": "dia_mes", "dia": 5, "n": 3}), "no dia 5 do mês (a cada 3 meses)")
        self.assertEqual(descrever({"tipo": "ultimo_dia_mes", "n": 1}), "no último dia do mês")
        self.assertEqual(descrever({"tipo": "semana_mes", "nth": -1, "dia": 4, "n": 1}), "na última sexta do mês")
        self.assertEqual(descrever({"tipo": "dias_semana", "dias": [0, 4]}), "em seg, sex")
        self.assertEqual(descrever({"tipo": "cada_dias", "n": 15}), "a cada 15 dias")
        self.assertEqual(descrever(None), "")


class FrequenciaIntervaloLivreTests(TestCase):
    """Periodicidades 'a cada N dias/semanas/meses/anos'."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.a = User.objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(self.a)

    def _ck(self, **kw):
        from agenda.models import Checklist, ChecklistItem

        base = dict(titulo="P", criado_por=self.a, diario=True, diario_desde=date(2026, 1, 5))  # segunda
        base.update(kw)
        c = Checklist.objects.create(**base)
        ChecklistItem.objects.create(checklist=c, texto="x")
        return c

    def _dias(self, c, de, ate):
        from agenda.services import checklists_diarios

        return [o["dia"] for o in checklists_diarios(self.a, de, ate) if o["checklist_id"] == c.id]

    def test_a_cada_15_dias(self):
        c = self._ck(periodicidade="cada_dias", intervalo=15)
        self.assertEqual(self._dias(c, date(2026, 1, 1), date(2026, 3, 10)),
                         [date(2026, 1, 5), date(2026, 1, 20), date(2026, 2, 4), date(2026, 2, 19), date(2026, 3, 6)])
        # janela que começa no meio do ciclo continua alinhada com a referência
        self.assertEqual(self._dias(c, date(2026, 2, 1), date(2026, 2, 28)), [date(2026, 2, 4), date(2026, 2, 19)])

    def test_a_cada_3_semanas_nos_dias_marcados(self):
        c = self._ck(periodicidade="cada_semanas", intervalo=3, dias_semana="0,4")
        self.assertEqual(self._dias(c, date(2026, 1, 5), date(2026, 2, 28)),
                         [date(2026, 1, 5), date(2026, 1, 9), date(2026, 1, 26), date(2026, 1, 30), date(2026, 2, 16), date(2026, 2, 20)])

    def test_a_cada_2_meses_no_dia_10(self):
        c = self._ck(periodicidade="cada_meses", intervalo=2, dia_mes=10)
        self.assertEqual(self._dias(c, date(2026, 1, 5), date(2026, 7, 31)),
                         [date(2026, 1, 10), date(2026, 3, 10), date(2026, 5, 10), date(2026, 7, 10)])

    def test_a_cada_2_anos(self):
        c = self._ck(periodicidade="cada_anos", intervalo=2, dia_mes=5)
        self.assertEqual(self._dias(c, date(2026, 1, 1), date(2030, 12, 31)), [date(2026, 1, 5), date(2028, 1, 5), date(2030, 1, 5)])

    def test_intervalo_1_equivale_ao_comum(self):
        c = self._ck(periodicidade="cada_dias", intervalo=1)
        self.assertEqual(len(self._dias(c, date(2026, 1, 5), date(2026, 1, 11))), 7)

    def test_frequencia_texto(self):
        from agenda.models import Checklist

        t = lambda **k: Checklist(**k).frequencia_texto  # noqa: E731
        self.assertEqual(t(periodicidade="cada_dias", intervalo=15), "A cada 15 dias")
        self.assertEqual(t(periodicidade="cada_meses", intervalo=3, dia_mes=10), "A cada 3 meses · dia 10")
        self.assertEqual(t(periodicidade="cada_semanas", intervalo=2), "A cada 2 semanas")
        self.assertEqual(t(periodicidade="mensal", dia_mes=5), "Mensal · dia 5")
        self.assertEqual(t(periodicidade="cada_anos", intervalo=1), "Anual")

    def test_salvar_com_intervalo_e_data_de_inicio(self):
        from agenda.models import Checklist

        corpo = {"titulo": "Quinzena", "itens": [{"texto": "a"}], "diario": True, "periodicidade": "cada_dias", "intervalo": 15, "desde": "2026-03-01"}
        r = self.client.post(reverse("agenda:checklist_salvar"), json.dumps(corpo), content_type="application/json")
        self.assertTrue(r.json()["success"])
        c = Checklist.objects.get()
        self.assertEqual((c.periodicidade, c.intervalo, c.diario_desde), ("cada_dias", 15, date(2026, 3, 1)))
        d = self.client.get(reverse("agenda:api_checklist_detalhe", args=[c.id])).json()["checklist"]
        self.assertEqual((d["intervalo"], d["desde"]), (15, "2026-03-01"))
        for ruim in ({"intervalo": None}, {"intervalo": 0}, {"intervalo": 999}, {"desde": "lixo"}):
            r = self.client.post(reverse("agenda:checklist_salvar"), json.dumps({**corpo, **ruim}), content_type="application/json")
            self.assertEqual(r.status_code, 400, ruim)
        meses = {**corpo, "periodicidade": "cada_meses", "intervalo": 2, "dia_mes": None}
        self.assertEqual(self.client.post(reverse("agenda:checklist_salvar"), json.dumps(meses), content_type="application/json").status_code, 400)


class CondicoesDeAgrupamentoTests(TestCase):
    """Agrupamento com condição especial (ex.: só no 5º dia do mês)."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.a = User.objects.create_superuser("adm", "a@a.com", "x")
        self.client.force_login(self.a)

    def _salvar(self, **extra):
        corpo = {
            "titulo": "Rotina do laboratório", "diario": True, "periodicidade": "diaria", "dias_semana": [0, 1, 2, 3, 4, 5, 6],
            "desde": "2026-01-01",
            "itens": [
                {"texto": "Ligar equipamentos", "grupo": "Diário"},
                {"texto": "Conferir EPIs", "grupo": "Diário"},
                {"texto": "Fechar balanço do mês", "grupo": "Mensal"},
                {"texto": "Arquivar relatórios", "grupo": "Mensal"},
            ],
            "grupos": [{"nome": "Mensal", "regra": {"tipo": "dia_mes", "dia": 5, "n": 1}}, {"nome": "Diário", "regra": {"tipo": "sempre"}}],
        }
        corpo.update(extra)
        return self.client.post(reverse("agenda:checklist_salvar"), json.dumps(corpo), content_type="application/json")

    def _occ(self, dia):
        from agenda.services import checklists_diarios

        return checklists_diarios(self.a, dia, dia)

    def test_agrupamento_so_aparece_no_dia_da_condicao(self):
        self.assertTrue(self._salvar().json()["success"])
        dia5, dia6 = date(2026, 3, 5), date(2026, 3, 6)
        occ5, occ6 = self._occ(dia5)[0], self._occ(dia6)[0]
        self.assertEqual([g["nome"] for g in occ5["grupos"]], ["Diário", "Mensal"])
        self.assertEqual([g["nome"] for g in occ6["grupos"]], ["Diário"])
        self.assertEqual((len(occ5["itens"]), len(occ6["itens"])), (4, 2))
        self.assertEqual([g["condicao"] for g in occ5["grupos"]], ["", "no dia 5 do mês"])

    def test_progresso_conta_so_os_itens_do_dia(self):
        self.assertTrue(self._salvar().json()["success"])
        from agenda.models import Checklist

        c = Checklist.objects.get()
        for it in c.itens.filter(grupo="Diário"):
            self.client.post(reverse("agenda:api_diario_toggle", args=[c.id, it.id]), json.dumps({"data": "2026-03-06"}), content_type="application/json")
        occ = self._occ(date(2026, 3, 6))[0]
        self.assertTrue(occ["feito"])  # no dia 6 só há os 2 itens "Diário", ambos marcados
        self.assertFalse(self._occ(date(2026, 3, 5))[0]["feito"])  # no dia 5 faltam os do agrupamento mensal

    def test_nao_marca_item_de_agrupamento_que_nao_vale_no_dia(self):
        from agenda.models import Checklist

        self._salvar()
        c = Checklist.objects.get()
        mensal = c.itens.filter(grupo="Mensal").first()
        url = reverse("agenda:api_diario_toggle", args=[c.id, mensal.id])
        r = self.client.post(url, json.dumps({"data": "2026-03-06"}), content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.post(url, json.dumps({"data": "2026-03-05"}), content_type="application/json")
        self.assertTrue(r.json()["feito"])

    def test_dia_sem_nenhum_agrupamento_valido_nao_gera_ocorrencia(self):
        itens = [{"texto": "Só no 5º dia", "grupo": "Mensal"}]
        self._salvar(itens=itens, grupos=[{"nome": "Mensal", "regra": {"tipo": "dia_mes", "dia": 5, "n": 1}}])
        self.assertEqual(self._occ(date(2026, 3, 6)), [])
        self.assertEqual(len(self._occ(date(2026, 3, 5))), 1)

    def test_item_sem_agrupamento_aparece_sempre(self):
        itens = [{"texto": "Solto", "grupo": ""}, {"texto": "Mensal", "grupo": "M"}]
        self._salvar(itens=itens, grupos=[{"nome": "M", "regra": {"tipo": "ultimo_dia_mes", "n": 1}}])
        self.assertEqual([i["texto"] for i in self._occ(date(2026, 3, 10))[0]["itens"]], ["Solto"])
        self.assertEqual([i["texto"] for i in self._occ(date(2026, 3, 31))[0]["itens"]], ["Solto", "Mensal"])

    def test_combina_com_a_periodicidade_do_checklist(self):
        # checklist semanal (segundas) + agrupamento "1ª segunda do mês"
        itens = [{"texto": "Semanal", "grupo": ""}, {"texto": "Mensal", "grupo": "M"}]
        self._salvar(itens=itens, periodicidade="semanal", dias_semana=[0], desde="2026-03-02",
                     grupos=[{"nome": "M", "regra": {"tipo": "semana_mes", "nth": 1, "dia": 0, "n": 1}}])
        seg1, seg2 = self._occ(date(2026, 3, 2))[0], self._occ(date(2026, 3, 9))[0]
        self.assertEqual((len(seg1["itens"]), len(seg2["itens"])), (2, 1))
        self.assertEqual(self._occ(date(2026, 3, 3)), [])  # terça: nem o checklist vale

    def test_detalhe_devolve_condicoes_e_renomear_remove_a_regra_antiga(self):
        from agenda.models import Checklist, ChecklistGrupo

        self._salvar()
        c = Checklist.objects.get()
        det = self.client.get(reverse("agenda:api_checklist_detalhe", args=[c.id])).json()["checklist"]
        self.assertEqual(det["condicoes"], {"Mensal": {"tipo": "dia_mes", "dia": 5, "n": 1}})
        itens = [{"id": i.id, "texto": i.texto, "grupo": "Fechamento" if i.grupo == "Mensal" else i.grupo} for i in c.itens.all()]
        self._salvar(id=c.id, itens=itens, grupos=[{"nome": "Fechamento", "regra": {"tipo": "dia_mes", "dia": 7, "n": 1}}])
        self.assertEqual(list(ChecklistGrupo.objects.values_list("nome", flat=True)), ["Fechamento"])
        self._salvar(id=c.id, itens=itens, grupos=[{"nome": "Fechamento", "regra": {"tipo": "sempre"}}])
        self.assertEqual(ChecklistGrupo.objects.count(), 0)  # sem condição não guarda regra

    def test_validacoes_da_condicao(self):
        for regra in ({"tipo": "x"}, {"tipo": "dia_mes", "dia": 99}, {"tipo": "dias_semana", "dias": []}):
            r = self._salvar(grupos=[{"nome": "Mensal", "regra": regra}])
            self.assertEqual(r.status_code, 400, regra)
            self.assertIn("Mensal", r.json()["error"])

    def test_condicao_de_agrupamento_sem_nome_e_ignorada(self):
        from agenda.models import ChecklistGrupo

        self._salvar(itens=[{"texto": "a", "grupo": ""}], grupos=[{"nome": "", "regra": {"tipo": "dia_mes", "dia": 5, "n": 1}}])
        self.assertEqual(ChecklistGrupo.objects.count(), 0)

    def test_checklist_associado_a_evento_tambem_respeita_a_condicao(self):
        from agenda.models import Checklist
        from agenda.services import ocorrencias

        self._salvar()
        c = Checklist.objects.get()
        corpo = {"titulo": "Rotina", "inicio": "2026-03-01T08:00", "dia_inteiro": True, "recorrencia": "diaria", "checklist_modelo": c.id}
        self.client.post(reverse("agenda:evento_salvar"), json.dumps(corpo), content_type="application/json")
        dia5 = [o for o in ocorrencias(self.a, date(2026, 3, 5), date(2026, 3, 5), so_checklist=True)]
        dia6 = [o for o in ocorrencias(self.a, date(2026, 3, 6), date(2026, 3, 6), so_checklist=True)]
        self.assertEqual((len(dia5[0]["itens"]), len(dia6[0]["itens"])), (4, 2))
        from agenda.models import Evento

        ev = Evento.objects.get()
        mensal = c.itens.filter(grupo="Mensal").first()
        r = self.client.post(reverse("agenda:api_item_toggle", args=[ev.id, mensal.id]), json.dumps({"data": "2026-03-06"}), content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_pagina_do_dia_mostra_a_condicao(self):
        self._salvar(desde="2026-03-05")
        r = self.client.get(reverse("agenda:checklist"), {"data": "2026-03-05"})
        self.assertContains(r, "no dia 5 do mês")
        self.assertContains(r, "Fechar balanço do mês")
        r = self.client.get(reverse("agenda:checklist"), {"data": "2026-03-06"})
        self.assertNotContains(r, "Fechar balanço do mês")
