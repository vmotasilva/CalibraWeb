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
from pcp.models import (AjusteCampo, AjusteVinculo, ValorEquivalente, Campo, Formulario, FormularioVersao, Frequencia, ListaOpcoes, OpcaoLista, Ocorrencia,
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
        self.assertContains(r, '1/4')  # T1: 1 feita de 4 devidas
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
        self.assertEqual((fita2.ativo, fita2.ordem), (False, 7))
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
        self.assertContains(self.client.get(reverse('pcp:pendencias') + '?data=2026-10-22'), 'Manut.')
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
        linhas = [r_ for r_ in range(6, ws.max_row + 1) if ws.cell(row=r_, column=1).value]
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


class DashboardTests(PendenciasBase):
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
        self.assertContains(r, 'Fitadeira')
        self.assertContains(r, reverse('pcp:atrasos_pagina', args=[self.pag.pk]))
        self.assertContains(r, 'Turno')       # colunas por frequência
        self.assertContains(r, 'Em atraso')
