from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from organization.models import Setor
from pcp.models import (Campo, Formulario, FormularioVersao, Frequencia, ListaOpcoes, OpcaoLista, Ocorrencia,
                        Pagina, Resposta, Turno, Verificacao)


class PcpBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('pcp', 'p@x.com', 'x')
        self.client.force_login(self.user)
        self.setor = Setor.objects.create(nome='Surfaçagem')
        self.t1 = Turno.objects.create(nome='Turno 1', sigla='T1', ordem=1)
        self.lista = ListaOpcoes.objects.create(nome='Ok/Nok')
        OpcaoLista.objects.create(lista=self.lista, valor='Ok', ordem=1)
        OpcaoLista.objects.create(lista=self.lista, valor='Nok', conforme=False, ordem=2)
        self.freq = Frequencia.objects.create(nome='Turno', periodicidade='turno')
        self.form = Formulario.objects.create(setor=self.setor, codigo='FOR.080', titulo='Surfaçagem')
        self.v15 = FormularioVersao.objects.create(formulario=self.form, revisao='R15')
        self.pag = Pagina.objects.create(versao=self.v15, nome='Fitadeira', grupo='Fita')
        self.c_lista = Campo.objects.create(pagina=self.pag, item='B-1', descricao='Limpeza', tipo='lista', lista=self.lista, frequencia=self.freq)
        self.c_num = Campo.objects.create(pagina=self.pag, item='B-5', descricao='Vácuo', tipo='numero',
                                          minimo=Decimal('-0.8'), maximo=Decimal('-0.6'), unidade='Bar')


class ModeloTests(PcpBase):
    def test_avaliar_numero_e_lista(self):
        self.assertTrue(self.c_num.avaliar('-0,7'))
        self.assertFalse(self.c_num.avaliar('-0.2'))
        self.assertIsNone(self.c_num.avaliar('abc'))
        self.assertTrue(self.c_lista.avaliar('Ok'))
        self.assertFalse(self.c_lista.avaliar('Nok'))
        self.assertIsNone(self.c_lista.avaliar(''))

    def test_proxima_revisao(self):
        self.assertEqual(self.v15.proxima_revisao(), 'R16')
        self.assertEqual(FormularioVersao(revisao='R09').proxima_revisao(), 'R10')

    def test_publicar_obsoleta_a_anterior(self):
        self.v15.publicar()
        nova = self.v15.clonar('R16')
        nova.publicar()
        self.v15.refresh_from_db()
        self.assertEqual(self.v15.status, 'obsoleta')
        self.assertEqual(nova.status, 'vigente')
        self.assertEqual(self.form.versao_vigente, nova)

    def test_clonar_copia_paginas_e_campos(self):
        nova = self.v15.clonar('R16', self.user, 'ajuste')
        self.assertEqual(nova.status, 'rascunho')
        pag = nova.paginas.get()
        self.assertNotEqual(pag.pk, self.pag.pk)
        self.assertEqual(pag.campos.count(), 2)
        self.assertEqual(self.pag.campos.count(), 2)  # original intacta


class FluxoTests(PcpBase):
    def test_revisao_vigente_nao_edita(self):
        self.v15.publicar()
        r = self.client.post(reverse('pcp:campo_novo', args=[self.pag.pk]), {'descricao': 'X', 'tipo': 'texto', 'ordem': 1})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.pag.campos.count(), 2)

    def test_rascunho_edita_e_publica_pela_tela(self):
        r = self.client.post(reverse('pcp:campo_novo', args=[self.pag.pk]), {
            'descricao': 'Novo', 'tipo': 'texto', 'ordem': 3, 'ativo': 'on'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.pag.campos.count(), 3)
        self.client.post(reverse('pcp:versao_publicar', args=[self.v15.pk]))
        self.v15.refresh_from_db()
        self.assertEqual(self.v15.status, 'vigente')

    def test_nova_revisao_pela_tela_clona(self):
        self.v15.publicar()
        r = self.client.post(reverse('pcp:versao_nova', args=[self.form.pk]), {'revisao': 'R16', 'motivo': 'x'})
        self.assertEqual(r.status_code, 302)
        nova = FormularioVersao.objects.get(revisao='R16')
        self.assertEqual(nova.paginas.get().campos.count(), 2)

    def test_lista_de_opcoes_pela_tela(self):
        r = self.client.post(reverse('pcp:lista_nova'), {'nome': 'Real', 'ativo': 'on', 'opcoes_texto': 'Realizado\nNão realizado | nok'})
        self.assertEqual(r.status_code, 302)
        lista = ListaOpcoes.objects.get(nome='Real')
        self.assertEqual([(o.valor, o.conforme) for o in lista.opcoes.all()], [('Realizado', True), ('Não realizado', False)])

    def test_preencher_salva_conformidade_e_ocorrencia(self):
        self.v15.publicar()
        r = self.client.post(reverse('pcp:preencher_salvar', args=[self.pag.pk]), {
            'data': '2026-10-22', 'turno': self.t1.pk,
            f'c_{self.c_lista.pk}': 'Ok', f'c_{self.c_num.pk}': '-0.2',
            'oc_tipo': 'tratativa', 'oc_campo': self.c_num.pk, 'oc_descricao': 'Vácuo baixo'})
        self.assertEqual(r.status_code, 302)
        ver = Verificacao.objects.get(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        self.assertTrue(Resposta.objects.get(verificacao=ver, campo=self.c_lista).conforme)
        self.assertFalse(Resposta.objects.get(verificacao=ver, campo=self.c_num).conforme)
        oc = Ocorrencia.objects.get(verificacao=ver)
        self.assertTrue(oc.pendente)
        # reenviar atualiza (sem duplicar) e limpa o valor em branco
        self.client.post(reverse('pcp:preencher_salvar', args=[self.pag.pk]), {
            'data': '2026-10-22', 'turno': self.t1.pk, f'c_{self.c_lista.pk}': 'Nok', f'c_{self.c_num.pk}': ''})
        self.assertEqual(Resposta.objects.filter(verificacao=ver).count(), 1)
        self.assertFalse(Resposta.objects.get(verificacao=ver).conforme)

    def test_nao_lanca_em_revisao_nao_vigente(self):
        self.client.post(reverse('pcp:preencher_salvar', args=[self.pag.pk]), {
            'data': '2026-10-22', 'turno': self.t1.pk, f'c_{self.c_lista.pk}': 'Ok'})
        self.assertEqual(Verificacao.objects.count(), 0)

    def test_tratar_ocorrencia(self):
        self.v15.publicar()
        ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        oc = Ocorrencia.objects.create(verificacao=ver, tipo='tratativa', descricao='x')
        self.client.post(reverse('pcp:ocorrencia_tratar', args=[oc.pk]), {'tratativa': 'ajustado'})
        oc.refresh_from_db()
        self.assertEqual(oc.status, 'tratada')
        self.assertFalse(oc.pendente)

    def test_telas_renderizam(self):
        self.v15.publicar()
        ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        Ocorrencia.objects.create(verificacao=ver, tipo='observacao', descricao='obs')
        urls = [
            reverse('pcp:formularios'), reverse('pcp:formulario_detalhe', args=[self.form.pk]),
            reverse('pcp:versao_detalhe', args=[self.v15.pk]), reverse('pcp:pagina_detalhe', args=[self.pag.pk]),
            reverse('pcp:turnos'), reverse('pcp:frequencias'), reverse('pcp:listas'),
            reverse('pcp:preencher'), reverse('pcp:preencher_pagina', args=[self.pag.pk]) + '?data=2026-10-22',
            reverse('pcp:ocorrencias') + '?status=todas',
            reverse('pcp:formulario_novo'), reverse('pcp:versao_nova', args=[self.form.pk]),
            reverse('pcp:turno_novo'), reverse('pcp:lista_editar', args=[self.lista.pk]),
        ]
        for u in urls:
            self.assertEqual(self.client.get(u).status_code, 200, u)
