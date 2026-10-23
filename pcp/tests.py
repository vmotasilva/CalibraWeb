import datetime
import io
from datetime import date, time
from decimal import Decimal

import openpyxl
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from organization.models import Setor
from django.core.cache import cache
from django.utils import timezone

from pcp import cobranca, pendencias as pend
from pcp.importacao_registros import importar_registros
from pcp.importacao import frequencia_canonica, importar_planilha, parse_arquivo, parse_faixa, parse_mais_menos
from pcp.models import (TemplatePagina, AjusteCampo, AjusteVinculo, ValorEquivalente, Campo, Formulario, FormularioVersao, Frequencia, ListaOpcoes, OpcaoLista, Ocorrencia,
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


class PendenciasBase(PcpBase):
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


class PendenciasTests(PendenciasBase):
    def test_janelas(self):
        d = date(2026, 10, 22)  # quinta-feira
        self.assertEqual(pend.janela('semanal', d), (date(2026, 10, 19), date(2026, 10, 25)))
        self.assertEqual(pend.janela('mensal', d), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual(pend.janela('trimestral', d), (date(2026, 10, 1), date(2026, 12, 31)))
        self.assertEqual(pend.janela('semestral', d), (date(2026, 7, 1), date(2026, 12, 31)))
        self.assertEqual(pend.janela('anual', d), (date(2026, 1, 1), date(2026, 12, 31)))
        self.assertEqual(pend.janela('quinzenal', d), (date(2026, 10, 16), date(2026, 10, 31)))
        self.assertEqual(pend.janela('quinzenal', date(2026, 10, 15)), (date(2026, 10, 1), date(2026, 10, 15)))
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
        self.assertContains(r, 'itens pendentes')          # só os itens pendentes, com os turnos em que faltam
        self.assertNotContains(r, '1/4')
        itens = [l for b in p['blocos'] for ls in b['grupos'].values() for l in ls if l['itens']]
        self.assertTrue(itens)
        self.assertEqual(sum(len(l['itens']) for l in itens) > 0, True)
        r = self.client.get(reverse('pcp:preencher_pagina', args=[self.pag.pk]) + f'?data=2026-10-22&turno={self.t1.pk}')
        self.assertEqual(r.context['n_devidos'], 4)
        self.assertEqual(r.context['n_pendentes'], 3)
        self.assertContains(r, 'Mostrar só pendentes')


class CobrancaTests(PendenciasBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.t3 = Turno.objects.create(nome='Turno 3', sigla='T3', ordem=3)
        for t, ini, fim in ((self.t1, time(6), time(14)), (self.t2, time(14), time(22)), (self.t3, time(22), time(6))):
            t.inicio, t.fim = ini, fim
            t.save()

    def agora(self, h, m=0, dia=22):
        return timezone.make_aware(datetime.datetime(2026, 10, dia, h, m))

    def test_turnos_iniciados(self):
        siglas = lambda h: sorted((d.day, t.sigla) for d, t in cobranca.turnos_iniciados(self.agora(h)))
        self.assertEqual(siglas(10), [(22, 'T1')])
        self.assertEqual(siglas(15), [(22, 'T1'), (22, 'T2')])
        self.assertEqual(siglas(23), [(22, 'T1'), (22, 'T2'), (22, 'T3')])
        self.assertEqual(siglas(2), [(21, 'T3')])  # madrugada: T3 que começou ontem

    def test_sem_horario_conta_como_iniciado(self):
        Turno.objects.update(inicio=None, fim=None)
        self.assertEqual(len(cobranca.turnos_iniciados(self.agora(3))), 3)

    def test_pendentes_nao_duplica_itens_nao_por_turno(self):
        # T1 já iniciado: por turno (1) + diária (1) + semanal (1) + mensal (1)
        self.assertEqual(cobranca.pendentes_em_andamento(self.agora(10)), 4)
        # T1 e T2: o item por turno conta 2x; os demais continuam 1x
        self.assertEqual(cobranca.pendentes_em_andamento(self.agora(15)), 5)
        self.responder(date(2026, 10, 22), self.t1, self.c_lista)
        self.assertEqual(cobranca.pendentes_em_andamento(self.agora(15)), 4)

    def test_sino_mostra_itens_para_quem_tem_acesso(self):
        from shared.notifications import get_user_cobrancas_items, get_user_cobrancas_counts
        ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        Ocorrencia.objects.create(verificacao=ver, tipo='tratativa', descricao='x')
        Ocorrencia.objects.create(verificacao=ver, tipo='observacao', descricao='y')
        cache.clear()
        counts = get_user_cobrancas_counts(self.user)
        self.assertEqual(counts['pcp_tratativas'], 1)
        self.assertGreater(counts['pcp_pendencias'], 0)
        chaves = {i.key: i for i in get_user_cobrancas_items(self.user)}
        self.assertEqual(chaves['pcp_tratativas'].count, 1)
        self.assertEqual(chaves['pcp_pendencias'].section, 'PCP')

    def test_turno_exige_inicio_e_fim_juntos(self):
        r = self.client.post(reverse('pcp:turno_novo'), {'nome': 'X', 'sigla': 'X', 'inicio': '06:00', 'ordem': 9, 'ativo': 'on'})
        self.assertEqual(r.status_code, 200)
        r = self.client.post(reverse('pcp:turno_novo'), {'nome': 'X', 'sigla': 'X', 'inicio': '06:00', 'fim': '14:00', 'ordem': 9, 'ativo': 'on'})
        self.assertEqual(r.status_code, 302)


class AtrasosTests(PendenciasBase):
    HOJE = date(2026, 10, 22)

    def setUp(self):
        super().setUp()
        self.v15.vigencia = date(2026, 10, 1)
        self.v15.save()

    def atrasos(self, campo, ini, fim, **kw):
        lista, devidos = pend.atrasos_pagina(self.pag, ini, fim, self.turnos, self.HOJE, kw.get('rastreio'))
        return [a for a in lista if a['campo'].pk == campo.pk], devidos

    def test_turno_e_diaria(self):
        self.responder(date(2026, 10, 20), self.t1, self.c_lista)
        self.responder(date(2026, 10, 20), self.t2, self.c_num, '-0,7')
        ini, fim = date(2026, 10, 19), date(2026, 10, 21)
        por_turno, devidos = self.atrasos(self.c_lista, ini, fim)
        self.assertEqual(sorted((a['fim'].day, a['turno'].sigla) for a in por_turno),
                         [(19, 'T1'), (19, 'T2'), (20, 'T2'), (21, 'T1'), (21, 'T2')])
        diaria, _ = self.atrasos(self.c_num, ini, fim)
        self.assertEqual(sorted(a['fim'].day for a in diaria), [19, 21])  # 20 foi feito (qualquer turno)
        self.assertEqual(devidos, 9)  # 6 por turno + 3 diárias; semanal/mensal ainda não encerraram

    def test_hoje_nao_entra_e_janelas_abertas_nao_atrasam(self):
        lista, devidos = pend.atrasos_pagina(self.pag, date(2026, 10, 20), date(2026, 10, 25), self.turnos, self.HOJE)
        self.assertTrue(all(a['fim'] <= date(2026, 10, 21) for a in lista))
        self.assertFalse([a for a in lista if a['campo'].pk in (self.c_sem.pk, self.c_mes.pk)])

    def test_semana_encerrada_conta_uma_vez(self):
        lista, _ = self.atrasos(self.c_sem, date(2026, 10, 12), date(2026, 10, 21))
        self.assertEqual([(a['inicio'], a['fim']) for a in lista], [(date(2026, 10, 12), date(2026, 10, 18))])
        self.responder(date(2026, 10, 15), self.t1, self.c_sem, 'x')  # feito no meio da semana: cumpre a janela inteira
        self.assertEqual(self.atrasos(self.c_sem, date(2026, 10, 12), date(2026, 10, 21))[0], [])

    def test_mes_encerrado(self):
        lista, _ = self.atrasos(self.c_mes, date(2026, 9, 25), date(2026, 10, 5))
        self.assertEqual([(a['inicio'], a['fim']) for a in lista], [(date(2026, 9, 1), date(2026, 9, 30))])

    def test_rastreio_corta_o_inicio(self):
        lista, _ = self.atrasos(self.c_lista, date(2026, 10, 19), date(2026, 10, 21), rastreio=date(2026, 10, 21))
        self.assertEqual(sorted(a['turno'].sigla for a in lista), ['T1', 'T2'])
        self.assertEqual({a['fim'].day for a in lista}, {21})
        self.assertEqual(pend.inicio_rastreio(self.form), date(2026, 10, 1))

    def test_painel_atrasos(self):
        self.responder(date(2026, 10, 20), self.t1, self.c_lista)
        p = pend.painel_atrasos(date(2026, 10, 19), date(2026, 10, 25), self.turnos, hoje=self.HOJE)
        self.assertEqual([str(d) for d in p['datas']], ['2026-10-19', '2026-10-20', '2026-10-21'])
        linha = p['blocos'][0]['grupos']['Sem grupo' if not self.pag.grupo else self.pag.grupo][0]
        self.assertEqual(linha['devidos'], 9)
        self.assertEqual(linha['atrasados'], 8)  # 9 devidos - 1 feito (c_lista T1 dia 20)
        self.assertEqual(p['percentual'], 11)
        d19, cel = linha['celulas'][0]
        self.assertEqual((d19, cel['n']), (date(2026, 10, 19), 3))  # lista T1, lista T2, diária

    def test_telas(self):
        r = self.client.get(reverse('pcp:atrasos') + '?dias=14')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Atrasos do período')
        r = self.client.get(reverse('pcp:atrasos_pagina', args=[self.pag.pk]) + '?dias=7')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get(reverse('pcp:atrasos') + '?dias=abc&formulario=x&ate=lixo').status_code, 200)

    def test_publicar_com_vigencia(self):
        nova = self.v15.clonar('R16')
        self.client.post(reverse('pcp:versao_publicar', args=[nova.pk]), {'vigencia': '2026-09-15'})
        nova.refresh_from_db()
        self.assertEqual((nova.status, nova.vigencia), ('vigente', date(2026, 9, 15)))
        self.assertEqual(pend.inicio_rastreio(self.form), date(2026, 9, 15))


class GruposTests(PcpBase):
    def setUp(self):
        super().setUp()
        self.pag.grupo = ''
        self.pag.save()
        self.outra = Pagina.objects.create(versao=self.v15, nome='Outra', grupo='Corte')
        self.v15.publicar()

    def url(self, nome, *args):
        return reverse(f'pcp:{nome}', args=args)

    def test_tela_sincroniza_grupos_existentes_e_filtra(self):
        r = self.client.get(self.url('grupos', self.form.pk))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(self.form.grupos.values_list('nome', flat=True)), ['Corte'])  # criado a partir do texto da página
        self.assertContains(self.client.get(self.url('grupos', self.form.pk) + '?grupo=__sem__'), 'Fitadeira')
        self.assertNotContains(self.client.get(self.url('grupos', self.form.pk) + '?grupo=Corte'), 'Fitadeira')

    def test_criar_renomear_unir_e_excluir_grupo(self):
        self.client.post(self.url('grupo_criar', self.form.pk), {'nome': '  Polimento  '})
        self.assertTrue(self.form.grupos.filter(nome='Polimento').exists())
        corte = self.form.garantir_grupo('Corte')
        self.client.post(self.url('grupo_renomear', corte.pk), {'nome': 'Corte e Gravação'})
        self.assertEqual(Pagina.objects.get(pk=self.outra.pk).grupo, 'Corte e Gravação')
        pol = self.form.grupos.get(nome='Polimento')
        self.client.post(self.url('grupo_renomear', pol.pk), {'nome': 'Corte e Gravação'})  # nome existente: une
        self.assertEqual(self.form.grupos.count(), 1)
        g = self.form.grupos.get()
        self.client.post(self.url('grupo_excluir', g.pk))
        self.assertEqual(self.form.grupos.count(), 0)
        self.assertEqual(Pagina.objects.get(pk=self.outra.pk).grupo, '')  # página não é apagada

    def test_ordenar_grupos(self):
        self.form.garantir_grupo('A')
        b = self.form.garantir_grupo('B')
        self.client.post(self.url('grupo_mover', b.pk), {'dir': 'up'})
        ordem = list(self.form.ordenar_grupos({'A': 1, 'B': 2, 'Sem grupo': 3, 'Z': 4}))
        self.assertEqual(ordem, ['B', 'A', 'Z', 'Sem grupo'])

    def test_mover_e_remover_em_massa_vale_para_outras_revisoes(self):
        nova = self.v15.clonar('R16')
        self.client.post(self.url('paginas_acao', self.form.pk), {
            'paginas': [self.pag.pk, self.outra.pk], 'acao': 'mover', 'destino': '__novo__', 'novo_nome': 'Blocagem'})
        self.assertEqual(set(Pagina.objects.values_list('grupo', flat=True)), {'Blocagem'})  # inclui o rascunho R16
        self.assertTrue(nova.paginas.filter(grupo='Blocagem').exists())
        self.client.post(self.url('paginas_acao', self.form.pk), {'paginas': [self.outra.pk], 'acao': 'remover'})
        self.assertEqual(Pagina.objects.get(pk=self.outra.pk).grupo, '')
        self.client.post(self.url('paginas_acao', self.form.pk), {'paginas': [self.pag.pk], 'acao': 'mover', 'destino': 'inexistente'})
        self.assertEqual(Pagina.objects.get(pk=self.pag.pk).grupo, 'Blocagem')  # destino inválido não altera

    def test_editar_pagina_travada_muda_grupo_e_propaga(self):
        r = self.client.post(self.url('pagina_editar', self.pag.pk), {'grupo': 'Polimento', 'ordem': 3, 'nome': 'Nome trocado'})
        self.assertEqual(r.status_code, 302)
        self.pag.refresh_from_db()
        self.assertEqual((self.pag.grupo, self.pag.nome), ('Polimento', 'Fitadeira'))
        self.assertTrue(self.form.grupos.filter(nome='Polimento').exists())

    def test_atalho_antigo_redireciona(self):
        r = self.client.get(self.url('versao_grupos', self.v15.pk))
        self.assertRedirects(r, self.url('grupos', self.form.pk))


class BlocosTests(PcpBase):
    """Excluir/desativar blocos e itens sem utilidade, inclusive na revisão vigente."""

    def setUp(self):
        super().setUp()
        self.outra = Pagina.objects.create(versao=self.v15, nome='Outra')
        self.v15.publicar()

    def test_exclui_bloco_sem_historico_na_revisao_vigente(self):
        r = self.client.post(reverse('pcp:pagina_excluir', args=[self.outra.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Pagina.objects.filter(pk=self.outra.pk).exists())

    def test_bloco_com_historico_nao_exclui_mas_desativa(self):
        Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        self.client.post(reverse('pcp:pagina_excluir', args=[self.pag.pk]))
        self.assertTrue(Pagina.objects.filter(pk=self.pag.pk).exists())
        self.client.post(reverse('pcp:pagina_alternar', args=[self.pag.pk]))
        self.pag.refresh_from_db()
        self.assertFalse(self.pag.ativo)
        self.assertNotContains(self.client.get(reverse('pcp:preencher')), reverse('pcp:preencher_pagina', args=[self.pag.pk]))  # some do preenchimento
        self.client.post(reverse('pcp:pagina_alternar', args=[self.pag.pk]))
        self.pag.refresh_from_db()
        self.assertTrue(self.pag.ativo)

    def test_desativar_propaga_para_rascunho_com_mesmo_nome(self):
        rascunho = self.v15.clonar('R16')
        self.client.post(reverse('pcp:pagina_alternar', args=[self.pag.pk]))
        self.assertFalse(rascunho.paginas.get(nome='Fitadeira').ativo)

    def test_acao_em_massa_excluir_e_desativar(self):
        Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        self.client.post(reverse('pcp:paginas_acao', args=[self.form.pk]), {'paginas': [self.pag.pk, self.outra.pk], 'acao': 'excluir'})
        self.assertTrue(Pagina.objects.filter(pk=self.pag.pk).exists())      # tem histórico: preservada
        self.assertFalse(Pagina.objects.filter(pk=self.outra.pk).exists())   # sem histórico: excluída
        self.client.post(reverse('pcp:paginas_acao', args=[self.form.pk]), {'paginas': [self.pag.pk], 'acao': 'desativar'})
        self.pag.refresh_from_db()
        self.assertFalse(self.pag.ativo)

    def test_campo_na_revisao_vigente(self):
        self.client.post(reverse('pcp:campo_alternar', args=[self.c_num.pk]))
        self.c_num.refresh_from_db()
        self.assertFalse(self.c_num.ativo)
        self.client.post(reverse('pcp:campo_excluir', args=[self.c_lista.pk]))
        self.assertFalse(Campo.objects.filter(pk=self.c_lista.pk).exists())
        ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        Resposta.objects.create(verificacao=ver, campo=self.c_num, valor='1')
        self.client.post(reverse('pcp:campo_excluir', args=[self.c_num.pk]))
        self.assertTrue(Campo.objects.filter(pk=self.c_num.pk).exists())  # com resposta: protegido


class AbasOcultasTests(PcpBase):
    def test_importacao_ignora_abas_ocultas(self):
        wb = openpyxl.load_workbook(_planilha_modelo())
        wb['Parâmetro de Receita-ABC'].sheet_state = 'hidden'
        saida = io.BytesIO()
        wb.save(saida)
        saida.seek(0)
        r = importar_planilha(saida, nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor)
        self.assertEqual([p[0] for p in r['paginas']], ['Fitadeira'])
        self.assertEqual(r['ocultas'], ['Parâmetro de Receita-ABC'])
        self.assertEqual(r['total_campos'], 3)

    def test_importacao_registra_grupos_e_herda_ajustes(self):
        r1 = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor, publicar=True)
        form = r1['formulario']
        self.assertTrue(form.grupos.filter(nome='Fita').exists())  # grupo vindo do Índice foi cadastrado
        form.atribuir_grupo(['Fitadeira'], 'Meu grupo')           # ajuste manual
        r2 = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R04 - x.xlsx', setor=self.setor)
        self.assertEqual(r2['versao'].paginas.get(nome='Fitadeira').grupo, 'Meu grupo')  # o ajuste manual prevalece


class ExcluirFormularioTests(PcpBase):
    def url(self):
        return reverse('pcp:formulario_excluir', args=[self.form.pk])

    def test_exclui_formulario_sem_historico_e_permite_reimportar(self):
        r = self.client.get(self.url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'FOR.080')
        self.client.post(self.url())
        self.assertFalse(Formulario.objects.filter(pk=self.form.pk).exists())
        self.assertFalse(Pagina.objects.exists() or Campo.objects.exists())
        self.assertTrue(Turno.objects.exists() and ListaOpcoes.objects.exists())  # cadastros base preservados
        r = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.080.R15 - x.xlsx', setor=self.setor)  # código livre de novo
        self.assertEqual(str(r['versao']), 'FOR.080.R15')

    def test_com_historico_exige_confirmacao_digitada(self):
        self.v15.publicar()
        ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 22), turno=self.t1)
        Resposta.objects.create(verificacao=ver, campo=self.c_lista, valor='Ok')
        Ocorrencia.objects.create(verificacao=ver, tipo='tratativa', descricao='x')
        r = self.client.post(self.url())  # sem confirmar
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Formulario.objects.filter(pk=self.form.pk).exists())
        self.client.post(self.url(), {'apagar_historico': 'on', 'codigo': 'errado'})
        self.assertTrue(Formulario.objects.filter(pk=self.form.pk).exists())
        r = self.client.post(self.url(), {'apagar_historico': 'on', 'codigo': 'for.080'})  # ignora maiúsculas
        self.assertRedirects(r, reverse('pcp:formularios'))
        self.assertFalse(Formulario.objects.filter(pk=self.form.pk).exists())
        self.assertEqual((Verificacao.objects.count(), Resposta.objects.count(), Ocorrencia.objects.count()), (0, 0, 0))


class OrdemPaginasTests(PcpBase):
    def setUp(self):
        super().setUp()
        self.pag.delete()
        self.nomes = ['DLP (10)', 'DLP (2)', 'DLP (1)']
        # ordem igual (0) em todas: a ordenação precisa funcionar mesmo com valores repetidos
        self.pags = [Pagina.objects.create(versao=self.v15, nome=n, grupo='Polimento', ordem=0) for n in self.nomes]
        self.v15.publicar()

    def nomes_na_ordem(self, versao=None):
        return [p.nome for p in (versao or self.v15).paginas.all()]

    def posicoes(self, html, nomes):
        return [html.index(n) for n in nomes]

    def test_ordenar_az_natural(self):
        self.client.post(reverse('pcp:grupo_ordenar', args=[self.form.pk]), {'filtro': 'Polimento'})
        self.assertEqual(self.nomes_na_ordem(), ['DLP (1)', 'DLP (2)', 'DLP (10)'])  # 10 depois de 2

    def test_subir_e_descer_dentro_do_grupo(self):
        self.client.post(reverse('pcp:grupo_ordenar', args=[self.form.pk]), {'filtro': 'Polimento'})
        p10 = Pagina.objects.get(nome='DLP (10)')
        self.client.post(reverse('pcp:pagina_mover', args=[p10.pk]), {'dir': 'up'})
        self.assertEqual(self.nomes_na_ordem(), ['DLP (1)', 'DLP (10)', 'DLP (2)'])
        p1 = Pagina.objects.get(nome='DLP (1)')
        self.client.post(reverse('pcp:pagina_mover', args=[p1.pk]), {'dir': 'up'})  # já é a primeira: não muda
        self.assertEqual(self.nomes_na_ordem(), ['DLP (1)', 'DLP (10)', 'DLP (2)'])
        self.client.post(reverse('pcp:pagina_mover', args=[p1.pk]), {'dir': 'down'})
        self.assertEqual(self.nomes_na_ordem(), ['DLP (10)', 'DLP (1)', 'DLP (2)'])

    def test_ordem_vale_para_rascunho_com_mesmo_nome(self):
        rascunho = self.v15.clonar('R16')
        self.client.post(reverse('pcp:grupo_ordenar', args=[self.form.pk]), {'filtro': 'Polimento'})
        self.assertEqual(self.nomes_na_ordem(rascunho), ['DLP (1)', 'DLP (2)', 'DLP (10)'])

    def test_ordem_aparece_nas_telas(self):
        self.client.post(reverse('pcp:grupo_ordenar', args=[self.form.pk]), {'filtro': 'Polimento'})
        p10 = Pagina.objects.get(nome='DLP (10)')
        self.client.post(reverse('pcp:pagina_mover', args=[p10.pk]), {'dir': 'up'})  # 1, 10, 2
        esperado = ['DLP (1)', 'DLP (10)', 'DLP (2)']
        for url in (reverse('pcp:preencher'), reverse('pcp:versao_detalhe', args=[self.v15.pk]),
                    reverse('pcp:grupos', args=[self.form.pk]) + '?grupo=Polimento'):
            html = self.client.get(url).content.decode()
            pos = self.posicoes(html, esperado)
            self.assertEqual(pos, sorted(pos), url)
        # pendências e atrasos precisam de itens devidos para listar a página; cria uma frequência por turno
        f = Frequencia.objects.create(nome='Turno X', periodicidade='turno')
        for p in Pagina.objects.all():
            Campo.objects.create(pagina=p, item='1', descricao='x', tipo='texto', frequencia=f)
        self.v15.vigencia = date(2026, 10, 1)
        self.v15.save()
        html = self.client.get(reverse('pcp:pendencias') + '?data=2026-10-22').content.decode()
        pos = self.posicoes(html, esperado)
        self.assertEqual(pos, sorted(pos))
        html = self.client.get(reverse('pcp:atrasos') + '?dias=7').content.decode()
        pos = self.posicoes(html, esperado)
        self.assertEqual(pos, sorted(pos))

    def test_setas_desabilitadas_nas_pontas(self):
        self.client.post(reverse('pcp:grupo_ordenar', args=[self.form.pk]), {'filtro': 'Polimento'})
        r = self.client.get(reverse('pcp:grupos', args=[self.form.pk]) + '?grupo=Polimento')
        paginas = r.context['paginas']
        self.assertEqual([(p.pode_subir, p.pode_descer) for p in paginas], [(False, True), (True, True), (True, False)])


def _planilha_registros(extra_numerico=False):
    """Formulário no padrão do FOR.080 com colunas de data x turno (2026 e uma de 2025) e uma aba mensal."""
    import datetime as dt
    wb = openpyxl.Workbook()
    wb.active.title = 'Dados'
    aba = wb.create_sheet('Fitadeira')
    aba.append(['Voltar ao índice', None, None, 'Fitadeira'])
    aba.append(['Resp', 'item', 'O que verificar', 'Especificações', 'Método', 'Frequencia', 'Plano de reação',
                dt.datetime(2026, 1, 5), None, None, dt.datetime(2026, 1, 6), None, None, dt.datetime(2025, 1, 7)])
    aba.append([None] * 7 + ['T1', 'T2', 'T3', 'T1', 'T2', 'T3', 'T1'])
    aba.append(['Oper.', 'A-1', 'Limpeza dos blocos', 'Sem poeira', 'Visual', 'Diário', 'Ar', 'ok', 'Realizado', None, 'Nok', None, None, 'ok'])
    aba.append([None, 'B-12', 'Temperatura da fita', '10 - 27 ° C', 'Termômetro', 'Turno', 'x', 21.5, 30, None, 22])
    if extra_numerico:
        aba.append([None, 'C-1', 'Medida qualquer', 'Conforme padrão', 'Régua', 'Turno', 'x', 1, 2, 3, 4, 5, 6])
    receita = wb.create_sheet('Parâmetro de Receita-ABC')
    receita.append(['Voltar', 'Parâmetro de Receita-ABC'])
    receita.append([None, 'Resp.', 'Frequência', 'Receita', 'Razão', 'Especificação', 'Tolerância (min - max)', 'Janeiro', 'Fevereiro'])
    receita.append([None, None, 'Mensal', 'Receita X', 'Z0/Z2', 0.05, '0,043 - 0,058', 0.05, 0.07])
    receita.append([None, None, 'Mensal', None, 'Z1/Z2', 0.111, '0,094 - 0,128'])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class RegistrosTests(PcpBase):
    HOJE = date(2026, 12, 31)

    def setUp(self):
        super().setUp()
        Turno.objects.create(nome='Turno 2', sigla='T2', ordem=2)
        Turno.objects.create(nome='Turno 3', sigla='T3', ordem=3)
        self.pag.delete()  # a estrutura vem da própria planilha
        self.form.delete()

    def estrutura(self, **kw):
        return importar_planilha(_planilha_registros(kw.pop('extra_numerico', False)),
                                 nome_arquivo='FOR.999.R03 - Teste.xlsx', setor=self.setor, publicar=True)

    def registros(self, **kw):
        extra = kw.pop('extra_numerico', False)
        return importar_registros(_planilha_registros(extra), nome_arquivo='FOR.999.R03 - Teste.xlsx', hoje=kw.pop('hoje', self.HOJE), **kw)

    def test_importa_lancamentos_por_data_e_turno(self):
        self.estrutura()
        r = self.registros()
        self.assertEqual((r['verificacoes_novas'], r['respostas_novas']), (5, 8))
        self.assertEqual((r['primeira_data'], r['ultima_data']), (date(2026, 1, 1), date(2026, 2, 1)))  # 2025 ignorado
        self.assertEqual(r['fora_do_limite'], 3)  # Nok, 30 (faixa 10-27) e 0,07 (faixa 0,043-0,058)
        fit = Pagina.objects.get(nome='Fitadeira')
        v = Verificacao.objects.get(pagina=fit, data=date(2026, 1, 5), turno__sigla='T2')
        self.assertEqual(sorted(v.respostas.values_list('campo__item', 'valor', 'conforme')), [('A-1', 'Realizado', True), ('B-12', '30', False)])
        self.assertFalse(Verificacao.objects.filter(data__year=2025).exists())
        mensal = Verificacao.objects.get(pagina__nome='ABC - Receita', data=date(2026, 2, 1))
        self.assertEqual(mensal.turno.sigla, 'T1')

    def test_vocabulario_ok_realizado_e_conformidade(self):
        self.estrutura()
        self.registros()
        r = Resposta.objects.get(campo__item='A-1', verificacao__data=date(2026, 1, 5), verificacao__turno__sigla='T1')
        self.assertEqual((r.valor, r.conforme), ('Ok', True))  # 'ok' normalizado
        nok = Resposta.objects.get(campo__item='A-1', verificacao__data=date(2026, 1, 6))
        self.assertEqual((nok.valor, nok.conforme), ('Nok', False))

    def test_reimportar_nao_duplica_nem_sobrescreve(self):
        self.estrutura()
        fit = Pagina.objects.get(nome='Fitadeira')
        campo = fit.campos.get(item='B-12')
        ver = Verificacao.objects.create(pagina=fit, data=date(2026, 1, 5), turno=Turno.objects.get(sigla='T1'))
        Resposta.objects.create(verificacao=ver, campo=campo, valor='99', conforme=False)  # lançado direto no sistema
        r1 = self.registros()
        self.assertEqual(r1['respostas_existentes'], 1)
        self.assertEqual(Resposta.objects.get(verificacao=ver, campo=campo).valor, '99')  # preservado
        total = Resposta.objects.count()
        r2 = self.registros()
        self.assertEqual((r2['respostas_novas'], Resposta.objects.count()), (0, total))

    def test_simular_nao_grava(self):
        self.estrutura()
        r = self.registros(simular=True)
        self.assertEqual(r['respostas_novas'], 8)
        self.assertEqual((Verificacao.objects.count(), Resposta.objects.count()), (0, 0))

    def test_ignora_datas_futuras(self):
        self.estrutura()
        r = self.registros(hoje=date(2026, 1, 5))
        self.assertEqual(r['futuros'], 3)  # dia 06/01 (2 valores) e fevereiro da aba mensal
        self.assertEqual(r['ultima_data'], date(2026, 1, 5))

    def test_exige_estrutura_importada(self):
        with self.assertRaises(ValueError):
            self.registros()  # formulário FOR.999 ainda não existe

    def test_ajustar_tipos_pelos_registros(self):
        self.estrutura(extra_numerico=True)
        campo = Campo.objects.get(item='C-1')
        self.assertEqual(campo.tipo, 'lista')
        r = self.registros(extra_numerico=True)
        campo.refresh_from_db()
        self.assertEqual(campo.tipo, 'lista')  # sem a opção, nada muda
        self.assertEqual(r['tipos_ajustados'], [])
        r = self.registros(extra_numerico=True, ajustar_tipos=True, simular=True)
        self.assertEqual([t[1] for t in r['tipos_ajustados']], ['C-1'])
        campo.refresh_from_db()
        self.assertEqual(campo.tipo, 'lista')  # simulação não altera
        Resposta.objects.filter(campo=campo).delete()
        self.registros(extra_numerico=True, ajustar_tipos=True)
        campo.refresh_from_db()
        self.assertEqual((campo.tipo, campo.lista_id), ('numero', None))

    def test_rastreio_desde_primeiro_registro(self):
        r = self.estrutura()
        self.assertEqual(r['versao'].vigencia, timezone.localdate())
        self.registros(rastreio_desde_primeiro=True)
        r['versao'].refresh_from_db()
        self.assertEqual(r['versao'].vigencia, date(2026, 1, 1))

    def test_tela_e_comando(self):
        from django.core.management import call_command
        self.estrutura()
        self.assertEqual(self.client.get(reverse('pcp:importar_registros')).status_code, 200)
        arq = SimpleUploadedFile('FOR.999.R03 - Teste.xlsx', _planilha_registros().read())
        r = self.client.post(reverse('pcp:importar_registros'), {'arquivo': arq, 'ano': 2026, 'simular': 'on', 'ajustar_tipos': 'on'})
        self.assertContains(r, 'Simulação')
        self.assertEqual(Resposta.objects.count(), 0)
        arq = SimpleUploadedFile('FOR.999.R03 - Teste.xlsx', _planilha_registros().read())
        self.client.post(reverse('pcp:importar_registros'), {'arquivo': arq, 'ano': 2026})
        self.assertEqual(Resposta.objects.count(), 8)
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            caminho = os.path.join(d, 'FOR.999.R03 - Teste.xlsx')
            open(caminho, 'wb').write(_planilha_registros().read())
            out = io.StringIO()
            call_command('importar_pcp_registros', caminho, '--simular', stdout=out)
            self.assertIn('SIMULAÇÃO', out.getvalue())

    def test_estrutura_e_registros_sao_importacoes_separadas(self):
        r = self.estrutura()
        self.assertEqual((Verificacao.objects.count(), Resposta.objects.count()), (0, 0))  # estrutura não traz lançamentos
        self.assertGreater(r['total_campos'], 0)


class AjustarTiposTests(PcpBase):
    def setUp(self):
        super().setUp()
        self.v15.publicar()
        self.c_ok = Campo.objects.create(pagina=self.pag, item='O-1', descricao='Coerente', tipo='lista', lista=self.lista)
        self.c_medida = Campo.objects.create(pagina=self.pag, item='M-1', descricao='Medida', tipo='lista', lista=self.lista)
        self.c_texto = Campo.objects.create(pagina=self.pag, item='T-1', descricao='Livre', tipo='lista', lista=self.lista)
        for dia in range(1, 7):
            ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 3, dia), turno=self.t1)
            Resposta.objects.create(verificacao=ver, campo=self.c_ok, valor='Ok', conforme=True)
            Resposta.objects.create(verificacao=ver, campo=self.c_medida, valor=str(40 + dia), conforme=None)
            Resposta.objects.create(verificacao=ver, campo=self.c_texto, valor='Lofoam', conforme=None)

    def test_propostas(self):
        from pcp.tipos import propor_ajustes
        p = {x['campo'].item: x for x in propor_ajustes(self.v15)}
        self.assertEqual(set(p), {'M-1', 'T-1'})  # 'Ok' é coerente com a lista; B-1 e B-5 não têm lançamentos
        self.assertEqual(p['M-1']['novo_tipo'], 'numero')
        self.assertEqual(p['T-1']['novo_tipo'], 'texto')
        self.assertEqual(p['M-1']['pct_numerico'], 100)
        self.assertIn('Lofoam', p['T-1']['exemplos'])

    def test_poucos_lancamentos_nao_geram_proposta(self):
        from pcp.tipos import propor_ajustes
        Resposta.objects.filter(campo=self.c_medida).exclude(verificacao__data__lte=date(2026, 3, 3)).delete()  # sobram 3
        self.assertNotIn('M-1', {x['campo'].item for x in propor_ajustes(self.v15)})

    def test_tela_e_aplicacao_propagam_e_limpam_conformidade(self):
        rascunho = self.v15.clonar('R16')
        Resposta.objects.filter(campo=self.c_medida).update(conforme=False)  # conformidade antiga, calculada pela lista
        url = reverse('pcp:ajustar_tipos', args=[self.form.pk])
        r = self.client.get(url)
        self.assertContains(r, 'Medida')
        self.assertContains(r, 'Livre')
        self.client.post(url, {'campos': [f'{self.c_medida.pk}|numero', f'{self.c_ok.pk}|texto', f'{self.c_texto.pk}|invalido']})
        self.c_medida.refresh_from_db()
        self.assertEqual((self.c_medida.tipo, self.c_medida.lista_id), ('numero', None))
        self.assertFalse(Resposta.objects.filter(campo=self.c_medida, conforme=False).exists())
        self.assertEqual(Campo.objects.get(pagina__versao=rascunho, item='M-1').tipo, 'numero')  # equivalente no rascunho
        self.c_ok.refresh_from_db()
        self.assertEqual(self.c_ok.tipo, 'texto')  # o POST manda: só itens de lista são alterados, tipo inválido é ignorado
        self.c_texto.refresh_from_db()
        self.assertEqual(self.c_texto.tipo, 'lista')

    def test_importar_estrutura_herda_ajustes_e_desativados(self):
        r1 = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.998.R01 - x.xlsx', setor=self.setor, publicar=True)
        fita = r1['versao'].paginas.get(nome='Fitadeira')
        temp = fita.campos.get(item='B-12')           # número com faixa 10-27
        limpeza = fita.campos.get(item='A-1')
        Campo.objects.filter(pk=limpeza.pk).update(tipo='texto', lista=None, ativo=False, critico=True)
        Pagina.objects.filter(pk=fita.pk).update(ativo=False, ordem=7)
        r2 = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.998.R02 - x.xlsx', setor=self.setor)
        fita2 = r2['versao'].paginas.get(nome='Fitadeira')
        self.assertEqual((fita2.ativo, fita2.ordem), (False, 1))   # ordem renumerada de 1 a n dentro do grupo
        l2 = fita2.campos.get(item='A-1')
        self.assertEqual((l2.tipo, l2.ativo, l2.critico), ('texto', False, True))
        t2 = fita2.campos.get(item='B-12')
        self.assertEqual((t2.tipo, t2.minimo, t2.maximo), ('numero', temp.minimo, temp.maximo))

    def test_especificacao_alterada_nao_herda_tipo(self):
        r1 = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.998.R01 - x.xlsx', setor=self.setor, publicar=True)
        Campo.objects.filter(pagina__versao=r1['versao'], item='B-12').update(tipo='texto', minimo=None, maximo=None)
        Campo.objects.filter(pagina__versao=r1['versao'], item='B-12').update(especificacao='10 - 28 ° C')  # a nova planilha traz 10 - 27
        r2 = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.998.R02 - x.xlsx', setor=self.setor)
        self.assertEqual(r2['versao'].paginas.get(nome='Fitadeira').campos.get(item='B-12').tipo, 'numero')  # reavaliado pela nova especificação


class LimitesTests(PcpBase):
    def setUp(self):
        super().setUp()
        self.c_num.delete()
        self.v15.publicar()
        mk = lambda item, spec, valores, **kw: self.campo_com(item, spec, valores, **kw)
        # valores 1..100 em "histórico": faixa de 99% corta as pontas (1 e 100)
        self.c_hist = mk('H-1', 'Conforme padrão', list(range(1, 101)))
        self.c_spec = mk('S-1', '10 - 27 ° C', [20 + (i % 5) for i in range(30)])
        self.c_meio = mk('M-1', 'até 75 °C', [50 + i for i in range(20)])           # só o máximo vem da especificação
        self.c_const = mk('K-1', 'Conforme padrão', [5] * 20)                        # sem variação
        self.c_poucos = mk('P-1', 'Conforme padrão', [1, 2, 3])                      # poucos lançamentos
        self.c_com = mk('L-1', 'Conforme padrão', list(range(20)), minimo=Decimal('0'), maximo=Decimal('100'))  # já tem limites

    def campo_com(self, item, spec, valores, **kw):
        campo = Campo.objects.create(pagina=self.pag, item=item, descricao=item, especificacao=spec, tipo='numero', **kw)
        for i, v in enumerate(valores):
            dia = date(2026, 1, 1) + datetime.timedelta(days=i // 3)
            ver, _ = Verificacao.objects.get_or_create(pagina=self.pag, data=dia, turno=[self.t1][0] if i % 3 == 0 else self._turno(i % 3))
            Resposta.objects.get_or_create(verificacao=ver, campo=campo, defaults={'valor': str(v), 'conforme': None})
        return campo

    def _turno(self, k):
        return Turno.objects.get_or_create(sigla=f'X{k}', defaults={'nome': f'X{k}', 'ordem': 10 + k})[0]

    def propostas(self, cobertura=99):
        from pcp.tipos import propor_limites
        return {p['campo'].item: p for p in propor_limites(self.v15, cobertura)}

    def test_leitor_de_especificacao(self):
        from pcp.tipos import limites_da_especificacao as L
        d = Decimal
        self.assertEqual(L('10 - 27 ° C'), (d('10'), d('27'), '° C'))
        self.assertEqual(L('45°C ± 2°C'), (d('43'), d('47'), '°C'))
        self.assertEqual(L('-0,8 <Pres. <-0,6 Bar'), (d('-0.8'), d('-0.6'), 'Bar'))
        self.assertEqual(L('580 L/h ± 20 L/h (cascata do Cuba)')[:2], (d('560'), d('600')))
        self.assertEqual(L('Para PRA: 1,67 - 1,73 mm'), (d('1.67'), d('1.73'), 'mm'))
        self.assertEqual(L('até 75° C')[:2], (None, d('75')))
        self.assertEqual(L('≥ 3 bar')[:2], (d('3'), None))
        self.assertEqual(L('[1,5 m/s, 3,5 m/s]')[:2], (d('1.5'), d('3.5')))
        for texto in ('Sem poeira', 'Conforme POP', '', None):
            self.assertIsNone(L(texto))

    def test_propostas_por_fonte(self):
        p = self.propostas()
        self.assertEqual(set(p), {'H-1', 'S-1', 'M-1'})  # K-1 constante, P-1 poucos e L-1 com limites ficam de fora
        self.assertEqual((p['H-1']['fonte'], p['H-1']['minimo'], p['H-1']['maximo']), ('histórico', 1, 100))  # 99% de 100 lançamentos: 0,5 por ponta, nada é cortado
        self.assertEqual((p['S-1']['fonte'], p['S-1']['minimo'], p['S-1']['maximo'], p['S-1']['pct_dentro']), ('especificação', 10, 27, 100))
        self.assertEqual((p['M-1']['fonte'], p['M-1']['minimo'], p['M-1']['maximo']), ('especificação + histórico', 50, 75))
        self.assertEqual(p['H-1']['mediana'], 51)

    def test_cobertura_muda_a_faixa_do_historico(self):
        self.assertEqual((self.propostas(100)['H-1']['minimo'], self.propostas(100)['H-1']['maximo']), (1, 100))
        self.assertEqual((self.propostas(98)['H-1']['minimo'], self.propostas(98)['H-1']['maximo']), (2, 99))
        self.assertEqual((self.propostas(95)['H-1']['minimo'], self.propostas(95)['H-1']['maximo']), (3, 98))

    def test_percentual_dentro_sinaliza_especificacao_incoerente(self):
        Campo.objects.filter(pk=self.c_spec.pk).update(especificacao='100 - 200')
        self.assertEqual(self.propostas()['S-1']['pct_dentro'], 0)
        r = self.client.get(reverse('pcp:sugerir_limites', args=[self.form.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'bg-danger')

    def test_aplicar_com_valores_editados_recalcula_conformidade_e_propaga(self):
        rascunho = self.v15.clonar('R16')
        url = reverse('pcp:sugerir_limites', args=[self.form.pk])
        r = self.client.post(url, {'campos': [self.c_hist.pk, self.c_spec.pk, self.c_const.pk],
                                   f'min_{self.c_hist.pk}': '10', f'max_{self.c_hist.pk}': '90,5',   # editado, com vírgula
                                   f'min_{self.c_spec.pk}': '10', f'max_{self.c_spec.pk}': '27', f'un_{self.c_spec.pk}': '°C',
                                   f'min_{self.c_const.pk}': '9', f'max_{self.c_const.pk}': '1'})   # inválido: mínimo > máximo
        self.assertEqual(r.status_code, 302)
        self.c_hist.refresh_from_db()
        self.assertEqual((self.c_hist.minimo, self.c_hist.maximo), (Decimal('10'), Decimal('90.5')))
        self.assertEqual(self.c_spec.__class__.objects.get(pk=self.c_spec.pk).unidade, '°C')
        fora = Resposta.objects.filter(campo=self.c_hist, conforme=False).count()
        self.assertEqual(fora, 9 + 10)  # valores 1..9 e 91..100
        self.assertEqual(Resposta.objects.filter(campo=self.c_hist, conforme=True).count(), 81)
        self.c_const.refresh_from_db()
        self.assertIsNone(self.c_const.minimo)  # limites inválidos não aplicados
        eq = Campo.objects.get(pagina__versao=rascunho, item='H-1')
        self.assertEqual((eq.minimo, eq.maximo), (Decimal('10'), Decimal('90.5')))
        self.assertNotIn('H-1', self.propostas())  # já tem limites: sai das sugestões

    def test_limite_de_um_lado_so(self):
        self.client.post(reverse('pcp:sugerir_limites', args=[self.form.pk]), {
            'campos': [self.c_meio.pk], f'min_{self.c_meio.pk}': '', f'max_{self.c_meio.pk}': '60'})
        self.c_meio.refresh_from_db()
        self.assertEqual((self.c_meio.minimo, self.c_meio.maximo), (None, Decimal('60')))
        self.assertEqual(Resposta.objects.filter(campo=self.c_meio, conforme=False).count(), 9)  # 61..69


class ValoresBase(PcpBase):
    HOJE = date(2026, 12, 31)

    def setUp(self):
        super().setUp()
        Turno.objects.create(nome='Turno 2', sigla='T2', ordem=2)
        Turno.objects.create(nome='Turno 3', sigla='T3', ordem=3)
        self.pag.delete()
        self.form.delete()

    def planilha(self, substituicoes):
        wb = openpyxl.load_workbook(_planilha_registros())
        for (linha, coluna), valor in substituicoes.items():
            wb['Fitadeira'].cell(row=linha, column=coluna).value = valor
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def estrutura(self):
        return importar_planilha(_planilha_registros(), nome_arquivo='FOR.999.R03 - Teste.xlsx', setor=self.setor, publicar=True)

    def registros(self, **kw):
        return importar_registros(kw.pop('arquivo', None) or _planilha_registros(), nome_arquivo='FOR.999.R03 - Teste.xlsx',
                                  hoje=self.HOJE, **kw)

    def listas(self):
        real = ListaOpcoes.objects.create(nome='Realizado / Não realizado')
        OpcaoLista.objects.create(lista=real, valor='Realizado', ordem=0)
        OpcaoLista.objects.create(lista=real, valor='Não realizado', conforme=False, ordem=1)
        return self.lista, real  # self.lista = 'Ok / Nok' (Ok, Nok)


class ValoresTests(ValoresBase):
    def test_sugestoes_com_base_nas_opcoes(self):
        from pcp.equivalencias import sugerir_opcao
        ok_nok, real = self.listas()
        proprias, outras = list(ok_nok.opcoes.all()), list(real.opcoes.all())
        sug = lambda v: sugerir_opcao(v, proprias, outras)
        o, conf, outra = sug('OK')
        self.assertEqual((o.valor, conf, outra), ('Ok', 'alta', False))
        o, conf, outra = sug('oki')                      # erro de digitação: opção da própria lista
        self.assertEqual((o.valor, conf, outra), ('Ok', 'media', False))
        o, conf, outra = sug('falta')                    # sinônimo de uma opção de OUTRA lista
        self.assertEqual((o.valor, conf, outra), ('Não realizado', 'alta', True))
        o, conf, outra = sug('realizaddo')
        self.assertEqual((o.valor, outra), ('Realizado', True))
        for texto in ('ND', 'Lofoam', '0,8%LH305', ''):  # texto livre: sem sugestão
            self.assertEqual(sug(texto)[0], None, texto)

    def test_relatorio_da_importacao_traz_sugestao(self):
        self.listas()
        self.estrutura()
        r = self.registros(arquivo=self.planilha({(4, 8): 'falat', (4, 9): 'Lofoam'}), simular=True)
        linhas = {l['valor']: l for l in r['nao_reconhecidos']}
        self.assertEqual(linhas['falat']['sugestao'].valor, 'Não realizado')
        self.assertFalse(linhas['falat']['de_outra_lista'])  # A-1 (limpeza) usa a lista Realizado / Não realizado
        self.assertIsNone(linhas['Lofoam']['sugestao'])

    def test_vincular_corrige_lancamentos_e_vale_nas_proximas_importacoes(self):
        _, real = self.listas()
        self.estrutura()
        planilha = lambda: self.planilha({(4, 8): 'talvez'})
        self.registros(arquivo=planilha())
        self.assertTrue(Resposta.objects.filter(valor='talvez', conforme__isnull=True).exists())
        opcao = real.opcoes.get(valor='Não realizado')
        lista_item = Campo.objects.get(item='A-1').lista
        r = self.client.post(reverse('pcp:vincular_valores'), {
            'total': 1, 'lista_0': lista_item.pk, 'valor_0': 'talvez', 'acao_0': f'op:{opcao.pk}', 'next': 'importar_registros'})
        self.assertRedirects(r, reverse('pcp:importar_registros'))
        resp = Resposta.objects.get(campo__item='A-1', verificacao__data=date(2026, 1, 5), verificacao__turno__sigla='T1')
        self.assertEqual((resp.valor, resp.conforme), ('Não realizado', False))   # lançamento já gravado foi corrigido
        eq = ValorEquivalente.objects.get()
        self.assertEqual((eq.chave, eq.opcao_id), ('talvez', opcao.pk))
        # apaga e reimporta: o vínculo é aplicado sozinho
        Resposta.objects.all().delete()
        Verificacao.objects.all().delete()
        r = self.registros(arquivo=planilha())
        resp = Resposta.objects.get(campo__item='A-1', verificacao__data=date(2026, 1, 5), verificacao__turno__sigla='T1')
        self.assertEqual((resp.valor, resp.conforme), ('Não realizado', False))
        self.assertFalse([l for l in r['nao_reconhecidos'] if l['valor'] == 'talvez'])

    def test_criar_como_nova_opcao_e_manter(self):
        self.listas()
        self.estrutura()
        self.registros(arquivo=self.planilha({(4, 8): 'ND', (4, 9): 'xyz'}))
        lista = Campo.objects.get(item='A-1').lista
        self.client.post(reverse('pcp:vincular_valores'), {
            'total': 2, 'lista_0': lista.pk, 'valor_0': 'ND', 'acao_0': 'novo:desvio',
            'lista_1': lista.pk, 'valor_1': 'xyz', 'acao_1': ''})  # manter: nada acontece
        opcao = lista.opcoes.get(valor='ND')
        self.assertFalse(opcao.conforme)
        self.assertEqual(Resposta.objects.get(valor='ND').conforme, False)
        self.assertIsNone(Resposta.objects.get(valor='xyz').conforme)
        self.assertFalse(lista.opcoes.filter(valor='xyz').exists())
        self.assertEqual(ValorEquivalente.objects.count(), 0)

    def test_tela_de_valores_por_formulario(self):
        self.listas()
        r0 = self.estrutura()
        self.registros(arquivo=self.planilha({(4, 8): 'falat', (4, 9): 'Lofoam'}))
        r = self.client.get(reverse('pcp:valores', args=[r0['formulario'].pk]))
        self.assertEqual(r.status_code, 200)
        valores = {l['valor']: l for l in r.context['linhas']}
        self.assertIn('falat', valores)
        self.assertEqual(valores['falat']['sugestao'].valor, 'Não realizado')
        self.assertNotIn('Ok', valores)  # coerente com a lista: não aparece
        self.assertContains(r, 'Lofoam')
        # quando tudo está vinculado, a tela mostra que não há pendências
        for l in r.context['linhas']:
            Resposta.objects.filter(valor=l['valor']).update(valor='Realizado', conforme=True)
        self.assertContains(self.client.get(reverse('pcp:valores', args=[r0['formulario'].pk])), 'Nenhum valor não reconhecido')

    def test_numericos_ficam_de_fora_dos_vinculos(self):
        from pcp.equivalencias import montar_linhas
        self.listas()
        linhas, numericos = montar_linhas({(self.lista.pk, '45'): 7, (self.lista.pk, 'falta'): 2})
        self.assertEqual([l['valor'] for l in linhas], ['falta'])
        self.assertEqual(numericos, 7)

    def test_vinculo_de_outra_lista_aparece_no_preenchimento(self):
        _, real = self.listas()
        r0 = self.estrutura()
        self.registros(arquivo=self.planilha({(4, 8): 'falat'}))
        lista = Campo.objects.get(item='A-1').lista
        opcao = real.opcoes.get(valor='Não realizado')
        self.client.post(reverse('pcp:vincular_valores'), {'total': 1, 'lista_0': lista.pk, 'valor_0': 'falat', 'acao_0': f'op:{opcao.pk}'})
        pagina = r0['versao'].paginas.get(nome='Fitadeira')
        html = self.client.get(reverse('pcp:preencher_pagina', args=[pagina.pk]) + f'?data=2026-01-05&turno={Turno.objects.get(sigla="T1").pk}').content.decode()
        self.assertIn('<option value="Não realizado" selected>', html)  # valor de outra lista continua visível

class MarcarTextoTests(ValoresBase):
    """Ação "marcar o item como texto livre" na mesma linha do vínculo de valores."""

    def preparar(self):
        self.listas()
        r0 = self.estrutura()
        self.registros(arquivo=self.planilha({(4, 8): 'Lofoam', (4, 9): 'Lofoam'}))   # 2 de 3 lançamentos do item A-1
        return r0

    def test_linha_mostra_itens_afetados_e_pre_seleciona_texto(self):
        r0 = self.preparar()
        r = self.client.get(reverse('pcp:valores', args=[r0['formulario'].pk]))
        linha = {l['valor']: l for l in r.context['linhas']}['Lofoam']
        self.assertEqual([(x['n'], x['total'], x['pct']) for x in linha['itens']], [(2, 3, 67)])
        self.assertTrue(linha['texto_sugerido'])
        self.assertContains(r, 'como texto livre')
        self.assertContains(r, 'parece texto livre')

    def test_valor_com_opcao_parecida_nao_pre_seleciona_texto(self):
        self.listas()
        r0 = self.estrutura()
        self.registros(arquivo=self.planilha({(4, 8): 'falat'}))
        linha = {l['valor']: l for l in self.client.get(reverse('pcp:valores', args=[r0['formulario'].pk])).context['linhas']}['falat']
        self.assertEqual(linha['sugestao'].valor, 'Não realizado')
        self.assertFalse(linha['texto_sugerido'])
        self.assertTrue(linha['itens'])  # a ação continua disponível

    def test_aplicar_marca_item_como_texto_e_limpa_conformidade(self):
        r0 = self.preparar()
        campo = Campo.objects.get(item='A-1')
        self.assertEqual(campo.tipo, 'lista')
        linha = {l['valor']: l for l in self.client.get(reverse('pcp:valores', args=[r0['formulario'].pk])).context['linhas']}['Lofoam']
        r = self.client.post(reverse('pcp:vincular_valores'), {
            'total': 1, 'lista_0': campo.lista_id, 'valor_0': 'Lofoam', 'acao_0': 'texto', 'itens_0': linha['itens_ids'],
            'formulario': r0['formulario'].pk, 'next': 'valores'})
        self.assertRedirects(r, reverse('pcp:valores', args=[r0['formulario'].pk]))
        campo.refresh_from_db()
        self.assertEqual((campo.tipo, campo.lista_id), ('texto', None))
        self.assertFalse(Resposta.objects.filter(campo=campo).exclude(conforme=None).exists())   # conformidade antiga limpa
        self.assertEqual(Resposta.objects.filter(campo=campo, valor='Lofoam').count(), 2)          # valores preservados
        self.assertEqual(ValorEquivalente.objects.count(), 0)

    def test_ids_de_itens_de_outra_lista_ou_tipo_sao_ignorados(self):
        r0 = self.preparar()
        campo = Campo.objects.get(item='A-1')
        outro_tipo = Campo.objects.get(item='B-12')       # numérico
        outra_lista = ListaOpcoes.objects.create(nome='Outra')
        self.client.post(reverse('pcp:vincular_valores'), {
            'total': 1, 'lista_0': outra_lista.pk, 'valor_0': 'Lofoam', 'acao_0': 'texto', 'itens_0': f'{campo.pk},{outro_tipo.pk}'})
        campo.refresh_from_db()
        outro_tipo.refresh_from_db()
        self.assertEqual(campo.tipo, 'lista')            # lista diferente da informada: não altera
        self.assertEqual(outro_tipo.tipo, 'numero')

    def test_relatorio_da_simulacao_traz_itens_afetados(self):
        self.listas()
        self.estrutura()
        r = self.registros(arquivo=self.planilha({(4, 8): 'Lofoam', (4, 9): 'Lofoam'}), simular=True)
        linha = {l['valor']: l for l in r['nao_reconhecidos']}['Lofoam']
        self.assertEqual([(x['n'], x['total']) for x in linha['itens']], [(2, 3)])
        self.assertTrue(linha['texto_sugerido'])


class DesfazerAjustesTests(PcpBase):
    def setUp(self):
        super().setUp()
        self.c_num.delete()
        self.v15.publicar()
        self.c_med = Campo.objects.create(pagina=self.pag, item='M-1', descricao='Medida', tipo='lista', lista=self.lista)
        self.c_lof = Campo.objects.create(pagina=self.pag, item='T-1', descricao='Livre', tipo='lista', lista=self.lista)
        for dia in range(1, 8):
            ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 3, dia), turno=self.t1)
            Resposta.objects.create(verificacao=ver, campo=self.c_med, valor=str(10 + dia), conforme=None)
            Resposta.objects.create(verificacao=ver, campo=self.c_lof, valor='Lofoam', conforme=None)
            Resposta.objects.create(verificacao=ver, campo=self.c_lista, valor='Ok', conforme=True)

    def tipo(self, campo, novo):
        return self.client.post(reverse('pcp:ajustar_tipos', args=[self.form.pk]), {'campos': [f'{campo.pk}|{novo}']})

    def desfazer(self, *ajustes):
        return self.client.post(reverse('pcp:ajustes', args=[self.form.pk]), {'ajustes': [a.pk for a in ajustes]})

    def test_ajuste_de_tipo_e_registrado_e_desfeito(self):
        self.tipo(self.c_med, 'numero')
        aj = AjusteCampo.objects.get()
        self.assertEqual((aj.origem, aj.antes['tipo'], aj.antes['lista'], aj.depois['tipo']), ('tipo', 'lista', self.lista.pk, 'numero'))
        self.assertIsNotNone(aj.criado_por)
        self.desfazer(aj)
        self.c_med.refresh_from_db()
        self.assertEqual((self.c_med.tipo, self.c_med.lista_id), ('lista', self.lista.pk))
        aj.refresh_from_db()
        self.assertTrue(aj.desfeito)
        self.assertEqual(Resposta.objects.filter(campo=self.c_med).count(), 7)  # lançamentos preservados

    def test_desfazer_recalcula_a_conformidade_pelo_tipo_restaurado(self):
        Resposta.objects.filter(campo=self.c_lista).update(conforme=True)
        # marca B-1 (lista Ok/Nok com 'Ok') como texto: conformidade limpa; desfazer devolve True
        self.client.post(reverse('pcp:vincular_valores'), {'total': 1, 'lista_0': self.lista.pk, 'valor_0': 'Ok', 'acao_0': 'texto', 'itens_0': str(self.c_lista.pk)})
        self.assertFalse(Resposta.objects.filter(campo=self.c_lista, conforme=True).exists())
        aj = AjusteCampo.objects.get(campo=self.c_lista)
        self.assertEqual(aj.origem, 'texto')
        self.desfazer(aj)
        self.assertEqual(Resposta.objects.filter(campo=self.c_lista, conforme=True).count(), 7)

    def test_limites_desfazem_para_sem_limites(self):
        self.tipo(self.c_med, 'numero')
        self.client.post(reverse('pcp:sugerir_limites', args=[self.form.pk]), {
            'campos': [self.c_med.pk], f'min_{self.c_med.pk}': '12', f'max_{self.c_med.pk}': '15', f'un_{self.c_med.pk}': 'mm'})
        self.assertTrue(Resposta.objects.filter(campo=self.c_med, conforme=False).exists())
        lim = AjusteCampo.objects.get(origem='limites')
        self.assertEqual((lim.antes['minimo'], lim.depois['minimo'], lim.depois['unidade']), (None, '12', 'mm'))
        self.desfazer(lim)
        self.c_med.refresh_from_db()
        self.assertEqual((self.c_med.tipo, self.c_med.minimo, self.c_med.maximo, self.c_med.unidade), ('numero', None, None, ''))
        self.assertFalse(Resposta.objects.filter(campo=self.c_med, conforme=False).exists())

    def test_nao_desfaz_se_o_item_mudou_depois(self):
        self.tipo(self.c_med, 'numero')
        aj = AjusteCampo.objects.get()
        Campo.objects.filter(pk=self.c_med.pk).update(tipo='texto')  # edição posterior
        self.desfazer(aj)
        self.c_med.refresh_from_db()
        self.assertEqual(self.c_med.tipo, 'texto')  # intocado
        aj.refresh_from_db()
        self.assertFalse(aj.desfeito)

    def test_desfaz_em_ordem_inversa_quando_selecionados_juntos(self):
        self.tipo(self.c_med, 'numero')
        self.client.post(reverse('pcp:sugerir_limites', args=[self.form.pk]), {
            'campos': [self.c_med.pk], f'min_{self.c_med.pk}': '12', f'max_{self.c_med.pk}': '15'})
        todos = list(AjusteCampo.objects.all())
        self.desfazer(*todos)  # o limite (mais recente) é desfeito antes do tipo
        self.c_med.refresh_from_db()
        self.assertEqual((self.c_med.tipo, self.c_med.lista_id, self.c_med.minimo), ('lista', self.lista.pk, None))
        self.assertTrue(all(a.desfeito for a in AjusteCampo.objects.all()))

    def test_desfazer_duas_vezes_e_ajuste_de_outro_formulario(self):
        self.tipo(self.c_med, 'numero')
        aj = AjusteCampo.objects.get()
        self.desfazer(aj)
        self.desfazer(aj)  # já desfeito: sem efeito
        self.assertEqual(AjusteCampo.objects.count(), 1)
        outro = Formulario.objects.create(setor=self.setor, codigo='FOR.777', titulo='Outro')
        r = self.client.post(reverse('pcp:ajustes', args=[outro.pk]), {'ajustes': [aj.pk]})  # id de outro formulário: ignorado
        self.assertEqual(r.status_code, 302)

    def test_propaga_ao_rascunho_e_desfaz_nos_dois(self):
        rascunho = self.v15.clonar('R16')
        self.tipo(self.c_med, 'numero')
        self.assertEqual(AjusteCampo.objects.count(), 2)  # vigente e rascunho
        self.desfazer(*AjusteCampo.objects.all())
        self.assertEqual(Campo.objects.get(pagina__versao=rascunho, item='M-1').tipo, 'lista')

    def test_tela_lista_e_filtra(self):
        self.tipo(self.c_med, 'numero')
        self.client.post(reverse('pcp:vincular_valores'), {'total': 1, 'lista_0': self.lista.pk, 'valor_0': 'Lofoam', 'acao_0': 'texto', 'itens_0': str(self.c_lof.pk)})
        url = reverse('pcp:ajustes', args=[self.form.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Lista: Ok/Nok')   # estado anterior legível
        self.assertEqual(len(self.client.get(url + '?origem=texto').context['linhas']), 1)
        self.assertEqual(len(self.client.get(url).context['linhas']), 2)


class HistoricoVinculosTests(ValoresBase):
    def preparar(self, valor='falat', celulas=((4, 8), (4, 9))):
        _, real = self.listas()
        r0 = self.estrutura()
        self.registros(arquivo=self.planilha({c: valor for c in celulas}))
        self.item = Campo.objects.get(item='A-1')
        self.real = real
        self.form_id = r0['formulario'].pk
        return r0

    def vincular(self, valor, acao, formulario=True):
        dados = {'total': 1, 'lista_0': self.item.lista_id, 'valor_0': valor, 'acao_0': acao}
        if formulario:
            dados['formulario'] = self.form_id
        return self.client.post(reverse('pcp:vincular_valores'), dados)

    def desfazer(self, *ajustes):
        return self.client.post(reverse('pcp:ajustes', args=[self.form_id]), {'ajustes': [f'v:{a.pk}' for a in ajustes]})

    def test_comprimir_faixas(self):
        from pcp.equivalencias import comprimir
        self.assertEqual(comprimir([7, 1, 2, 3, 8, 20]), [[1, 3], [7, 8], [20, 20]])
        self.assertEqual(comprimir([]), [])

    def test_vinculo_e_registrado_e_desfeito(self):
        self.preparar()
        nao = self.real.opcoes.get(valor='Não realizado')
        self.vincular('falat', f'op:{nao.pk}')
        aj = AjusteVinculo.objects.get()
        self.assertEqual((aj.acao, aj.valor, aj.total, aj.opcao_id, aj.alias_anterior_id), ('vinculo', 'falat', 2, nao.pk, None))
        self.assertIsNotNone(aj.criado_por)
        self.assertEqual(Resposta.objects.filter(valor='Não realizado', conforme=False).count(), 2)
        self.desfazer(aj)
        self.assertEqual(Resposta.objects.filter(valor='falat', conforme__isnull=True).count(), 2)  # texto e conformidade originais
        self.assertEqual(ValorEquivalente.objects.count(), 0)                                        # vínculo removido
        aj.refresh_from_db()
        self.assertTrue(aj.desfeito)
        # sem o vínculo, 'falat' volta a ser não reconhecido numa nova importação
        Resposta.objects.all().delete()
        Verificacao.objects.all().delete()
        r = self.registros(arquivo=self.planilha({(4, 8): 'falat'}), simular=True)
        self.assertIn('falat', [l['valor'] for l in r['nao_reconhecidos']])

    def test_desfazer_restaura_o_vinculo_anterior(self):
        self.preparar()
        ok = self.real.opcoes.get(valor='Realizado')
        nao = self.real.opcoes.get(valor='Não realizado')
        self.vincular('falat', f'op:{ok.pk}')
        primeiro = AjusteVinculo.objects.get()
        self.vincular('falat', f'op:{nao.pk}')   # religa o valor: os lançamentos já foram corrigidos pelo primeiro vínculo
        segundo = AjusteVinculo.objects.exclude(pk=primeiro.pk).get()
        self.assertEqual((segundo.total, segundo.alias_anterior_id), (0, ok.pk))
        self.assertEqual(ValorEquivalente.objects.get().opcao_id, nao.pk)
        self.desfazer(segundo)
        self.assertEqual(ValorEquivalente.objects.get().opcao_id, ok.pk)   # voltou ao vínculo anterior

    def test_criar_opcao_e_desfazer_remove_a_opcao(self):
        self.preparar(valor='ND')
        self.vincular('ND', 'novo:desvio')
        aj = AjusteVinculo.objects.get()
        self.assertEqual((aj.acao, aj.opcao_criada), ('opcao', True))
        self.assertTrue(self.item.lista.opcoes.filter(valor='ND').exists())
        self.assertEqual(Resposta.objects.filter(valor='ND', conforme=False).count(), 2)
        self.desfazer(aj)
        self.assertFalse(self.item.lista.opcoes.filter(valor='ND').exists())     # opção criada pela ação foi removida
        self.assertEqual(Resposta.objects.filter(valor='ND', conforme__isnull=True).count(), 2)

    def test_opcao_criada_e_mantida_se_outros_lancamentos_a_usam(self):
        self.preparar(valor='ND')
        self.vincular('ND', 'novo:ok')
        aj = AjusteVinculo.objects.get()
        ver = Verificacao.objects.create(pagina=self.item.pagina, data=date(2026, 5, 1), turno=Turno.objects.get(sigla='T1'))
        Resposta.objects.create(verificacao=ver, campo=self.item, valor='ND', conforme=True)   # lançamento novo, feito depois
        self.desfazer(aj)
        self.assertTrue(self.item.lista.opcoes.filter(valor='ND').exists())    # ainda em uso: mantida
        self.assertEqual(Resposta.objects.filter(valor='ND', verificacao=ver).count(), 1)

    def test_desfazer_parcial_mantem_lancamentos_editados_depois(self):
        self.preparar()
        nao = self.real.opcoes.get(valor='Não realizado')
        self.vincular('falat', f'op:{nao.pk}')
        aj = AjusteVinculo.objects.get()
        editado = Resposta.objects.filter(valor='Não realizado').first()
        Resposta.objects.filter(pk=editado.pk).update(valor='Realizado', conforme=True)   # alguém corrigiu à mão
        self.desfazer(aj)
        self.assertEqual(Resposta.objects.filter(valor='falat').count(), 1)               # só o que continuava como o vínculo deixou
        self.assertEqual(Resposta.objects.get(pk=editado.pk).valor, 'Realizado')
        aj.refresh_from_db()
        self.assertTrue(aj.desfeito)

    def test_nao_desfaz_se_a_opcao_foi_removida(self):
        self.preparar()
        nao = self.real.opcoes.get(valor='Não realizado')
        self.vincular('falat', f'op:{nao.pk}')
        aj = AjusteVinculo.objects.get()
        nao.delete()  # a opção sumiu (os vínculos que apontam para ela também)
        aj.refresh_from_db()
        self.desfazer(aj)
        aj.refresh_from_db()
        self.assertFalse(aj.desfeito)

    def test_tela_lista_vinculos_e_filtra(self):
        self.preparar()
        nao = self.real.opcoes.get(valor='Não realizado')
        self.vincular('falat', f'op:{nao.pk}')
        self.vincular('falat', f'op:{nao.pk}', formulario=False)  # sem formulário: não aparece no histórico dele
        url = reverse('pcp:ajustes', args=[self.form_id])
        r = self.client.get(url)
        self.assertEqual([l['tipo'] for l in r.context['linhas']], ['vinculo'])
        self.assertContains(r, '«falat»')
        self.assertContains(r, 'Valores vinculados a opções')
        self.assertEqual(len(self.client.get(url + '?origem=vinculo').context['linhas']), 1)
        self.assertEqual(len(self.client.get(url + '?origem=tipo').context['linhas']), 0)

    def test_relatorio_da_importacao_informa_o_formulario(self):
        self.listas()
        self.estrutura()
        arq = SimpleUploadedFile('FOR.999.R03 - Teste.xlsx', self.planilha({(4, 8): 'Lofoam'}).read())
        r = self.client.post(reverse('pcp:importar_registros'), {'arquivo': arq, 'ano': 2026, 'simular': 'on'})
        self.assertContains(r, 'name="formulario"')


class StatusMaquinaTests(PendenciasBase):
    D = date(2026, 10, 22)  # quinta-feira

    def marcar(self, status, turno=None, data='2026-10-22', **extra):
        dados = {'data': data, 'turno': (turno or self.t1).pk, 'status': status, 'escopo': 'turno', **extra}
        return self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), dados)

    def devidos(self, turno, data=None):
        return set(pend.avaliar_pagina(self.pag, data or self.D, self.turnos)[turno.pk])

    def test_turno_marcado_dispensa_os_itens_por_turno_so_nele(self):
        self.assertIn(self.c_lista.pk, self.devidos(self.t1))
        self.marcar('manutencao', motivo='troca de ferramenta')
        v = Verificacao.objects.get(pagina=self.pag, data=self.D, turno=self.t1)
        self.assertEqual((v.status, v.motivo), ('manutencao', 'troca de ferramenta'))
        self.assertNotIn(self.c_lista.pk, self.devidos(self.t1))     # item por turno dispensado em T1
        self.assertIn(self.c_lista.pk, self.devidos(self.t2))        # T2 continua exigindo
        self.assertIn(self.c_num.pk, self.devidos(self.t1))          # diário: o dia não está todo parado

    def test_dia_inteiro_dispensa_itens_diarios(self):
        self.marcar('parada', escopo='dia')
        self.assertEqual(Verificacao.objects.filter(pagina=self.pag, data=self.D, status='parada').count(), 2)
        for t in self.turnos:
            self.assertNotIn(self.c_num.pk, self.devidos(t))         # diário dispensado
            self.assertIn(self.c_sem.pk, self.devidos(t))            # semanal: só um dia parado, ainda é devido

    def test_periodo_dispensa_semanal_quando_toda_a_janela_esta_parada(self):
        self.marcar('manutencao', escopo='dia', data='2026-10-19', ate='2026-10-25')   # semana inteira (seg-dom)
        self.assertEqual(Verificacao.objects.filter(pagina=self.pag, status='manutencao').count(), 14)
        self.assertNotIn(self.c_sem.pk, self.devidos(self.t1))      # semanal dispensado
        self.assertIn(self.c_mes.pk, self.devidos(self.t1))         # mensal: o resto do mês ainda conta
        # na quarta-feira da mesma semana, a janela até aquele dia também está toda marcada
        self.assertNotIn(self.c_sem.pk, self.devidos(self.t1, date(2026, 10, 21)))

    def test_voltar_a_operar_limpa_e_remove_verificacao_vazia(self):
        self.marcar('manutencao')
        self.marcar('')
        self.assertFalse(Verificacao.objects.filter(pagina=self.pag, data=self.D, turno=self.t1).exists())   # só existia pela situação
        self.assertIn(self.c_lista.pk, self.devidos(self.t1))
        self.marcar('parada')
        Resposta.objects.create(verificacao=Verificacao.objects.get(pagina=self.pag, data=self.D, turno=self.t1), campo=self.c_lista, valor='Ok')
        self.marcar('')
        v = Verificacao.objects.get(pagina=self.pag, data=self.D, turno=self.t1)   # tinha lançamento: é mantida, sem situação
        self.assertEqual(v.status, '')

    def test_so_na_revisao_vigente_e_status_valido(self):
        self.marcar('invalido')
        self.assertFalse(Verificacao.objects.exists())
        rascunho = self.v15.clonar('R16')
        pag16 = rascunho.paginas.get()
        self.client.post(reverse('pcp:preencher_status', args=[pag16.pk]), {'data': '2026-10-22', 'turno': self.t1.pk, 'status': 'parada', 'escopo': 'turno'})
        self.assertFalse(Verificacao.objects.exists())

    def test_vale_entre_revisoes_pelo_nome_da_pagina(self):
        self.marcar('manutencao')
        nova = self.v15.clonar('R16')
        nova.publicar()
        pag16 = nova.paginas.get()
        resultado = pend.avaliar_pagina(pag16, self.D, self.turnos)
        self.assertNotIn(pag16.campos.get(item='B-1').pk, resultado[self.t1.pk])

    def test_painel_atrasos_e_sino_respeitam_a_dispensa(self):
        from pcp import cobranca
        antes = pend.painel(self.D, self.turnos)['devidos']
        self.marcar('manutencao', escopo='dia')
        depois = pend.painel(self.D, self.turnos)
        self.assertLess(depois['devidos'], antes)
        celula = depois['blocos'][0]['grupos']['Fita'][0]['celulas'][0]
        self.assertEqual((celula['status'], celula['status_rotulo']), ('manutencao', 'Em Manutenção'))
        self.assertEqual(depois['blocos'][0]['grupos']['Fita'][0]['celulas'][0]['status'], 'manutencao')
        # atrasos: dia 21/10 todo parado não gera atraso (itens por turno e diário)
        self.v15.vigencia = date(2026, 10, 1)
        self.v15.save()
        self.marcar('parada', escopo='dia', data='2026-10-21')
        lista, devidos = pend.atrasos_pagina(self.pag, date(2026, 10, 21), date(2026, 10, 21), self.turnos, self.D)
        self.assertEqual((lista, devidos), ([], 0))

    def test_exportacao_preenche_todos_os_itens_do_turno_com_a_situacao(self):
        import openpyxl as xl
        self.marcar('manutencao')
        ver = Verificacao.objects.create(pagina=self.pag, data=self.D, turno=self.t2)
        Resposta.objects.create(verificacao=ver, campo=self.c_lista, valor='Nok', conforme=False)
        r = self.client.get(reverse('pcp:exportar_pagina', args=[self.pag.pk]) + '?mes=2026-10')
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        wb = xl.load_workbook(io.BytesIO(r.content))
        self.assertEqual(wb.sheetnames[0], 'Fitadeira')
        self.assertIn('Situação da máquina', wb.sheetnames)
        self.assertIn('Ocorrências', wb.sheetnames)
        ws = wb['Fitadeira']
        col = next(c for c in range(1, ws.max_column + 1) if ws.cell(row=4, column=c).value == '22/10')
        assert ws.cell(row=5, column=col).value == 'T1' and ws.cell(row=5, column=col + 1).value == 'T2'
        linhas = [r_ for r_ in range(6, ws.max_row + 1) if ws.cell(row=r_, column=2).value]   # coluna 1 = Nº, coluna 2 = Item
        self.assertGreaterEqual(len(linhas), 4)
        for l in linhas:   # TODOS os itens de T1 saem preenchidos com a situação
            self.assertEqual(ws.cell(row=l, column=col).value, 'Em Manutenção')
        self.assertEqual(ws.cell(row=6, column=col + 1).value, 'Nok')       # T2: o que foi lançado
        situacoes = [[c.value for c in row] for row in wb['Situação da máquina'].iter_rows(min_row=2)]
        self.assertEqual([s[3] for s in situacoes], ['Em Manutenção'])
        # exportação do formulário inteiro
        r = self.client.get(reverse('pcp:exportar_formulario', args=[self.form.pk]) + '?mes=2026-10')
        self.assertEqual(xl.load_workbook(io.BytesIO(r.content)).sheetnames[0], 'Fitadeira')
        self.assertEqual(self.client.get(reverse('pcp:exportar_pagina', args=[self.pag.pk]) + '?mes=lixo').status_code, 200)

    def test_tela_de_preenchimento_mostra_a_situacao(self):
        self.marcar('parada')
        url = reverse('pcp:preencher_pagina', args=[self.pag.pk]) + f'?data=2026-10-22&turno={self.t1.pk}'
        r = self.client.get(url)
        self.assertContains(r, 'Parada')
        self.assertContains(r, 'não são obrigatórios')
        # só este turno está parado: o item por turno é dispensado, mas diário, semanal e mensal seguem devidos
        self.assertEqual((r.context['status'], r.context['n_devidos']), ('parada', 3))
        self.assertFalse([l for l in r.context['linhas'] if l['campo'].pk == self.c_lista.pk and l['devido']])
        self.assertContains(r, reverse('pcp:exportar_pagina', args=[self.pag.pk]))   # formulário de exportação do mês


class StatusNaImportacaoTests(ValoresBase):
    def preparar(self, **celulas):
        self.estrutura()
        return self.registros(arquivo=self.planilha(celulas))

    def status(self, dia, turno):
        return Verificacao.objects.get(pagina__nome='Fitadeira', data=dia, turno__sigla=turno).status

    def test_item_em_manutencao_ou_parada_marca_o_turno(self):
        self.estrutura()
        r = self.registros(arquivo=self.planilha({(4, 9): 'Em Manut.', (4, 11): 'Máq. Parada'}))   # A-1: D5/T2 e D6/T1
        self.assertEqual(self.status(date(2026, 1, 5), 'T2'), 'manutencao')
        self.assertEqual(self.status(date(2026, 1, 6), 'T1'), 'parada')
        self.assertEqual(self.status(date(2026, 1, 5), 'T1'), '')              # turno sem marcação continua em operação
        self.assertEqual(r['status_marcados'], {'manutencao': 1, 'parada': 1})
        v = Verificacao.objects.get(pagina__nome='Fitadeira', data=date(2026, 1, 5), turno__sigla='T2')
        self.assertEqual(v.motivo, 'Importado da planilha')
        # os valores lançados continuam gravados, e o item do turno deixa de ser devido
        self.assertTrue(Resposta.objects.filter(verificacao=v, campo__item='B-12').exists())
        pagina = v.pagina
        t2 = Turno.objects.get(sigla='T2')
        devidos = pend.avaliar_pagina(pagina, date(2026, 1, 5), [t2])[t2.pk]
        self.assertFalse([pk for pk in devidos if Campo.objects.get(pk=pk).frequencia and Campo.objects.get(pk=pk).frequencia.periodicidade == 'turno'])

    def test_um_unico_item_basta_e_a_maioria_decide(self):
        self.estrutura()
        # mesmo turno (D5/T1): um item 'Manut.' e outro 'Parada' -> empate vira parada
        self.registros(arquivo=self.planilha({(4, 8): 'Manut.', (5, 8): 'Parada'}))
        self.assertEqual(self.status(date(2026, 1, 5), 'T1'), 'parada')

    def test_nao_sobrescreve_situacao_marcada_manualmente_e_simulacao_nao_grava(self):
        self.estrutura()
        r = self.registros(arquivo=self.planilha({(4, 9): 'Em Manut.'}), simular=True)
        self.assertEqual(r['status_marcados'], {'manutencao': 1})
        self.assertFalse(Verificacao.objects.exists())
        pagina = Pagina.objects.get(nome='Fitadeira')
        Verificacao.objects.create(pagina=pagina, data=date(2026, 1, 5), turno=Turno.objects.get(sigla='T2'), status='parada', motivo='manual')
        self.registros(arquivo=self.planilha({(4, 9): 'Em Manut.'}))
        v = Verificacao.objects.get(pagina=pagina, data=date(2026, 1, 5), turno__sigla='T2')
        self.assertEqual((v.status, v.motivo), ('parada', 'manual'))

    def test_relatorio_da_tela_informa_os_turnos_marcados(self):
        self.estrutura()
        arq = SimpleUploadedFile('FOR.999.R03 - Teste.xlsx', self.planilha({(4, 9): 'Em Manut.'}).read())
        r = self.client.post(reverse('pcp:importar_registros'), {'arquivo': arq, 'ano': 2026, 'simular': 'on'})
        self.assertContains(r, 'em manutenção')


class DashboardBase(PendenciasBase):
    HOJE = date(2026, 10, 22)
    INI, FIM = date(2026, 10, 12), date(2026, 10, 21)   # 10 dias, de segunda a quarta da semana seguinte

    def setUp(self):
        super().setUp()
        cache.clear()
        self.v15.vigencia = date(2026, 10, 1)
        self.v15.save()
        for dia in range(12, 17):                                 # T1 lançado nos dias 12 a 16 (5 de 20 prazos por turno)
            self.lancar(date(2026, 10, dia), self.t1, self.c_lista, 'Ok')
        for dia in (13, 14, 15, 19):                              # diário lançado em 4 dos 10 dias
            self.lancar(date(2026, 10, dia), self.t1, self.c_num, '-0,7')
        self.lancar(date(2026, 10, 14), self.t1, self.c_sem, 'x')  # semanal da semana 12-18

    def lancar(self, dia, turno, campo, valor):
        ver, _ = Verificacao.objects.get_or_create(pagina=self.pag, data=dia, turno=turno)
        Resposta.objects.create(verificacao=ver, campo=campo, valor=valor)

    def dash(self, **kw):
        return pend.dashboard(self.INI, self.FIM, self.turnos, hoje=self.HOJE, **kw)


class DashboardTests(DashboardBase):
    def test_cumprimento_por_pagina_e_frequencia(self):
        d = self.dash()
        self.assertEqual([c['nome'] for c in d['colunas']], ['Turno', 'Diária', 'Semanal'])   # mensal sem prazo encerrado no período: não aparece
        self.assertEqual((d['devidos'], d['feitos'], d['atrasados'], d['pct']), (31, 10, 21, 32))
        linha = d['blocos'][0]['grupos'][0]['linhas'][0]
        self.assertEqual(linha['nome'], 'Fitadeira')
        self.assertEqual(linha['celulas'], [{'devidos': 20, 'feitos': 5, 'pct': 25}, {'devidos': 10, 'feitos': 4, 'pct': 40},
                                            {'devidos': 1, 'feitos': 1, 'pct': 100}])
        self.assertEqual([(f['nome'], f['devidos'], f['feitos']) for f in d['por_frequencia']],
                         [('Turno', 20, 5), ('Diária', 10, 4), ('Semanal', 1, 1)])
        self.assertEqual((d['blocos'][0]['codigo'], d['blocos'][0]['pct']), ('FOR.080', 32))

    def test_evolucao_por_dia_e_por_semana(self):
        d = self.dash()
        self.assertEqual(d['agrupamento'], 'dia')
        self.assertEqual(len(d['evolucao']), 10)
        self.assertEqual(sum(e['devidos'] for e in d['evolucao']), 31)
        longo = pend.dashboard(date(2026, 8, 1), self.FIM, self.turnos, hoje=self.HOJE)
        self.assertEqual(longo['agrupamento'], 'semana')
        self.assertTrue(all(e['rotulo'].startswith('sem.') for e in longo['evolucao']))

    def test_maquina_parada_tira_os_itens_do_calculo(self):
        antes = self.dash()
        Verificacao.objects.filter(pagina=self.pag, data=date(2026, 10, 12), turno=self.t1).update(status='parada')
        depois = self.dash()
        self.assertEqual(depois['devidos'], antes['devidos'] - 1)   # só o item por turno de T1 em 12/10 (o diário ainda é devido: T2 opera)
        self.assertEqual(depois['paradas'], 1)
        self.assertEqual(antes['paradas'], 0)

    def test_rastreio_e_hoje_nao_entram(self):
        self.v15.vigencia = date(2026, 10, 20)
        self.v15.save()
        d = self.dash()
        self.assertEqual(d['colunas'][0]['nome'], 'Turno')
        self.assertLess(d['devidos'], 31)               # antes da vigência nada é cobrado
        hoje_dentro = pend.dashboard(self.INI, date(2026, 10, 30), self.turnos, hoje=self.HOJE)
        self.assertEqual(hoje_dentro['fim'], date(2026, 10, 21))   # o dia corrente fica de fora

    def test_filtro_por_formulario_e_sem_dados(self):
        outro = Formulario.objects.create(setor=self.setor, codigo='FOR.777', titulo='Outro')
        self.assertEqual(len(self.dash()['blocos']), 1)           # formulário sem revisão vigente não aparece
        self.assertEqual(self.dash(formulario_id=self.form.pk)['devidos'], 31)
        self.assertEqual(self.dash(formulario_id=outro.pk)['blocos'], [])

    def test_tela_cache_e_atualizar(self):
        url = reverse('pcp:dashboard')
        r = self.client.get(url + '?dias=30')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'dados-dashboard')
        self.assertContains(r, 'Cumprimento por frequência')
        self.assertEqual(self.client.get(url + '?dias=abc&formulario=x&ate=lixo').status_code, 200)
        self.assertEqual(self.client.get(url + '?atualizar=1').status_code, 200)
        self.assertIn('d', r.context)

    def test_tela_com_dados_mostra_a_pagina_com_link_para_atrasos(self):
        r = self.client.get(reverse('pcp:dashboard') + f'?dias=30&ate={self.FIM}')   # a tela calcula com o relógio real
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['d']['fim'], self.FIM)
        self.assertContains(r, 'Fitadeira')   # farol dos prazos em andamento
        self.assertContains(r, 'Em atraso')
        self.assertNotContains(r, 'Menor cumprimento')


class RankingDashboardTests(DashboardBase):
    def setUp(self):
        super().setUp()
        # item por turno com 12 de 20 prazos cumpridos (60%, 8 atrasos): fica entre os dois itens do dashboard em %, mas com mais atrasos que o diário
        self.c_extra = Campo.objects.create(pagina=self.pag, item='E-9', descricao='Extra por turno', tipo='texto', frequencia=self.f_turno)
        for dia in range(12, 18):
            for turno in self.turnos:
                self.lancar(date(2026, 10, dia), turno, self.c_extra, 'x')

    def rank(self, ordem='pct', top=10):
        return pend.ranking(self.dash(), ordem, top)

    def test_itens_ordenados_por_menor_cumprimento(self):
        _, itens = self.rank('pct')
        # c_lista 5/20 = 25%, c_num 4/10 = 40%, c_extra 12/20 = 60%; o semanal (1 prazo) não tem prazos suficientes
        self.assertEqual([(i['item'], i['pct']) for i in itens], [('B-1', 25), (self.c_num.item, 40), ('E-9', 60)])
        self.assertEqual(itens[0]['atrasados'], 15)
        self.assertEqual((itens[0]['pagina'], itens[0]['codigo'], itens[0]['frequencia']), ('Fitadeira', 'FOR.080', 'Turno'))

    def test_ordenar_por_mais_atrasos(self):
        _, por_pct = self.rank('pct')
        _, por_atrasos = self.rank('atrasos')
        self.assertEqual([i['item'] for i in por_atrasos], ['B-1', 'E-9', self.c_num.item])   # 15, 8 e 6 atrasos
        self.assertNotEqual([i['item'] for i in por_pct], [i['item'] for i in por_atrasos])

    def test_paginas_com_minimo_de_prazos_e_top(self):
        paginas, _ = self.rank()
        self.assertEqual([(p['nome'], p['codigo']) for p in paginas], [('Fitadeira', 'FOR.080')])
        outra = Pagina.objects.create(versao=self.v15, nome='Pouco uso', grupo='Fita')
        Campo.objects.create(pagina=outra, item='X', descricao='x', tipo='texto', frequencia=self.f_sem)   # 1 prazo semanal: abaixo do mínimo
        self.assertEqual([p['nome'] for p in self.rank()[0]], ['Fitadeira'])
        _, itens = self.rank(top=2)
        self.assertEqual(len(itens), 2)

    def test_pagina_pior_primeiro(self):
        pior = Pagina.objects.create(versao=self.v15, nome='Pior', grupo='Fita')
        Campo.objects.create(pagina=pior, item='P-1', descricao='Nunca preenchido', tipo='texto', frequencia=self.f_dia)   # 10 prazos, 0 feitos
        paginas, itens = self.rank()
        self.assertEqual([(p['nome'], p['pct']) for p in paginas][0], ('Pior', 0))
        self.assertEqual(itens[0]['item'], 'P-1')

class DesativarDoRankingTests(DashboardBase):
    def desativar(self, pagina=None, **extra):
        return self.client.post(reverse('pcp:pagina_desativar', args=[(pagina or self.pag).pk]), extra)

    def test_desativa_volta_para_o_dashboard_com_os_filtros_e_mantem_o_historico(self):
        url = reverse('pcp:dashboard') + f'?dias=14&ate={self.FIM}&ordem=atrasos&top=20'
        r = self.desativar(next=url)
        self.assertRedirects(r, url, fetch_redirect_response=False)
        self.pag.refresh_from_db()
        self.assertFalse(self.pag.ativo)
        self.assertTrue(Resposta.objects.filter(campo=self.c_lista).exists())   # histórico preservado

    def test_some_do_dashboard_na_hora_apesar_do_cache(self):
        url = reverse('pcp:dashboard') + f'?dias=30&ate={self.FIM}'
        self.assertTrue(self.client.get(url).context['d']['blocos'][0]['grupos'])   # popula o cache
        self.desativar()
        r = self.client.get(url)                                                # sem esperar os 2 minutos do cache
        self.assertEqual(r.context['d']['blocos'][0]['grupos'], [])

    def test_vale_para_o_rascunho_de_mesmo_nome_e_nao_reativa(self):
        rascunho = self.v15.clonar('R16')
        self.desativar()
        self.assertFalse(rascunho.paginas.get(nome='Fitadeira').ativo)
        self.desativar()   # de novo: continua desativada (não alterna)
        self.pag.refresh_from_db()
        self.assertFalse(self.pag.ativo)

    def test_next_externo_e_ignorado_e_get_nao_e_permitido(self):
        r = self.desativar(next='https://site-malicioso.example/x')
        self.assertRedirects(r, reverse('pcp:pagina_detalhe', args=[self.pag.pk]), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('pcp:pagina_desativar', args=[self.pag.pk])).status_code, 405)

    def test_reativar_pelo_gerenciador_traz_a_pagina_de_volta_ao_dashboard(self):
        url = reverse('pcp:dashboard') + f'?dias=30&ate={self.FIM}'
        self.client.get(url)
        self.desativar()
        self.client.post(reverse('pcp:paginas_acao', args=[self.form.pk]), {'paginas': [self.pag.pk], 'acao': 'ativar'})
        self.assertTrue(self.client.get(url).context['d']['blocos'][0]['grupos'])


class RegrasDePrazoTests(TestCase):
    """Regras de prazo por frequência (qualquer turno vale; quinzena e trimestre/semestre fixos)."""

    def test_semana_de_segunda_a_domingo(self):
        self.assertEqual(pend.janela('semanal', date(2026, 10, 25)), (date(2026, 10, 19), date(2026, 10, 25)))   # domingo
        self.assertEqual(pend.janela('semanal', date(2026, 10, 26)), (date(2026, 10, 26), date(2026, 11, 1)))    # segunda: nova semana

    def test_quinzena_acompanha_o_fim_do_mes(self):
        self.assertEqual(pend.janela('quinzenal', date(2026, 1, 15)), (date(2026, 1, 1), date(2026, 1, 15)))
        self.assertEqual(pend.janela('quinzenal', date(2026, 1, 16)), (date(2026, 1, 16), date(2026, 1, 31)))
        self.assertEqual(pend.janela('quinzenal', date(2026, 4, 20)), (date(2026, 4, 16), date(2026, 4, 30)))      # mês de 30 dias
        self.assertEqual(pend.janela('quinzenal', date(2026, 2, 28)), (date(2026, 2, 16), date(2026, 2, 28)))      # fevereiro
        self.assertEqual(pend.janela('quinzenal', date(2028, 2, 20)), (date(2028, 2, 16), date(2028, 2, 29)))      # bissexto
        self.assertEqual(pend.janela('quinzenal', date(2026, 12, 31)), (date(2026, 12, 16), date(2026, 12, 31)))

    def test_trimestre_com_referencias_fixas(self):
        esperado = {1: (1, 3), 3: (1, 3), 4: (4, 6), 6: (4, 6), 7: (7, 9), 9: (7, 9), 10: (10, 12), 12: (10, 12)}
        for mes, (m0, m1) in esperado.items():
            ini, fim = pend.janela('trimestral', date(2026, mes, 15))
            self.assertEqual((ini.month, ini.day, fim.month), (m0, 1, m1), mes)
        self.assertEqual(pend.janela('trimestral', date(2026, 9, 30))[1], date(2026, 9, 30))
        self.assertEqual(pend.janela('trimestral', date(2026, 10, 1))[0], date(2026, 10, 1))

    def test_semestre_com_referencias_fixas(self):
        self.assertEqual(pend.janela('semestral', date(2026, 6, 30)), (date(2026, 1, 1), date(2026, 6, 30)))
        self.assertEqual(pend.janela('semestral', date(2026, 7, 1)), (date(2026, 7, 1), date(2026, 12, 31)))
        self.assertEqual(pend.janela('semestral', date(2026, 12, 31)), (date(2026, 7, 1), date(2026, 12, 31)))

    def test_rotulos_dos_prazos(self):
        d = date(2026, 10, 22)
        self.assertEqual(pend.rotulo_janela('semanal', d), '19/10–25/10')
        self.assertEqual(pend.rotulo_janela('quinzenal', d), '16/10–31/10')
        self.assertEqual(pend.rotulo_janela('mensal', d), 'out/2026')
        self.assertEqual(pend.rotulo_janela('trimestral', d), 'out–dez/2026')
        self.assertEqual(pend.rotulo_janela('semestral', d), 'jul–dez/2026')
        self.assertEqual(pend.rotulo_janela('anual', d), '2026')
        self.assertEqual(pend.rotulo_janela('turno', d), '22/10')


class FarolTests(PendenciasBase):
    D = date(2026, 10, 22)  # quinta-feira

    def setUp(self):
        super().setUp()
        self.v15.vigencia = date(2026, 10, 1)
        self.v15.save()

    def agora(self, h=10, m=0, dia=22):
        return timezone.make_aware(datetime.datetime(2026, 10, dia, h, m))

    def lancar(self, dia, turno, campo, valor='x'):
        ver, _ = Verificacao.objects.get_or_create(pagina=self.pag, data=dia, turno=turno)
        Resposta.objects.create(verificacao=ver, campo=campo, valor=valor)

    def farol(self, data=None, **kw):
        data = data or self.D
        return pend.farol(data, hoje=self.D, agora=self.agora(**kw))

    def celulas(self, f):
        """{nome da frequência: célula} da única página."""
        linha = f['blocos'][0]['grupos'][0]['linhas'][0]
        return {col['nome']: c for col, c in zip(f['colunas'], linha['celulas']) if c}

    def test_prazos_em_aberto_ficam_amarelos_e_cumpridos_verdes(self):
        c = self.celulas(self.farol())
        self.assertEqual({k: v['cor'] for k, v in c.items()}, {'Turno': 'amarelo', 'Diária': 'amarelo', 'Semanal': 'amarelo', 'Mensal': 'amarelo'})
        self.assertEqual((c['Turno']['devidos'], c['Turno']['feitos']), (2, 0))      # T1 e T2 já iniciados (sem horário cadastrado)
        self.assertIn('vence em 3 dia(s)', c['Semanal']['dica'])
        self.assertIn('vence em 9 dia(s)', c['Mensal']['dica'])
        self.assertIn('vence hoje', c['Diária']['dica'])

    def test_basta_um_registro_em_qualquer_turno_da_semana(self):
        self.lancar(date(2026, 10, 25), self.t2, self.c_sem)            # domingo, T2: ainda dentro da semana 19-25
        c = self.celulas(self.farol())
        self.assertEqual((c['Semanal']['cor'], c['Semanal']['feitos']), ('verde', 1))
        self.assertIn('Cumprido', c['Semanal']['dica'])
        self.lancar(date(2026, 10, 18), self.t1, self.c_mes)            # outro mês/semana não vale para a semana, mas vale para o mês
        c = self.celulas(self.farol())
        self.assertEqual(c['Mensal']['cor'], 'verde')

    def test_registro_da_semana_anterior_nao_vale(self):
        self.lancar(date(2026, 10, 18), self.t1, self.c_sem)            # domingo da semana anterior
        self.assertEqual(self.celulas(self.farol())['Semanal']['cor'], 'amarelo')

    def test_data_passada_com_prazo_encerrado_fica_vermelha(self):
        c = self.celulas(self.farol(data=date(2026, 10, 14)))           # semana 12-18 já encerrou
        self.assertEqual({k: v['cor'] for k, v in c.items()}, {'Turno': 'vermelho', 'Diária': 'vermelho', 'Semanal': 'vermelho', 'Mensal': 'amarelo'})
        self.assertIn('Prazo encerrado', c['Semanal']['dica'])
        self.lancar(date(2026, 10, 16), self.t2, self.c_sem)
        self.assertEqual(self.celulas(self.farol(data=date(2026, 10, 14)))['Semanal']['cor'], 'verde')

    def test_turno_encerrado_sem_registro_fica_vermelho(self):
        for t, ini, fim in ((self.t1, time(6), time(14)), (self.t2, time(14), time(22))):
            t.inicio, t.fim = ini, fim
            t.save()
        c = self.celulas(self.farol(h=15))                              # T1 já terminou, T2 em andamento
        self.assertEqual((c['Turno']['cor'], c['Turno']['devidos']), ('vermelho', 2))
        self.lancar(self.D, self.t1, self.c_lista)
        self.assertEqual(self.celulas(self.farol(h=15))['Turno']['cor'], 'amarelo')   # só T2 pendente e ainda em andamento
        self.lancar(self.D, self.t2, self.c_lista)
        self.assertEqual(self.celulas(self.farol(h=15))['Turno']['cor'], 'verde')
        self.assertEqual(self.celulas(self.farol(h=8))['Turno']['devidos'], 1)   # 8h: só T1 iniciado

    def test_vigencia_e_dispensa_e_futuro(self):
        self.v15.vigencia = date(2026, 10, 26)                          # a semana 19-25 encerrou antes da vigência: não é cobrada
        self.v15.save()
        c = self.celulas(self.farol())
        self.assertNotIn('Semanal', c)
        self.assertIn('Mensal', c)                                      # o mês termina depois da vigência
        self.v15.vigencia = date(2026, 10, 1)
        self.v15.save()
        self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), {'data': '2026-10-22', 'turno': self.t1.pk, 'status': 'parada', 'escopo': 'dia'})
        c = self.celulas(self.farol())
        self.assertNotIn('Turno', c)                                    # dia todo parado: itens por turno e diários dispensados
        self.assertNotIn('Diária', c)
        self.assertEqual(pend.farol(date(2026, 10, 30), hoje=self.D, agora=self.agora())['contagem']['vermelho'], 0)  # futuro: nada vencido

    def test_contagem_e_cor_da_pagina(self):
        f = self.farol(data=date(2026, 10, 14))
        self.assertEqual(f['contagem'], {'verde': 0, 'amarelo': 1, 'vermelho': 3})
        self.assertEqual(f['blocos'][0]['grupos'][0]['linhas'][0]['cor'], 'vermelho')   # pior situação da página
        self.assertEqual([(c['nome'], c['prazo']) for c in f['colunas']],
                         [('Turno', '14/10'), ('Diária', '14/10'), ('Semanal', '12/10–18/10'), ('Mensal', 'out/2026')])

    def test_tela_mostra_o_farol_e_aceita_a_data_de_observacao(self):
        url = reverse('pcp:dashboard')
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Farol dos prazos em andamento')
        self.assertContains(r, 'Basta um registro em qualquer turno')
        self.assertEqual(self.client.get(url + '?observar=2026-10-14').context['observar'], date(2026, 10, 14))
        self.assertEqual(self.client.get(url + '?observar=lixo').status_code, 200)


class NumeracaoTests(PcpBase):
    """Itens com Nº de 1 a n em cada bloco (identifica e ordena); páginas numeradas de 1 a n em cada grupo."""

    def setUp(self):
        super().setUp()
        for c, n in ((self.c_lista, 1), (self.c_num, 2)):
            Campo.objects.filter(pk=c.pk).update(ordem=n)
        self.c3 = Campo.objects.create(pagina=self.pag, item='C-3', descricao='Terceiro', tipo='texto', ordem=3)
        self.v15.publicar()

    def numeros(self, pagina=None):
        return [(c.item, c.ordem) for c in (pagina or self.pag).campos.order_by('ordem', 'pk')]

    def test_importador_numera_itens_de_1_a_n_e_paginas_de_1_a_n_por_grupo(self):
        r = importar_planilha(_planilha_modelo(), nome_arquivo='FOR.999.R03 - x.xlsx', setor=self.setor)
        for pagina in r['versao'].paginas.all():
            self.assertEqual([c.ordem for c in pagina.campos.order_by('ordem')], list(range(1, pagina.campos.count() + 1)))
        for grupo in set(r['versao'].paginas.values_list('grupo', flat=True)):
            nums = sorted(r['versao'].paginas.filter(grupo=grupo).values_list('ordem', flat=True))
            self.assertEqual(nums, list(range(1, len(nums) + 1)), grupo)

    def test_mover_item_com_setas_e_numero_digitado(self):
        url = lambda c: reverse('pcp:campo_mover', args=[c.pk])
        self.client.post(url(self.c3), {'dir': 'up'})
        self.assertEqual(self.numeros(), [('B-1', 1), ('C-3', 2), ('B-5', 3)])
        self.client.post(url(self.c_lista), {'posicao': '3'})                       # digita o Nº
        self.assertEqual(self.numeros(), [('C-3', 1), ('B-5', 2), ('B-1', 3)])
        self.client.post(url(self.c_lista), {'dir': 'down'})                        # já é o último: nada muda
        self.assertEqual([n for _, n in self.numeros()], [1, 2, 3])
        self.client.post(url(self.c_num), {'posicao': '99'})                        # fora do intervalo vai para o fim
        self.assertEqual(self.numeros()[-1], ('B-5', 3))
        self.client.post(url(self.c_num), {'posicao': 'x'})                         # inválido: ignorado
        self.assertEqual(self.numeros()[-1], ('B-5', 3))

    def test_mover_vale_na_revisao_vigente_e_propaga_ao_rascunho(self):
        rascunho = self.v15.clonar('R16')
        self.client.post(reverse('pcp:campo_mover', args=[self.c3.pk]), {'posicao': '1'})   # a revisão vigente está travada: mover é permitido
        self.assertEqual(self.numeros()[0], ('C-3', 1))
        self.assertEqual(self.numeros(rascunho.paginas.get())[0], ('C-3', 1))

    def test_excluir_renumera_e_novo_item_entra_no_fim_ou_na_posicao(self):
        rascunho = self.v15.clonar('R16')
        pag16 = rascunho.paginas.get()
        self.client.post(reverse('pcp:campo_excluir', args=[pag16.campos.get(item='B-1').pk]))
        self.assertEqual(self.numeros(pag16), [('B-5', 1), ('C-3', 2)])                    # renumerado sem buraco
        self.client.post(reverse('pcp:campo_novo', args=[pag16.pk]), {'descricao': 'Novo', 'tipo': 'texto', 'ordem': 0, 'ativo': 'on'})
        self.assertEqual(self.numeros(pag16)[-1][1], 3)                                    # ordem 0/vazia: fim do bloco
        self.client.post(reverse('pcp:campo_novo', args=[pag16.pk]), {'item': 'N-2', 'descricao': 'No início', 'tipo': 'texto', 'ordem': 1, 'ativo': 'on'})
        self.assertEqual(self.numeros(pag16)[0], ('N-2', 1))
        self.assertEqual([n for _, n in self.numeros(pag16)], [1, 2, 3, 4])   # 3 itens - 1 excluído + 2 criados

    def test_editar_o_numero_do_item_reposiciona_os_demais(self):
        rascunho = self.v15.clonar('R16')
        pag16 = rascunho.paginas.get()
        c = pag16.campos.get(item='C-3')
        self.client.post(reverse('pcp:campo_editar', args=[c.pk]), {'item': 'C-3', 'descricao': 'Terceiro', 'tipo': 'texto', 'ordem': 1, 'ativo': 'on'})
        self.assertEqual(self.numeros(pag16), [('C-3', 1), ('B-1', 2), ('B-5', 3)])

    def test_paginas_numeradas_por_grupo(self):
        outra = Pagina.objects.create(versao=self.v15, nome='Outra', grupo='Fita', ordem=0)
        terceira = Pagina.objects.create(versao=self.v15, nome='Terceira', grupo='Fita', ordem=0)
        self.v15.formulario.renumerar_paginas(self.v15)
        self.assertEqual(sorted(self.v15.paginas.filter(grupo='Fita').values_list('ordem', flat=True)), [1, 2, 3])
        self.client.post(reverse('pcp:pagina_editar', args=[terceira.pk]), {'grupo': 'Fita', 'ordem': 1, 'nome': 'Terceira', 'codigo_sistema': '', 'ativo': 'on'})
        self.assertEqual(list(self.v15.paginas.filter(grupo='Fita').order_by('ordem').values_list('nome', 'ordem'))[0], ('Terceira', 1))
        self.client.post(reverse('pcp:paginas_acao', args=[self.form.pk]), {'paginas': [outra.pk], 'acao': 'mover', 'destino': '__novo__', 'novo_nome': 'Corte'})
        self.assertEqual(sorted(self.v15.paginas.filter(grupo='Fita').values_list('ordem', flat=True)), [1, 2])   # o grupo de origem foi renumerado
        self.assertEqual(list(self.v15.paginas.filter(grupo='Corte').values_list('ordem', flat=True)), [1])

    def test_migracao_renumera_dados_antigos(self):
        from django.apps import apps
        from importlib import import_module
        Campo.objects.filter(pagina=self.pag).update(ordem=0)                 # dados antigos: tudo zero, sem ordem
        Campo.objects.filter(pk=self.c3.pk).update(ordem=7)
        Pagina.objects.filter(pk=self.pag.pk).update(ordem=9)
        import_module('pcp.migrations.0009_numeracao_blocos').renumerar(apps, None)
        self.assertEqual([n for _, n in self.numeros()], [1, 2, 3])
        self.assertEqual(self.numeros()[-1][0], 'C-3')                        # manteve a ordem relativa (o 7 vem por último)
        self.pag.refresh_from_db()
        self.assertEqual(self.pag.ordem, 1)

    def test_numero_aparece_nas_telas_e_na_planilha(self):
        import openpyxl as xl
        r = self.client.get(reverse('pcp:pagina_detalhe', args=[self.pag.pk]))
        self.assertContains(r, reverse('pcp:campo_mover', args=[self.c3.pk]))
        self.assertContains(r, 'name="posicao"')
        r = self.client.get(reverse('pcp:exportar_pagina', args=[self.pag.pk]) + '?mes=2026-10')
        ws = xl.load_workbook(io.BytesIO(r.content))['Fitadeira']
        self.assertEqual([ws.cell(row=4, column=1).value, ws.cell(row=4, column=2).value], ['Nº', 'Item'])
        self.assertEqual([(ws.cell(row=l, column=1).value, ws.cell(row=l, column=2).value) for l in (6, 7, 8)], [(1, 'B-1'), (2, 'B-5'), (3, 'C-3')])


class VigenciaEditavelTests(PendenciasBase):
    """Antes da vigência 'a cada turno' e diária não são cobrados; ajustar a vigência traz o histórico de volta."""
    D = date(2026, 10, 22)

    def setUp(self):
        super().setUp()
        cache.clear()
        self.v15.vigencia = date(2026, 10, 22)      # publicada em 22/10 (como no ambiente real)
        self.v15.save()

    def farol(self, data):
        agora = timezone.make_aware(datetime.datetime(2026, 10, 23, 10, 0))
        f = pend.farol(data, hoje=date(2026, 10, 23), agora=agora)
        linha = f['blocos'][0]['grupos'][0]['linhas'][0]
        return f, {col['nome']: c for col, c in zip(f['colunas'], linha['celulas']) if c}

    def test_antes_da_vigencia_so_aparecem_prazos_que_terminam_depois(self):
        f, c = self.farol(date(2026, 10, 20))
        self.assertEqual(sorted(c), ['Mensal', 'Semanal'])          # turno e diária terminam em 20/10, antes da vigência (22/10)
        self.assertEqual(f['blocos'][0]['rastreio'], date(2026, 10, 22))
        self.assertEqual(f['blocos'][0]['versao_id'], self.v15.pk)

    def test_ajustar_a_vigencia_traz_os_demais_de_volta(self):
        url = reverse('pcp:versao_vigencia', args=[self.v15.pk])
        r = self.client.post(url, {'vigencia': '2026-10-01'})
        self.assertRedirects(r, reverse('pcp:versao_detalhe', args=[self.v15.pk]))
        self.v15.refresh_from_db()
        self.assertEqual(self.v15.vigencia, date(2026, 10, 1))
        _, c = self.farol(date(2026, 10, 20))
        self.assertEqual(sorted(c), ['Diária', 'Mensal', 'Semanal', 'Turno'])

    def test_vigencia_invalida_ou_vazia_e_ignorada(self):
        url = reverse('pcp:versao_vigencia', args=[self.v15.pk])
        self.client.post(url, {'vigencia': ''})
        self.client.post(url, {'vigencia': '31/02/2026'})
        self.v15.refresh_from_db()
        self.assertEqual(self.v15.vigencia, date(2026, 10, 22))
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_a_menor_vigencia_entre_as_revisoes_vale(self):
        nova = self.v15.clonar('R16')
        self.client.post(reverse('pcp:versao_vigencia', args=[nova.pk]), {'vigencia': '2026-12-01'})   # posterior: não atrasa o rastreio
        self.assertEqual(pend.inicio_rastreio(self.form), date(2026, 10, 22))
        self.client.post(reverse('pcp:versao_vigencia', args=[nova.pk]), {'vigencia': '2026-09-01'})
        self.assertEqual(pend.inicio_rastreio(self.form), date(2026, 9, 1))

    def test_tela_avisa_quando_a_data_e_anterior_ao_rastreio(self):
        url = reverse('pcp:dashboard') + '?observar=2026-10-20'
        r = self.client.get(url)
        self.assertContains(r, 'anterior ao início do rastreio')
        self.assertContains(r, reverse('pcp:versao_detalhe', args=[self.v15.pk]))
        self.client.post(reverse('pcp:versao_vigencia', args=[self.v15.pk]), {'vigencia': '2026-10-01'})
        self.assertNotContains(self.client.get(url), 'anterior ao início do rastreio')    # o cache do dashboard foi invalidado

    def test_tela_da_revisao_mostra_o_campo_de_vigencia(self):
        r = self.client.get(reverse('pcp:versao_detalhe', args=[self.v15.pk]))
        self.assertContains(r, 'name="vigencia"')
        self.assertContains(r, 'value="2026-10-22"')


class ExportacaoDadosTests(PendenciasBase):
    D = date(2026, 10, 22)

    def setUp(self):
        super().setUp()
        for n, c in enumerate([self.c_lista, self.c_num, self.c_sem, self.c_mes, self.c_ev, self.c_sem0], 1):
            Campo.objects.filter(pk=c.pk).update(ordem=n)
        Campo.objects.filter(pk=self.c_num.pk).update(item='B-5')

    def baixar(self, nome='exportar_dados_pagina', pk=None, **params):
        import openpyxl as xl
        r = self.client.get(reverse(f'pcp:{nome}', args=[pk or self.pag.pk]), params)
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        wb = xl.load_workbook(io.BytesIO(r.content))
        return wb, list(wb['EXPORTAÇÃO'].iter_rows(values_only=True))

    def lancar(self, dia, turno, campo, valor):
        ver, _ = Verificacao.objects.get_or_create(pagina=self.pag, data=dia, turno=turno)
        Resposta.objects.create(verificacao=ver, campo=campo, valor=valor)

    def test_formato_dados_uma_linha_por_item_data_e_turno(self):
        wb, linhas = self.baixar(de='2026-10-22')
        self.assertEqual(wb.sheetnames, ['EXPORTAÇÃO'])
        self.assertEqual(linhas[0], ('Formulário', 'Grupo', 'Página', 'ORD', 'Item', 'Data', 'Turno', 'Valor'))
        dados = linhas[1:]
        self.assertEqual(len(dados), 6 * 2)                                       # 6 itens x 1 dia x 2 turnos (T1, T2), mesmo sem valor
        self.assertEqual(dados[0], ('FOR.080', 'Fita', 'Fitadeira', 1, 'B-1', datetime.datetime(2026, 10, 22), 'T1', None))
        self.assertEqual([(l[6], l[3]) for l in dados], [('T1', n) for n in range(1, 7)] + [('T2', n) for n in range(1, 7)])  # por turno e ORD

    def test_valores_numeros_e_ordenacao_por_data_e_turno(self):
        self.lancar(date(2026, 10, 22), self.t2, self.c_num, '-0,7')
        self.lancar(date(2026, 10, 23), self.t1, self.c_lista, 'Ok')
        _, linhas = self.baixar(de='2026-10-22', ate='2026-10-23')
        dados = linhas[1:]
        self.assertEqual(len(dados), 6 * 2 * 2)
        self.assertEqual([(l[5].day, l[6]) for l in dados[::6]], [(22, 'T1'), (22, 'T2'), (23, 'T1'), (23, 'T2')])   # data, depois turno
        num = [l for l in dados if l[4] == 'B-5' and l[5].day == 22 and l[6] == 'T2'][0]
        self.assertEqual(num[7], -0.7)                                            # número de verdade, não texto
        ok = [l for l in dados if l[4] == 'B-1' and l[5].day == 23 and l[6] == 'T1'][0]
        self.assertEqual(ok[7], 'Ok')

    def test_manutencao_e_parada_preenchem_todos_os_itens_do_turno(self):
        self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), {'data': '2026-10-22', 'turno': self.t1.pk, 'status': 'manutencao', 'escopo': 'turno'})
        self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), {'data': '2026-10-22', 'turno': self.t2.pk, 'status': 'parada', 'escopo': 'turno'})
        _, linhas = self.baixar(de='2026-10-22')
        self.assertEqual({l[7] for l in linhas[1:] if l[6] == 'T1'}, {'Em Manutenção'})
        self.assertEqual({l[7] for l in linhas[1:] if l[6] == 'T2'}, {'Parada'})

    def test_somente_com_valor(self):
        self.lancar(date(2026, 10, 22), self.t1, self.c_lista, 'Ok')
        _, linhas = self.baixar(de='2026-10-22', somente_valor='1')
        self.assertEqual([(l[4], l[6], l[7]) for l in linhas[1:]], [('B-1', 'T1', 'Ok')])

    def test_formulario_inteiro_na_ordem_dos_grupos_e_paginas(self):
        outra = Pagina.objects.create(versao=self.v15, nome='Outra', grupo='Corte', ordem=1)
        Campo.objects.create(pagina=outra, item='Z-1', descricao='z', tipo='texto', ordem=1)
        self.v15.formulario.garantir_grupo('Fita')
        _, linhas = self.baixar('exportar_dados_formulario', pk=self.form.pk, de='2026-10-22', somente_valor='')
        paginas = list(dict.fromkeys((l[1], l[2]) for l in linhas[1:]))
        self.assertEqual(paginas, [('Corte', 'Outra'), ('Fita', 'Fitadeira')])    # ordenado por grupo e página
        self.assertEqual({l[0] for l in linhas[1:]}, {'FOR.080'})

    def test_periodo_invertido_e_limite_de_93_dias_e_estimativa_de_linhas(self):
        _, linhas = self.baixar(de='2026-10-23', ate='2026-10-22')                # invertido: corrige
        self.assertEqual({l[5].day for l in linhas[1:]}, {22, 23})
        _, linhas = self.baixar(de='2026-01-01', ate='2026-12-31', somente_valor='1')   # limitado a 93 dias (e só com valor)
        self.assertEqual(len(linhas), 1)
        from pcp import exportacao
        antigo = exportacao.LIMITE_LINHAS_DADOS
        exportacao.LIMITE_LINHAS_DADOS = 10
        try:
            r = self.client.get(reverse('pcp:exportar_dados_pagina', args=[self.pag.pk]), {'de': '2026-10-22', 'ate': '2026-10-25'})
            self.assertRedirects(r, reverse('pcp:preencher_pagina', args=[self.pag.pk]), fetch_redirect_response=False)   # acima do limite: não gera
        finally:
            exportacao.LIMITE_LINHAS_DADOS = antigo

    def test_menu_exportar_nas_telas(self):
        r = self.client.get(reverse('pcp:preencher_pagina', args=[self.pag.pk]) + f'?data=2026-10-22&turno={self.t1.pk}')
        self.assertContains(r, reverse('pcp:exportar_dados_pagina', args=[self.pag.pk]))
        self.assertContains(r, reverse('pcp:exportar_pagina', args=[self.pag.pk]))
        r = self.client.get(reverse('pcp:formulario_detalhe', args=[self.form.pk]))
        self.assertContains(r, reverse('pcp:exportar_dados_formulario', args=[self.form.pk]))
        self.assertContains(r, 'Formato DADOS')


def _template_grade():
    """Template no modo grade: cabeçalho, linha âncora com NUM/ITEM/DESCRICAO e VALOR por dia/turno, rodapé e mesclagem abaixo da âncora."""
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'PCP'
    ws['A1'] = '{{FORMULARIO_CODIGO}} {{ REVISAO }} {{PAGINA}} - {{MES_NOME}}'
    ws['A2'] = 'Tag desconhecida: {{FOO}}'
    for j, t in enumerate(['Nº', 'Item', 'Descrição'], 1):
        ws.cell(row=4, column=j, value=t)
    ws['D4'], ws['F4'] = '{{DIA:1}}', '{{DIA:2}}'
    for col, sigla in zip('DEFG', ('T1', 'T2', 'T1', 'T2')):
        ws[f'{col}5'] = sigla
    ws['A6'], ws['B6'], ws['C6'] = '{{NUM}}', '{{ITEM}}', '{{DESCRICAO}}'
    ws['D6'], ws['E6'], ws['F6'], ws['G6'] = '{{VALOR:1:T1}}', '{{VALOR:1:T2}}', '{{VALOR:2:T1}}', '{{VALOR:2:2}}'   # T2 por sigla e por posição
    ws['A6'].font = Font(bold=True)
    ws['A6'].fill = PatternFill('solid', fgColor='EEEEEE')
    ws.row_dimensions[6].height = 30
    ws['A7'] = 'Total de itens: {{TOTAL_ITENS}}'
    ws.row_dimensions[7].height = 44
    ws['A9'] = 'Assinatura'
    ws.merge_cells('A9:C9')
    doc = wb.create_sheet('_DOC')
    doc['A1'] = 'Variável {{PAGINA}} (documentação: não vai para a saída)'
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _template_lista():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['Página', 'Nº', 'Item', 'Data', 'Turno', 'Valor', 'Situação'])
    ws.append(['{{PAGINA}}', '{{NUM}}', '{{ITEM}}', '{{DATA}}', '{{TURNO}}', '{{VALOR}}', '{{STATUS}}'])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TemplatesBase(PendenciasBase):
    def setUp(self):
        super().setUp()
        for n, c in enumerate([self.c_lista, self.c_num, self.c_sem, self.c_mes, self.c_ev, self.c_sem0], 1):
            Campo.objects.filter(pk=c.pk).update(ordem=n)
        self.p = Pagina.objects.get(pk=self.pag.pk)

    def lancar(self, dia, turno, campo, valor):
        ver, _ = Verificacao.objects.get_or_create(pagina=self.pag, data=dia, turno=turno)
        Resposta.objects.create(verificacao=ver, campo=campo, valor=valor, conforme=None)

    def dados(self):
        self.lancar(date(2026, 10, 1), self.t1, self.c_lista, 'Ok')
        self.lancar(date(2026, 10, 2), self.t2, self.c_num, '-0,7')
        self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), {'data': '2026-10-01', 'turno': self.t2.pk, 'status': 'manutencao', 'escopo': 'turno'})

    def gerar(self, conteudo, mes=10):
        from pcp import templates_xlsx
        saida = templates_xlsx.gerar(conteudo, self.form, self.v15, self.p, 2026, mes, hoje=date(2026, 11, 3))
        return openpyxl.load_workbook(io.BytesIO(saida.getvalue()))


class TemplatesXlsxTests(TemplatesBase):
    def test_analise_do_template(self):
        from pcp import templates_xlsx
        a = templates_xlsx.analisar(_template_grade())
        self.assertEqual(a['modo'], 'grade')
        self.assertIn('VALOR:2:2', a['tags'])
        self.assertIn('REVISAO', a['tags'])          # aceita espaços dentro das chaves
        self.assertEqual(a['desconhecidas'], ['FOO'])
        self.assertEqual(a['abas'], 1)                # a aba "_DOC" não conta
        self.assertEqual(templates_xlsx.analisar(_template_lista())['modo'], 'lista')
        for ruim in (b'nao e xlsx',):
            with self.assertRaises(ValueError):
                templates_xlsx.analisar(ruim)
        semtags = io.BytesIO()
        wb = openpyxl.Workbook()
        wb.active['A1'] = 'sem variáveis'
        wb.save(semtags)
        with self.assertRaises(ValueError):
            templates_xlsx.analisar(semtags.getvalue())

    def test_classificacao_das_tags(self):
        from pcp.templates_xlsx import classificar
        self.assertEqual([classificar(t) for t in ('PAGINA', 'DIA:31', 'DIA:32', 'NUM', 'VALOR:5:T3', 'VALOR', 'VALOR:5', 'XYZ', 'STATUS:1:2')],
                         ['escalar', 'dia', 'desconhecida', 'item', 'grade', 'lista', 'desconhecida', 'desconhecida', 'grade'])

    def test_modo_grade_preenche_cabecalho_repete_a_ancora_e_desloca_o_resto(self):
        self.dados()
        wb = self.gerar(_template_grade())
        self.assertEqual(wb.sheetnames, ['PCP'])      # a aba de documentação "_" não vai para a saída
        ws = wb['PCP']
        self.assertEqual(ws['A1'].value, 'FOR.080 R15 Fitadeira - outubro de 2026')
        self.assertEqual(ws['A2'].value, 'Tag desconhecida: {{FOO}}')          # desconhecida fica visível
        self.assertEqual((ws['D4'].value, ws['F4'].value), ('01/10', '02/10'))
        # âncora repetida para os 6 itens (linhas 6 a 11), com Nº, item e descrição
        self.assertEqual([ws.cell(row=r, column=1).value for r in range(6, 12)], [1, 2, 3, 4, 5, 6])
        self.assertEqual([ws.cell(row=r, column=2).value for r in range(6, 8)], ['B-1', 'B-5'])
        self.assertTrue(ws['A8'].font.b and ws['A11'].fill.fgColor.rgb.endswith('EEEEEE'))     # estilo copiado
        self.assertEqual(ws.row_dimensions[11].height, 30)
        # valores por dia e turno (T2 por sigla e por posição); manutenção preenche TODOS os itens do turno
        self.assertEqual(ws['D6'].value, 'Ok')                                  # B-1, 01/10, T1
        self.assertEqual([ws.cell(row=r, column=5).value for r in range(6, 12)], ['Em Manutenção'] * 6)   # 01/10, T2
        self.assertTrue(ws['E6'].fill.fgColor.rgb.endswith('FFE0B2'))           # laranja de manutenção
        self.assertEqual(ws['G7'].value, -0.7)                                  # B-5, 02/10, T2 via {{VALOR:2:2}}: número de verdade
        self.assertIn(ws['F6'].value, ('', None))                               # 02/10 T1 sem lançamento
        # o que estava abaixo da âncora foi deslocado em 5 linhas, com alturas e mesclagem
        self.assertEqual(ws['A12'].value, 'Total de itens: 6')
        self.assertEqual(ws.row_dimensions[12].height, 44)
        self.assertEqual(ws['A14'].value, 'Assinatura')
        self.assertIn('A14:C14', [str(m) for m in ws.merged_cells.ranges])

    def test_dias_que_o_mes_nao_tem_ficam_vazios(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws['A1'], ws['B1'] = '{{DIA:30}}', '{{DIASEMANA:1}}'
        ws['A2'], ws['B2'] = '{{ITEM}}', '{{VALOR:30:T1}}'
        buf = io.BytesIO()
        wb.save(buf)
        out = self.gerar(buf.getvalue(), mes=2)['Sheet']      # fevereiro de 2026 tem 28 dias
        self.assertIn(out['A1'].value, ('', None))
        self.assertEqual(out['B1'].value, 'dom')              # 01/02/2026 é domingo
        self.assertIn(out['B2'].value, ('', None))

    def test_modo_lista_so_com_slots_preenchidos_em_ordem(self):
        self.dados()
        ws = self.gerar(_template_lista()).active
        linhas = [[c.value for c in row] for row in ws.iter_rows(min_row=2)]
        self.assertEqual(len(linhas), 1 + 6 + 1)                                # Ok (01/10 T1) + 6 itens em manutenção (01/10 T2) + -0,7 (02/10 T2)
        self.assertEqual([l[3].day for l in linhas], [1] * 7 + [2])
        self.assertEqual([l[4] for l in linhas], ['T1'] + ['T2'] * 6 + ['T2'])
        self.assertEqual([l[1] for l in linhas[1:7]], [1, 2, 3, 4, 5, 6])      # ORD dentro do turno
        self.assertEqual((linhas[0][5], linhas[0][6] or ''), ('Ok', ''))   # texto vazio é lido de volta como vazio
        self.assertEqual((linhas[1][5], linhas[1][6]), ('Em Manutenção', 'Em Manutenção'))
        self.assertEqual(linhas[-1][5], -0.7)
        self.assertEqual(ws['D2'].number_format, 'dd/mm/yyyy')

    def test_sem_dados_limpa_a_linha_ancora(self):
        ws = self.gerar(_template_lista()).active
        self.assertEqual([c.value for c in ws[2]], [None] * 7)
        self.assertEqual(ws.max_row, 2)

    def test_modelo_de_exemplo_e_um_template_valido_de_ponta_a_ponta(self):
        from pcp import templates_xlsx
        amostra = templates_xlsx.gerar_amostra().getvalue()
        a = templates_xlsx.analisar(amostra)
        self.assertEqual((a['desconhecidas'], a['abas']), ([], 2))
        self.assertIn('VALOR:31:T1', a['tags'])
        self.dados()
        wb = self.gerar(amostra)
        self.assertEqual(wb.sheetnames, ['Página', 'Modo lista'])
        ws = wb['Página']
        self.assertEqual(ws['A1'].value, 'FOR.080 · R15 — Fitadeira')
        self.assertEqual(ws['A6'].value, 1)
        self.assertEqual(ws['F6'].value, 'Ok')            # dia 1, T1 (primeira coluna de valores)
        self.assertEqual(wb['Modo lista'].max_row, 1 + 8)


class TemplatesTelasTests(TemplatesBase):
    def enviar(self, conteudo=None, nome='FOR.080 PCP.xlsx', **extra):
        dados = {'formulario': self.form.pk, 'nome': 'Layout mensal', 'pagina_nome': '', 'descricao': 'teste',
                 'arquivo': SimpleUploadedFile(nome, conteudo if conteudo is not None else _template_grade()), **extra}
        return self.client.post(reverse('pcp:templates_pagina'), dados)

    def test_cadastro_guarda_o_arquivo_no_banco_e_analisa_as_tags(self):
        r = self.enviar()
        self.assertRedirects(r, reverse('pcp:templates_pagina'))
        t = TemplatePagina.objects.get()
        self.assertEqual((t.nome, t.formulario_id, t.pagina_nome, t.nome_arquivo_original), ('Layout mensal', self.form.pk, '', 'FOR.080 PCP.xlsx'))
        self.assertEqual((t.analise['modo'], t.analise['desconhecidas']), ('grade', ['FOO']))
        self.assertTrue(t.arquivo_base64 and t.criado_por)
        r = self.client.get(reverse('pcp:templates_pagina'))
        self.assertContains(r, 'Layout mensal')
        self.assertContains(r, '{{VALOR:1:T1}}')              # catálogo de variáveis na tela
        self.assertContains(r, 'não reconhecida')
        self.assertEqual(self.client.get(reverse('pcp:template_pagina_baixar', args=[t.pk])).content, _template_grade())

    def test_cadastro_recusa_arquivo_invalido_sem_variaveis_ou_grande_demais(self):
        r = self.enviar(b'isto nao e um xlsx')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(TemplatePagina.objects.exists())
        vazio = io.BytesIO()
        wb = openpyxl.Workbook()
        wb.active['A1'] = 'sem tags'
        wb.save(vazio)
        self.enviar(vazio.getvalue())
        self.assertFalse(TemplatePagina.objects.exists())
        self.enviar(nome='planilha.xls')
        self.assertFalse(TemplatePagina.objects.exists())
        from pcp.forms import TemplatePaginaForm
        antigo = TemplatePaginaForm.TAMANHO_MAXIMO
        TemplatePaginaForm.TAMANHO_MAXIMO = 100
        try:
            self.enviar()
            self.assertFalse(TemplatePagina.objects.exists())
        finally:
            TemplatePaginaForm.TAMANHO_MAXIMO = antigo

    def test_modelo_de_exemplo_para_baixar(self):
        r = self.client.get(reverse('pcp:template_pagina_amostra'))
        self.assertEqual(r.status_code, 200)
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        self.assertEqual(wb.sheetnames, ['Página', 'Modo lista', '_VARIÁVEIS'])

    def test_ativar_desativar_e_excluir(self):
        self.enviar()
        t = TemplatePagina.objects.get()
        self.client.post(reverse('pcp:template_pagina_alternar', args=[t.pk]))
        t.refresh_from_db()
        self.assertFalse(t.ativo)
        self.client.post(reverse('pcp:template_pagina_excluir', args=[t.pk]))
        self.assertFalse(TemplatePagina.objects.exists())
        self.assertEqual(self.client.get(reverse('pcp:template_pagina_excluir', args=[t.pk])).status_code, 405)

    def test_exportar_pagina_no_template(self):
        self.enviar()
        t = TemplatePagina.objects.get()
        self.dados()
        r = self.client.get(reverse('pcp:exportar_template', args=[self.pag.pk]), {'template': t.pk, 'mes': '2026-10'})
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn('FOR.080_Fitadeira_2026-10', r['Content-Disposition'])
        ws = openpyxl.load_workbook(io.BytesIO(r.content))['PCP']
        self.assertEqual(ws['A1'].value, 'FOR.080 R15 Fitadeira - outubro de 2026')
        self.assertEqual(ws['D6'].value, 'Ok')

    def test_template_que_nao_serve_e_recusado(self):
        self.enviar(pagina_nome='Outra página')                       # serve só para outra página
        t = TemplatePagina.objects.get()
        url = reverse('pcp:exportar_template', args=[self.pag.pk])
        destino = reverse('pcp:preencher_pagina', args=[self.pag.pk])
        self.assertRedirects(self.client.get(url, {'template': t.pk}), destino, fetch_redirect_response=False)
        TemplatePagina.objects.filter(pk=t.pk).update(pagina_nome='Fitadeira', ativo=False)   # inativo
        self.assertRedirects(self.client.get(url, {'template': t.pk}), destino, fetch_redirect_response=False)
        outro = Formulario.objects.create(setor=self.setor, codigo='FOR.777', titulo='Outro')
        de_outro = TemplatePagina.objects.create(formulario=outro, nome='x', arquivo_base64='x')
        self.assertRedirects(self.client.get(url, {'template': de_outro.pk}), destino, fetch_redirect_response=False)   # de outro formulário
        self.assertRedirects(self.client.get(url, {'template': 'abc'}), destino, fetch_redirect_response=False)

    def test_menu_exportar_mostra_os_templates_da_pagina(self):
        self.enviar()
        TemplatePagina.objects.create(formulario=self.form, nome='Só para outra', pagina_nome='Outra página', arquivo_base64='x')
        r = self.client.get(reverse('pcp:preencher_pagina', args=[self.pag.pk]) + f'?data=2026-10-22&turno={self.t1.pk}')
        self.assertContains(r, 'Gerar no template')
        self.assertContains(r, 'Layout mensal')
        self.assertNotContains(r, 'Só para outra')
        TemplatePagina.objects.all().delete()
        r = self.client.get(reverse('pcp:preencher_pagina', args=[self.pag.pk]) + f'?data=2026-10-22&turno={self.t1.pk}')
        self.assertContains(r, 'Cadastrar template')


class SemanaBase(PendenciasBase):
    HOJE = date(2026, 10, 22)   # quinta-feira

    def setUp(self):
        super().setUp()
        cache.clear()
        for n, c in enumerate([self.c_lista, self.c_num, self.c_sem, self.c_mes, self.c_ev, self.c_sem0], 1):
            Campo.objects.filter(pk=c.pk).update(ordem=n)
        Campo.objects.filter(pk=self.c_num.pk).update(minimo=Decimal('-0.8'), maximo=Decimal('-0.6'), tipo='numero', unidade='bar')
        self.v15.vigencia = date(2026, 10, 1)
        self.v15.save()
        self.pag = Pagina.objects.get(pk=self.pag.pk)

    def agora(self, h=10):
        return timezone.make_aware(datetime.datetime(2026, 10, 22, h, 0))

    def lancar(self, dia, turno, campo, valor, conforme=None):
        ver, _ = Verificacao.objects.get_or_create(pagina=self.pag, data=dia, turno=turno)
        Resposta.objects.create(verificacao=ver, campo=campo, valor=valor, conforme=conforme)

    def visao(self, ref=None, h=10):
        from pcp import semana as sem
        return sem.visao_semanal(self.pag, ref or self.HOJE, hoje=self.HOJE, agora=self.agora(h))

    def linha(self, v, campo):
        return next(l for l in v['linhas'] if l['campo'] == campo.pk)

    def estados_dias(self, v, campo):
        return [[p['estado'] for p in dia] for dia in self.linha(v, campo)['dias']]


class SemanaTests(SemanaBase):
    def test_estrutura_da_semana(self):
        v = self.visao()
        self.assertEqual((v['ini'], v['fim']), (date(2026, 10, 19), date(2026, 10, 25)))
        self.assertEqual([d['rotulo'] for d in v['dias']], ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom'])
        self.assertEqual([d['hoje'] for d in v['dias']], [False, False, False, True, False, False, False])
        self.assertEqual([t['sigla'] for t in v['turnos']], ['T1', 'T2'])
        self.assertEqual(self.visao(date(2026, 10, 25))['ini'], date(2026, 10, 19))      # domingo pertence à mesma semana
        self.assertEqual(self.visao(date(2026, 10, 26))['ini'], date(2026, 10, 26))

    def test_item_por_turno_um_farol_por_turno_e_dia(self):
        v = self.visao()
        self.assertEqual(self.estados_dias(v, self.c_lista), [['nok', 'nok']] * 3 + [['aberto', 'aberto']] + [['futuro', 'futuro']] * 3)
        self.lancar(date(2026, 10, 19), self.t1, self.c_lista, 'Ok', True)
        self.assertEqual(self.estados_dias(self.visao(), self.c_lista)[0], ['ok', 'nok'])    # T1 ok, T2 sem lançamento

    def test_item_diario_qualquer_turno_vale_e_fora_do_limite_e_nok(self):
        self.lancar(date(2026, 10, 19), self.t2, self.c_num, '-0,7', True)       # segunda: em T2 já vale o dia
        self.lancar(date(2026, 10, 20), self.t1, self.c_num, '-0,2', False)      # terça: lançado fora do limite
        e = [d[0] for d in self.estados_dias(self.visao(), self.c_num)]
        self.assertEqual(e, ['ok', 'nok', 'nok', 'aberto', 'futuro', 'futuro', 'futuro'])
        detalhe = self.visao()['detalhes'][f'{self.c_num.pk}:20261020:0']
        self.assertEqual(detalhe['estado'], 'nok')
        self.assertIn('fora do especificado', detalhe['resumo'])

    def test_item_semanal_um_farol_para_a_semana_e_qualquer_dia_vale(self):
        j = self.linha(self.visao(), self.c_sem)
        self.assertEqual((j['tipo'], [p['estado'] for p in j['janelas']], [p['rotulo'] for p in j['janelas']]), ('janelas', ['aberto'], ['19/10–25/10']))
        self.lancar(date(2026, 10, 21), self.t2, self.c_sem, 'x', True)          # quarta, T2
        self.assertEqual([p['estado'] for p in self.linha(self.visao(), self.c_sem)['janelas']], ['ok'])
        self.assertEqual([p['estado'] for p in self.linha(self.visao(), self.c_mes)['janelas']], ['aberto'])

    def test_quinzena_que_cruza_a_semana_gera_dois_farois(self):
        f = Frequencia.objects.create(nome='Quinzenal', periodicidade='quinzenal')
        c = Campo.objects.create(pagina=self.pag, item='Q-1', descricao='quinzenal', tipo='texto', frequencia=f, ordem=7)
        v = self.visao(date(2026, 10, 14))                                         # semana 12-18/10 toca as quinzenas 1-15 e 16-31
        j = self.linha(v, c)['janelas']
        self.assertEqual([(p['rotulo'], p['estado']) for p in j], [('01/10–15/10', 'nok'), ('16/10–31/10', 'aberto')])   # a 1ª já encerrou sem registro

    def test_item_sob_demanda_so_mostra_lancamentos(self):
        self.lancar(date(2026, 10, 20), self.t1, self.c_ev, 'troca')
        self.lancar(date(2026, 10, 21), self.t2, self.c_sem0, 'algo')
        v = self.visao()
        self.assertEqual(self.estados_dias(v, self.c_ev), [[], ['info'], [], [], [], [], []])
        self.assertEqual(self.estados_dias(v, self.c_sem0), [[], [], ['info'], [], [], [], []])
        self.assertEqual(sum(v['contagem'].values()), sum(v['contagem'][k] for k in ('ok', 'nok', 'aberto', 'futuro', 'dispensado', 'sem')))   # 'info' não conta

    def test_maquina_parada_dispensa_e_explica_no_detalhe(self):
        self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), {'data': '2026-10-20', 'turno': self.t1.pk, 'status': 'parada', 'escopo': 'turno', 'motivo': 'troca de ferramenta'})
        v = self.visao()
        self.assertEqual(self.estados_dias(v, self.c_lista)[1], ['dispensado', 'nok'])      # só T1 de terça está parado
        self.assertEqual(self.estados_dias(v, self.c_num)[1], ['nok'])                      # o dia não está todo parado
        d = v['detalhes'][f'{self.c_lista.pk}:20261020:{self.t1.pk}']
        self.assertIn('Parada (troca de ferramenta)', d['maquina'])
        self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), {'data': '2026-10-20', 'turno': self.t2.pk, 'status': 'manutencao', 'escopo': 'turno'})
        self.assertEqual(self.estados_dias(self.visao(), self.c_num)[1], ['dispensado'])    # todos os turnos do dia parados

    def test_antes_do_rastreio_fica_sem_exigencia(self):
        self.v15.vigencia = date(2026, 10, 21)
        self.v15.save()
        e = self.estados_dias(self.visao(), self.c_lista)
        self.assertEqual((e[0], e[1], e[2]), (['sem', 'sem'], ['sem', 'sem'], ['nok', 'nok']))

    def test_turno_encerrado_hoje_sem_registro_fica_nok(self):
        for t, ini, fim in ((self.t1, time(6), time(14)), (self.t2, time(14), time(22))):
            t.inicio, t.fim = ini, fim
            t.save()
        self.assertEqual(self.estados_dias(self.visao(h=15), self.c_lista)[3], ['nok', 'aberto'])    # T1 encerrou, T2 em andamento
        self.assertEqual(self.estados_dias(self.visao(h=8), self.c_lista)[3], ['aberto', 'futuro'])  # T2 ainda não começou

    def test_detalhe_traz_os_dados_que_compoem_o_farol_e_e_serializavel(self):
        import json
        self.lancar(date(2026, 10, 19), self.t1, self.c_lista, 'Ok', True)
        v = self.visao()
        d = v['detalhes'][f'{self.c_lista.pk}:20261019:{self.t1.pk}']
        self.assertEqual((d['estado'], d['estado_rotulo'], d['prazo']), ('ok', 'OK', 'Dia 19/10/2026, turno T1'))
        self.assertEqual([(r['data'], r['turno'], r['valor'], r['conforme']) for r in d['registros']], [('19/10/2026', 'T1', 'Ok', True)])
        item = v['itens'][self.c_lista.pk]
        self.assertEqual((item['num'], item['item'], item['frequencia']), (1, 'B-1', 'Turno'))
        json.dumps({'itens': v['itens'], 'detalhes': v['detalhes']})        # vai para o navegador como JSON

    def test_tela_pagina_semana_e_navegacao(self):
        url = reverse('pcp:semana')
        r = self.client.get(url, {'pagina': self.pag.pk, 'semana': '2026-10-21'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.context['d']['ini'], r.context['anterior'], r.context['proxima']), (date(2026, 10, 19), date(2026, 10, 12), date(2026, 10, 26)))
        self.assertContains(r, 'modal-farol')
        self.assertContains(r, 'farol-btn')
        self.assertContains(r, f'?pagina={self.pag.pk}&semana=2026-10-12')
        self.assertEqual([f[1] for f in r.context['frequencias']][:3], ['Turno', 'Diária', 'Semanal'])
        r = self.client.get(url)                                              # sem parâmetros: primeira página, semana atual
        self.assertEqual(r.context['pagina'].pk, self.pag.pk)
        self.assertEqual(self.client.get(url, {'pagina': 'lixo', 'semana': 'lixo'}).status_code, 200)
        self.pag.versao.paginas.update(ativo=False)
        self.assertContains(self.client.get(url), 'Nenhuma página ativa')

    def test_filtro_de_frequencia_na_tela_de_preenchimento(self):
        r = self.client.get(reverse('pcp:preencher_pagina', args=[self.pag.pk]) + f'?data=2026-10-22&turno={self.t1.pk}')
        nomes = [(nome, qtd) for _, nome, qtd in r.context['frequencias_pagina']]
        self.assertEqual(nomes, [('Turno', 1), ('Diária', 1), ('Semanal', 1), ('Mensal', 1), ('Por evento', 1), ('Sem frequência', 1)])
        self.assertContains(r, 'id="filtro_frequencia"')
        self.assertContains(r, f'data-freq="{self.f_turno.pk}"')
        self.assertContains(r, 'data-freq="0"')                               # item sem frequência
        self.assertContains(r, 'Todas (6)')


class SemanaLancarDoPopupTests(SemanaBase):
    """Botão "Lançar/Corrigir" do pop-up: leva à tela de preenchimento na data e no turno do farol, com o item em destaque."""

    def destino(self, v, chave):
        return v['detalhes'][chave]['lancar']

    def base(self):
        return reverse('pcp:preencher_pagina', args=[self.pag.pk])

    def test_item_por_turno_vai_para_o_dia_e_turno_do_farol(self):
        v = self.visao()
        d = self.destino(v, f'{self.c_lista.pk}:20261020:{self.t2.pk}')
        self.assertEqual(d['url'], f'{self.base()}?data=2026-10-20&turno={self.t2.pk}#campo-{self.c_lista.pk}')
        self.assertEqual((d['data'], d['turno']), ('20/10/2026', 'T2'))

    def test_item_diario_vai_para_o_primeiro_turno_do_dia_sem_lancamento(self):
        self.lancar(date(2026, 10, 20), self.t1, self.c_num, '-0,7', True)
        d = self.destino(self.visao(), f'{self.c_num.pk}:20261020:0')
        self.assertEqual(d['turno'], 'T2')                                      # T1 já tem lançamento do item no dia
        self.assertTrue(d['url'].startswith(f'{self.base()}?data=2026-10-20&turno={self.t2.pk}'))
        self.assertEqual(self.destino(self.visao(), f'{self.c_num.pk}:20261021:0')['turno'], 'T1')   # dia sem lançamento: primeiro turno

    def test_prazo_periodico_vai_para_hoje_se_em_curso_ou_para_o_ultimo_dia_se_encerrado(self):
        v = self.visao()
        self.assertTrue(self.destino(v, f'{self.c_sem.pk}:j:20261019')['url'].startswith(f'{self.base()}?data=2026-10-22'))   # semana em curso: hoje
        f = Frequencia.objects.create(nome='Quinzenal', periodicidade='quinzenal')
        c = Campo.objects.create(pagina=self.pag, item='Q-1', descricao='q', tipo='texto', frequencia=f, ordem=7)
        v = self.visao(date(2026, 10, 14))
        self.assertTrue(self.destino(v, f'{c.pk}:j:20261001')['url'].startswith(f'{self.base()}?data=2026-10-15'))             # quinzena encerrada: último dia

    def test_farol_futuro_nao_tem_botao_mas_os_demais_tem(self):
        v = self.visao()
        self.assertIsNone(v['detalhes'][f'{self.c_lista.pk}:20261023:{self.t1.pk}']['lancar'])       # sexta: ainda não começou
        self.assertIsNotNone(v['detalhes'][f'{self.c_lista.pk}:20261022:{self.t1.pk}']['lancar'])    # hoje: em aberto
        self.assertIsNotNone(v['detalhes'][f'{self.c_lista.pk}:20261019:{self.t1.pk}']['lancar'])    # passado sem lançamento: lançar fora do prazo
        self.lancar(date(2026, 10, 19), self.t1, self.c_lista, 'Ok', True)
        d = self.visao()['detalhes'][f'{self.c_lista.pk}:20261019:{self.t1.pk}']
        self.assertTrue(d['lancar'] and d['registros'])                                              # já lançado: o botão vira "Corrigir"

    def test_item_sob_demanda_tambem_leva_ao_lancamento(self):
        self.lancar(date(2026, 10, 20), self.t1, self.c_ev, 'troca')
        d = self.destino(self.visao(), f'{self.c_ev.pk}:20261020:{self.t1.pk}')
        self.assertIn(f'#campo-{self.c_ev.pk}', d['url'])

    def test_tela_tem_o_botao_e_a_preenchimento_tem_ancora_e_destaque(self):
        r = self.client.get(reverse('pcp:semana'), {'pagina': self.pag.pk, 'semana': '2026-10-21'})
        self.assertContains(r, 'id="modal-farol-lancar"')
        self.assertContains(r, 'Corrigir lançamento')                                                # texto alternado no JS conforme haja registros
        r = self.client.get(f'{self.base()}?data=2026-10-20&turno={self.t1.pk}')
        self.assertContains(r, f'id="campo-{self.c_lista.pk}"')
        self.assertContains(r, 'pcp-destaque')                                                       # script de destaque via #campo-ID
        self.assertEqual(self.client.get(f'{self.base()}?data=2026-10-20&turno={self.t1.pk}#campo-{self.c_lista.pk}').status_code, 200)

    def test_json_do_popup_continua_serializavel_com_o_destino(self):
        import json
        v = self.visao()
        json.dumps({'itens': v['itens'], 'detalhes': v['detalhes']})


class SemanaGruposETests(SemanaBase):
    """Separadores por frequência com sub-total e botão "+" nos itens sob demanda."""

    def get(self):
        return self.client.get(reverse('pcp:semana'), {'pagina': self.pag.pk, 'semana': '2026-10-21'})

    def test_grupos_por_frequencia_com_subtotal(self):
        self.lancar(date(2026, 10, 19), self.t1, self.c_lista, 'Ok', True)
        r = self.get()
        nomes = [g['nome'] for g in r.context['grupos']]
        self.assertEqual(nomes[:3], ['Turno', 'Diária', 'Semanal'])
        g = r.context['grupos'][0]
        self.assertEqual(g['ok'], 1)
        self.assertEqual(sum(len(g['linhas']) for g in r.context['grupos']), len(r.context['d']['linhas']))
        self.assertContains(r, 'class="grupo-freq"')

    def test_botao_mais_nos_itens_sob_demanda(self):
        self.lancar(date(2026, 10, 20), self.t1, self.c_ev, 'troca')
        r = self.get()
        linha = next(l for l in r.context['d']['linhas'] if l['campo'] == self.c_ev.pk)
        self.assertEqual([n['rotulo'] for n in linha['novos'][1]], ['T2'])           # terça: T1 já tem registro
        self.assertEqual(linha['novos'][1:2][0][0]['data'], '20/10/2026')
        self.assertTrue(all(n['url'].endswith(f'#campo-{self.c_ev.pk}') for n in linha['novos'][0]))
        self.assertContains(r, "farol-novo")
        self.assertContains(r, f'#campo-{self.c_ev.pk}')


class SemanaLancarNoPopupTests(SemanaBase):
    """Lançamento direto do pop-up (endpoint JSON por item) respeitando o tipo do campo."""

    def post(self, campo, valor, dia='2026-10-20', turno=None):
        return self.client.post(reverse('pcp:preencher_item', args=[self.pag.pk]),
                                {'campo': campo.pk, 'data': dia, 'turno': (turno or self.t1).pk, 'valor': valor})

    def test_lanca_numero_avalia_conformidade_e_corrige(self):
        r = self.post(self.c_num, '-0,2')
        self.assertEqual((r.status_code, r.json()['conforme']), (200, False))
        self.assertEqual(Resposta.objects.get(campo=self.c_num).valor, '-0,2')
        self.assertTrue(self.post(self.c_num, '-0,7').json()['conforme'])
        self.assertEqual(Resposta.objects.filter(campo=self.c_num).count(), 1)

    def test_valida_tipo_e_data(self):
        self.assertEqual(self.post(self.c_num, 'abc').status_code, 400)
        self.assertEqual(self.post(self.c_lista, 'valor fora da lista').status_code, 400)
        self.assertEqual(self.post(self.c_num, '1', dia='2999-01-01').status_code, 400)
        self.assertEqual(self.post(self.c_num, '1', dia='lixo').status_code, 400)

    def test_lista_aceita_opcao_e_valor_vazio_limpa(self):
        opcao = self.c_lista.lista.opcoes.first().valor
        self.assertEqual(self.post(self.c_lista, opcao).status_code, 200)
        self.assertEqual(Resposta.objects.filter(campo=self.c_lista).count(), 1)
        self.assertTrue(self.post(self.c_lista, '').json()['limpo'])
        self.assertEqual(Resposta.objects.filter(campo=self.c_lista).count(), 0)

    def test_dados_do_popup_trazem_tipo_opcoes_e_destino(self):
        v = self.visao()
        item = v['itens'][self.c_lista.pk]
        self.assertEqual(item['tipo_codigo'], 'lista')
        self.assertTrue(item['opcoes'])
        d = v['detalhes'][f'{self.c_lista.pk}:20261020:{self.t2.pk}']['lancar']
        self.assertEqual((d['iso'], d['turno_id']), ('2026-10-20', self.t2.pk))


class SemanaMobileTests(SemanaBase):
    def test_cards_por_grupo_recolhiveis_legenda_em_popup_e_nav_em_dropdown(self):
        r = self.client.get(reverse('pcp:semana'), {'pagina': self.pag.pk, 'semana': '2026-10-21'})
        self.assertContains(r, 'grupo-card')
        self.assertContains(r, 'data-bs-toggle="collapse"')
        self.assertContains(r, 'id="modal-legenda"')
        self.assertContains(r, 'dropdown-toggle w-100')                    # abas do PCP em drop-down
        self.assertEqual(r.content.decode().count('class="card mb-3 grupo-card"'), len(r.context['grupos']))
        self.assertEqual(r.content.decode().count('class="card item-card mb-2"'), len(r.context['d']['linhas']))


class DashboardMobileTests(DashboardBase):
    def test_celular_sem_graficos_nem_texto_explicativo_e_cards_de_pagina(self):
        r = self.client.get(reverse('pcp:dashboard'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('row g-3 mb-3 d-none d-md-flex', html) if r.context['d']['devidos'] else None
        self.assertIn('small text-muted d-none d-md-block', html)          # texto "Cada ponto é o prazo…" escondido no celular
        self.assertIn('d-md-none p-2', html)                               # cards: grupo > página


class SemanaOcorrenciaNoPopupTests(SemanaBase):
    def post(self, **extra):
        dados = {'campo': self.c_ev.pk, 'data': '2026-10-20', 'turno': self.t1.pk, 'tipo': 'tratativa', 'descricao': 'Pinça trocada'}
        dados.update(extra)
        return self.client.post(reverse('pcp:ocorrencia_registrar', args=[self.pag.pk]), dados)

    def test_registra_ocorrencia_do_item_na_data_e_turno(self):
        r = self.post()
        self.assertEqual((r.status_code, r.json()['ok']), (200, True))
        oc = Ocorrencia.objects.get()
        self.assertEqual((oc.campo, oc.tipo, oc.descricao, oc.verificacao.data, oc.verificacao.turno), (self.c_ev, 'tratativa', 'Pinça trocada', date(2026, 10, 20), self.t1))
        self.assertEqual(oc.criado_por, self.user) if hasattr(self, 'user') else None

    def test_valida_descricao_data_e_tipo_desconhecido_vira_observacao(self):
        self.assertEqual(self.post(descricao='  ').status_code, 400)
        self.assertEqual(self.post(data='2999-01-01').status_code, 400)
        self.assertEqual(self.post(data='lixo').status_code, 400)
        self.assertEqual(self.post(tipo='xyz').status_code, 200)
        self.assertEqual(Ocorrencia.objects.get().tipo, 'observacao')

    def test_botao_mais_tem_chave_de_detalhe_e_tela_tem_botao_de_ocorrencia(self):
        r = self.client.get(reverse('pcp:semana'), {'pagina': self.pag.pk, 'semana': '2026-10-19'})
        linha = next(l for l in r.context['d']['linhas'] if l['campo'] == self.c_ev.pk)
        n = linha['novos'][1][0]
        self.assertEqual(r.context['d']['detalhes'][n['key']]['estado'], 'novo')
        self.assertContains(r, 'id="modal-farol-ocorrencia"')
        self.assertContains(r, f'data-key="{n["key"]}"')


def _template_calendario(blocos=5, largura=2):
    """Template em calendário (como o FOR.080): DATA mesclada sobre as colunas dos turnos, TURNO e VALOR só na 1ª coluna do bloco."""
    from openpyxl.styles import Border, PatternFill, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.hyperlink import Hyperlink
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'TEMPLATE'
    ws['A2'] = 'Voltar ao índice'
    ws['A2'].hyperlink = Hyperlink(ref='A2', location="'Índice'!A1")
    ws['D2'] = '{{PAGINA}}'
    for j, t in enumerate(['Item', 'O que verificar'], 1):
        ws.cell(row=4, column=j, value=t)
    ws['A6'], ws['B6'] = '{{ITEM}}', '{{DESCRICAO}}'
    azul = PatternFill('solid', fgColor='DDEBF7')
    lado = Side(style='thin')
    for b in range(blocos):
        c0 = 3 + b * largura
        ws.merge_cells(start_row=4, start_column=c0, end_row=4, end_column=c0 + largura - 1)
        for j in range(largura):
            ws.cell(row=4, column=c0 + j).fill = azul
            ws.cell(row=5, column=c0 + j).fill = azul
            ws.cell(row=6, column=c0 + j).border = Border(left=lado, right=lado)
            ws.cell(row=7, column=c0 + j).border = Border(left=lado, right=lado)
            ws.column_dimensions[get_column_letter(c0 + j)].width = 7
        ws.cell(row=4, column=c0).number_format = 'dd/mm/yyyy'
    ws['C4'], ws['C5'], ws['C6'] = '{{DATA}}', '{{TURNO}}', '{{VALOR}}'
    ws['A8'] = 'Rodapé fixo'
    ws.freeze_panes = 'C1'
    ws.add_data_validation(DataValidation(type='list', formula1='"Ok,Nok"', sqref='C6:XFD7'))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TemplateCalendarioTests(TemplatesBase):
    def setUp(self):
        super().setUp()
        self.p2 = Pagina.objects.create(versao=self.v15, nome='Outra', grupo='Fita')
        Campo.objects.create(pagina=self.p2, item='Z-1', descricao='zz', tipo='texto', ordem=1, frequencia=self.f_turno)

    def gerar_cal(self, ini=date(2026, 10, 1), fim=date(2026, 10, 3), paginas=None, conteudo=None):
        from pcp import templates_xlsx
        paginas = [self.p, self.p2] if paginas is None else paginas
        s = templates_xlsx.gerar_calendario(conteudo or _template_calendario(), self.form, self.v15, paginas, ini, fim, hoje=date(2026, 10, 5))
        return openpyxl.load_workbook(io.BytesIO(s.getvalue()))

    def test_reconhece_o_modo_calendario_sozinho(self):
        from pcp import templates_xlsx
        self.assertEqual(templates_xlsx.analisar(_template_calendario())['modo'], 'calendario')
        self.assertTrue(templates_xlsx.eh_calendario(_template_calendario()))
        self.assertFalse(templates_xlsx.eh_calendario(_template_lista()))      # DATA e VALOR na mesma linha continua sendo modo lista
        self.assertFalse(templates_xlsx.eh_calendario(_template_grade()))

    def test_uma_aba_por_pagina_mais_indice_com_o_layout_do_template(self):
        wb = self.gerar_cal()
        self.assertEqual(wb.sheetnames, ['Índice', 'Fitadeira', 'Outra'])
        ws = wb['Fitadeira']
        self.assertEqual(ws['D2'].value, 'Fitadeira')
        self.assertEqual(ws['A2'].hyperlink.location, "'Índice'!A1")                  # "Voltar ao índice"
        self.assertEqual(wb['Índice']['B5'].hyperlink.location, "'Fitadeira'!A1")
        self.assertEqual(ws.freeze_panes, 'C1')
        self.assertEqual([ws.cell(4, c).value.date() for c in (3, 5, 7)], [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)])
        self.assertEqual(ws.cell(4, 3).number_format, 'dd/mm/yyyy')                     # formato da data do template preservado
        self.assertEqual([ws.cell(5, c).value for c in range(3, 9)], ['T1', 'T2'] * 3)
        self.assertEqual(len([m for m in ws.merged_cells.ranges if m.min_row == 4]), 3)  # um bloco mesclado por data; sem blocos após o período
        self.assertEqual(ws.max_column, 8)
        self.assertEqual(ws.cell(5, 3).fill.fgColor.rgb, '00DDEBF7')                     # estilo copiado para todos os blocos
        self.assertEqual(ws.cell(6, 8).border.right.style, 'thin')
        self.assertEqual(ws.column_dimensions['H'].width, 7)
        self.assertIn('H', str(ws.data_validations.dataValidation[0].sqref))

    def test_itens_nas_linhas_valores_por_data_e_turno_e_rodape_deslocado(self):
        self.lancar(date(2026, 10, 1), self.t1, self.c_lista, 'Ok')
        self.lancar(date(2026, 10, 2), self.t2, self.c_num, '-0,7')
        ws = self.gerar_cal(paginas=[self.p])['Fitadeira']
        campos = list(self.p.campos.filter(ativo=True).order_by('ordem', 'pk'))
        n = len(campos)
        self.assertEqual([ws.cell(6 + k, 1).value for k in range(n)], [c.item for c in campos])
        self.assertEqual(ws.cell(6, 3).value, 'Ok')                                       # item 1, dia 1, T1
        self.assertEqual(ws.cell(7, 6).value, -0.7)                                       # item 2, dia 2, T2 (número)
        self.assertEqual(ws.cell(7 + n, 1).value, 'Rodapé fixo')                      # rodapé desloca para depois dos itens

    def test_destaque_fora_do_especificado_e_situacao_da_maquina(self):
        ver = Verificacao.objects.create(pagina=self.pag, data=date(2026, 10, 1), turno=self.t1)
        Resposta.objects.create(verificacao=ver, campo=self.c_lista, valor='Nok', conforme=False)
        self.client.post(reverse('pcp:preencher_status', args=[self.pag.pk]), {'data': '2026-10-02', 'turno': self.t2.pk, 'status': 'parada', 'escopo': 'turno'})
        ws = self.gerar_cal(paginas=[self.p])['Fitadeira']
        self.assertEqual((ws.cell(6, 3).value, ws.cell(6, 3).font.b, ws.cell(6, 3).font.color.rgb), ('Nok', True, '00C00000'))
        self.assertEqual((ws.cell(6, 6).value, ws.cell(6, 6).fill.fgColor.rgb), ('Parada', '00D9D9D9'))

    def test_periodo_grande_demais_e_validacoes(self):
        from pcp import templates_xlsx
        with self.assertRaises(ValueError):
            self.gerar_cal(ini=date(2000, 1, 1), fim=date(2100, 1, 1))
        with self.assertRaises(ValueError):
            self.gerar_cal(ini=date(2026, 10, 3), fim=date(2026, 10, 1))
        with self.assertRaises(ValueError):
            self.gerar_cal(paginas=[])
        with self.assertRaises(ValueError):
            templates_xlsx.gerar_calendario(_template_grade(), self.form, self.v15, [self.p], date(2026, 10, 1), date(2026, 10, 2))

    def test_tela_gera_todas_as_paginas_ou_so_o_grupo_ou_a_pagina(self):
        from pcp import templates_xlsx
        tpl = TemplatePagina.objects.create(formulario=self.form, nome='Calendário', arquivo_base64=templates_xlsx.codificar(_template_calendario()),
                                            analise=templates_xlsx.analisar(_template_calendario()))
        url = reverse('pcp:exportar_template', args=[self.p.pk])

        def abas(**extra):
            r = self.client.get(url, {'template': tpl.pk, 'de': '2026-10-01', 'ate': '2026-10-02', **extra})
            self.assertEqual(r.status_code, 200)
            return openpyxl.load_workbook(io.BytesIO(r.content)).sheetnames
        self.assertEqual(abas(), ['Índice', 'Fitadeira', 'Outra'])                         # padrão: todas as páginas
        self.assertEqual(abas(escopo='pagina'), ['Índice', 'Fitadeira'])
        self.assertEqual(abas(escopo='grupo'), ['Índice', 'Fitadeira', 'Outra'])
        self.p2.grupo = 'Outro grupo'
        self.p2.save()
        self.assertEqual(abas(escopo='grupo'), ['Índice', 'Fitadeira'])
        r = self.client.get(reverse('pcp:preencher_pagina', args=[self.p.pk]) + f'?data=2026-10-01&turno={self.t1.pk}')
        self.assertContains(r, 'data-modo="calendario"')
        self.assertContains(r, 'Todas as páginas do formulário')


class PendenciasRecolhiveisTests(PendenciasBase):
    def test_itens_pendentes_agrupados_por_frequencia_e_camadas_recolhiveis(self):
        p = pend.painel(date(2026, 10, 22), self.turnos)
        linhas = [l for b in p['blocos'] for ls in b['grupos'].values() for l in ls if l['itens']]
        self.assertTrue(linhas)
        for l in linhas:
            nomes = [f['nome'] for f in l['por_frequencia']]
            self.assertEqual(sum(len(f['itens']) for f in l['por_frequencia']), len(l['itens']))
            self.assertEqual(len(nomes), len(set(nomes)))
        r = self.client.get(reverse('pcp:pendencias') + '?data=2026-10-22')
        self.assertContains(r, 'data-bs-target="#g-1-1"')                       # grupo recolhível
        self.assertContains(r, 'pcp-toggle-pagina')                              # página recolhível
        self.assertContains(r, 'pcp-toggle-freq')                                # frequência recolhível
        self.assertContains(r, 'data-pcp-todos')                                 # expandir/recolher tudo

    def test_semana_tem_cabecalho_congelado(self):
        pag = self.pag
        r = self.client.get(reverse('pcp:semana'), {'pagina': pag.pk})
        self.assertContains(r, 'semana-scroll')
        self.assertContains(r, 'position: sticky')
