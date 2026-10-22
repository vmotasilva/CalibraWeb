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
