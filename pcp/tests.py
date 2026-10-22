import io
from datetime import date
from decimal import Decimal

import openpyxl
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from organization.models import Setor
from pcp import pendencias as pend
from pcp.importacao import frequencia_canonica, importar_planilha, parse_arquivo, parse_faixa, parse_mais_menos
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


def _planilha_modelo():
    """Planilha mínima no padrão do FOR.080 (cabeçalho + T1/T2/T3 + itens) com Índice e uma aba ignorada."""
    wb = openpyxl.Workbook()
    wb.active.title = 'Dados'
    ind = wb.create_sheet('Índice')
    ind.append([None, ' ', None, 'Índice Geral - Teste', None, None, None, None, None, 'FOR.999.R03'])
    ind.append([None, 'Fita', None, 'Corte', None, 'Polimento', None, 'Gravação'])
    ind.append([None, 'Fitadeira', None, 'VFT Orbit 1.0 (1)'])
    aba = wb.create_sheet('Fitadeira')
    aba.append(['Voltar ao índice', None, None, 'Fitadeira'])
    aba.append(['Resp', 'item', 'O que verificar', 'Especificações/Tolerancias', 'Método de Verificação', 'Frequencia de Verificação', 'Plano de Reação', '2026-01-01'])
    aba.append([None, None, None, None, None, None, None, 'T1', 'T2', 'T3'])
    aba.append(['Oper.', 'A-1', 'Limpeza dos blocos', 'Sem poeira', 'Visual', 'Pelo menos diariamente', 'Pistola de ar'])
    aba.append([None, 'B-12', 'Temperatura da fita', '10 - 27 ° C', 'Termômetro', 'Turno', 'Sala climatizada'])
    aba.append([None, 'B-13', 'Temperatura do banho', '45°C ± 2°C', 'Painel', 'A cada troca de banho', 'Ajustar'])
    receita = wb.create_sheet('Parâmetro de Receita-ABC')
    receita.append(['Voltar', 'Parâmetro de Receita-ABC'])
    receita.append([None, 'Resp.', 'Frequência', 'Receita', 'Razão', 'Especificação', 'Tolerância (min - max)'])
    receita.append([None, None, 'Mensal', 'Receita X', 'Z0/Z2', 0.05, '0,043 - 0,058'])
    receita.append([None, None, 'Mensal', None, 'Z1/Z2', 0.111, '0,094 - 0,128'])
    wb.create_sheet('D1 (Por Hora)').append(['Data'])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class ImportacaoTests(PcpBase):
    def test_parsers(self):
        self.assertEqual(parse_arquivo('FOR.080.R15 - Formulário Surfaçagem - PCP Latam.xlsx'), ('FOR.080', 'R15', 'Formulário Surfaçagem - PCP Latam'))
        self.assertEqual(parse_faixa('10 - 27 ° C'), (Decimal('10'), Decimal('27'), '° C'))
        self.assertIsNone(parse_faixa('Sem poeira'))
        self.assertEqual(parse_mais_menos('45°C ± 2°C'), (Decimal('43'), Decimal('47'), '°C'))
        self.assertEqual(frequencia_canonica('Pelo menos diariamente')[0], 'Diária')
        self.assertEqual(frequencia_canonica('A cada troca de lâmina')[0], 'Sob demanda / por evento')

    def test_importa_estrutura(self):
        r = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - Formulário Teste.xlsx', setor=self.setor)
        v = r['versao']
        self.assertEqual((str(v), v.status), ('FOR.999.R03', 'rascunho'))
        self.assertEqual(r['total_campos'], 5)
        self.assertEqual([i[0] for i in r['ignoradas']], ['D1 (Por Hora)'])
        fita = v.paginas.get(nome='Fitadeira')
        self.assertEqual(fita.grupo, 'Fita')  # vindo do Índice
        limpeza, temp, banho = fita.campos.all()
        self.assertEqual((limpeza.tipo, limpeza.lista.nome, limpeza.responsavel), ('lista', 'Realizado / Não realizado', 'Oper.'))
        self.assertEqual(limpeza.frequencia.nome, 'Diária')
        self.assertEqual((temp.tipo, temp.minimo, temp.maximo), ('numero', Decimal('10'), Decimal('27')))
        self.assertEqual((banho.minimo, banho.maximo, banho.frequencia.nome), (Decimal('43'), Decimal('47'), 'Sob demanda / por evento'))
        self.assertEqual(banho.frequencia_detalhe, 'A cada troca de banho')
        rec = v.paginas.get(nome='ABC - Receita')
        self.assertEqual(rec.grupo, 'Parâmetro de Receita')
        z1 = rec.campos.get(descricao='Z1/Z2')
        self.assertEqual((z1.etapa, z1.minimo, z1.maximo), ('Receita X', Decimal('0.094'), Decimal('0.128')))

    def test_revisao_repetida_exige_substituir(self):
        importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor)
        with self.assertRaises(ValueError):
            importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor)
        r = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor, substituir=True)
        self.assertEqual(FormularioVersao.objects.filter(revisao='R03').count(), 1)
        self.assertEqual(r['total_campos'], 5)

    def test_nao_substitui_revisao_publicada(self):
        importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor, publicar=True)
        with self.assertRaises(ValueError):
            importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor, substituir=True)

    def test_nome_sem_padrao_exige_codigo(self):
        with self.assertRaises(ValueError):
            importar_planilha(_planilha_modelo(), nome_arquivo='planilha.xlsx', setor=self.setor)

    def test_tela_de_importacao(self):
        self.assertEqual(self.client.get(reverse('pcp:importar')).status_code, 200)
        arq = SimpleUploadedFile('FOR.999.R03 - Teste.xlsx', _planilha_modelo().read())
        r = self.client.post(reverse('pcp:importar'), {'arquivo': arq, 'setor': self.setor.pk})
        v = FormularioVersao.objects.get(revisao='R03')
        self.assertRedirects(r, reverse('pcp:versao_detalhe', args=[v.pk]))
        self.assertEqual(v.status, 'rascunho')
        ruim = SimpleUploadedFile('FOR.998.R01 - X.xlsx', b'nao e um xlsx')
        r = self.client.post(reverse('pcp:importar'), {'arquivo': ruim, 'setor': self.setor.pk})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(FormularioVersao.objects.filter(revisao='R01', formulario__codigo='FOR.998').exists())


class PendenciasTests(PcpBase):
    def setUp(self):
        super().setUp()
        self.t2 = Turno.objects.create(nome='Turno 2', sigla='T2', ordem=2)
        mk = lambda nome, per: Frequencia.objects.create(nome=nome, periodicidade=per)
        self.f_turno, self.f_dia, self.f_sem, self.f_mes, self.f_ev = (
            self.freq, mk('Diária', 'diaria'), mk('Semanal', 'semanal'), mk('Mensal', 'mensal'), mk('Por evento', 'evento'))
        self.c_lista.frequencia = self.f_turno
        self.c_lista.save()
        self.c_num.frequencia = self.f_dia
        self.c_num.save()
        self.c_sem = Campo.objects.create(pagina=self.pag, item='S-1', descricao='Semanal', tipo='texto', frequencia=self.f_sem)
        self.c_mes = Campo.objects.create(pagina=self.pag, item='M-1', descricao='Mensal', tipo='texto', frequencia=self.f_mes)
        self.c_ev = Campo.objects.create(pagina=self.pag, item='E-1', descricao='Evento', tipo='texto', frequencia=self.f_ev)
        self.c_sem0 = Campo.objects.create(pagina=self.pag, item='X-1', descricao='Sem frequencia', tipo='texto')
        self.v15.publicar()
        self.turnos = [self.t1, self.t2]

    def responder(self, dia, turno, campo, valor='Ok', pagina=None):
        ver, _ = Verificacao.objects.get_or_create(pagina=pagina or self.pag, data=dia, turno=turno)
        Resposta.objects.create(verificacao=ver, campo=campo, valor=valor)

    def test_janelas(self):
        d = date(2026, 10, 22)  # quinta-feira
        self.assertEqual(pend.janela('semanal', d), (date(2026, 10, 19), date(2026, 10, 25)))
        self.assertEqual(pend.janela('mensal', d), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(pend.janela('trimestral', d), (date(2026, 10, 1), date(2026, 12, 31)))
        self.assertEqual(pend.janela('semestral', d), (date(2026, 7, 1), date(2026, 12, 31)))
        self.assertEqual(pend.janela('anual', d), (date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(pend.janela('quinzenal', d), (date(2026, 10, 9), d))
        self.assertIsNone(pend.janela('evento', d))

    def test_devidos_e_pendentes(self):
        d = date(2026, 10, 22)
        r = pend.avaliar_pagina(self.pag, d, self.turnos)
        # evento e sem frequência não entram; os 4 demais estão pendentes nos dois turnos
        self.assertEqual(set(r[self.t1.pk]), {self.c_lista.pk, self.c_num.pk, self.c_sem.pk, self.c_mes.pk})
        self.assertFalse(any(r[self.t1.pk].values()))

    def test_cada_periodicidade_cumpre_na_sua_janela(self):
        d = date(2026, 10, 22)
        self.responder(d, self.t1, self.c_lista)           # turno: só T1
        self.responder(d, self.t2, self.c_num, '-0,7')     # diária: vale para os dois turnos
        self.responder(date(2026, 10, 19), self.t1, self.c_sem, 'x')  # semanal: segunda da mesma semana
        self.responder(date(2026, 9, 30), self.t1, self.c_mes, 'x')   # mensal: mês anterior NÃO vale
        r = pend.avaliar_pagina(self.pag, d, self.turnos)
        self.assertTrue(r[self.t1.pk][self.c_lista.pk])
        self.assertFalse(r[self.t2.pk][self.c_lista.pk])
        self.assertTrue(r[self.t1.pk][self.c_num.pk] and r[self.t2.pk][self.c_num.pk])
        self.assertTrue(r[self.t1.pk][self.c_sem.pk])
        self.assertFalse(r[self.t1.pk][self.c_mes.pk])
        self.assertFalse(pend.avaliar_pagina(self.pag, date(2026, 10, 26), self.turnos)[self.t1.pk][self.c_sem.pk])  # semana seguinte

    def test_resposta_em_branco_nao_conta(self):
        d = date(2026, 10, 22)
        self.responder(d, self.t1, self.c_lista, valor='')
        self.assertFalse(pend.avaliar_pagina(self.pag, d, self.turnos)[self.t1.pk][self.c_lista.pk])

    def test_historico_vale_entre_revisoes(self):
        d = date(2026, 10, 22)
        self.responder(date(2026, 10, 5), self.t1, self.c_mes, 'feito')
        nova = self.v15.clonar('R16')
        nova.publicar()
        pag16 = nova.paginas.get()
        self.assertNotEqual(pag16.pk, self.pag.pk)
        r = pend.avaliar_pagina(pag16, d, self.turnos)
        c_mes16 = pag16.campos.get(item='M-1')
        self.assertTrue(r[self.t1.pk][c_mes16.pk])  # mensal já cumprida na revisão anterior

    def test_painel_e_tela(self):
        d = date(2026, 10, 22)
        self.responder(d, self.t1, self.c_lista)
        p = pend.painel(d, self.turnos)
        self.assertEqual((p['devidos'], p['feitos'], p['pendentes']), (8, 1, 7))
        self.assertEqual(p['percentual'], 12)
        r = self.client.get(reverse('pcp:pendencias') + '?data=2026-10-22')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '1/4')  # T1: 1 feita de 4 devidas
        r = self.client.get(reverse('pcp:preencher_pagina', args=[self.pag.pk]) + f'?data=2026-10-22&turno={self.t1.pk}')
        self.assertEqual(r.context['n_devidos'], 4)
        self.assertEqual(r.context['n_pendentes'], 3)
        self.assertContains(r, 'Mostrar só pendentes')
