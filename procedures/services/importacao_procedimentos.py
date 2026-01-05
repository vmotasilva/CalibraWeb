# -*- coding: utf-8 -*-
"""
Serviço para importação em massa de procedimentos a partir de arquivo Excel/CSV

Características:
- Validação de dados antes de persistir
- Tratamento robusto de erros
- Relatório detalhado de operação
- Suporte para criação e atualização
- Transação segura com rollback
"""

import pandas as pd
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ValidationError

from procedures.models import Procedimento

logger = logging.getLogger(__name__)


class ImportacaoProcedimentosService:
    """Serviço de importação de procedimentos com validação e tratamento de erros."""
    
    # Colunas esperadas - podem ser mapeadas de diferentes nomes
    COLUNAS_OBRIGATORIAS = ['codigo', 'nome']
    
    # Mapeamento flexível de nomes de colunas (entrada -> campo modelo)
    MAPEAMENTO_COLUNAS = {
        'codigo': ['codigo', 'Código', 'Code', 'CODIGO'],
        'nome': ['nome', 'Nome', 'Title', 'Título', 'NOME'],
        'descricao': ['descricao', 'Descrição', 'Description', 'DESCRICAO'],
        'pasta': ['pasta', 'Pasta', 'Folder', 'PASTA'],
        'classificacao': ['classificacao', 'Classificação', 'Classification', 'CLASSIFICACAO'],
        'autor': ['autor', 'Autor', 'Author', 'AUTOR'],
        'numero_revisao': ['numero_revisao', 'número_revisão', 'Número Revisão', 'NUMERO_REVISAO', 'revisao'],
        'ultima_revisao': ['ultima_revisao', 'última_revisão', 'Última Revisão', 'ULTIMA_REVISAO', 'Data Revisão'],
        'data_aprovacao': ['data_aprovacao', 'Data Aprovação', 'Data de Aprovação', 'DATA_APROVACAO'],
        'proxima_revisao': ['proxima_revisao', 'Próxima Revisão', 'Próxima Revisão', 'PROXIMA_REVISAO'],
        'data_validade': ['data_validade', 'Data Validade', 'Data de Validade', 'DATA_VALIDADE'],
        'documentos_controlados': ['documentos_controlados', 'Documentos Controlados', 'DOCUMENTOS_CONTROLADOS'],
        'matriz': ['matriz', 'Matriz', 'Matrix', 'MATRIZ'],
        'sub_area': ['sub_area', 'Sub-Área', 'Sub Área', 'SUB_AREA'],
        'criticidade': ['criticidade', 'Criticidade', 'CRITICIDADE', 'Nível de Criticidade', 'CRITICO', 'NAO_CRITICO'],
    }
    
    def __init__(self, arquivo):
        """Inicializa o serviço com um arquivo."""
        self.arquivo = arquivo
        self.df = None
        self.resultados = {
            'total': 0,
            'criados': 0,
            'atualizados': 0,
            'erros': 0,
            'linhas_processadas': [],
            'erros_detalhados': [],
        }
    
    def carregar_arquivo(self) -> bool:
        """Carrega arquivo Excel/CSV."""
        try:
            # Detecta tipo de arquivo
            if self.arquivo.name.endswith('.csv'):
                self.df = pd.read_csv(self.arquivo, encoding='utf-8')
            elif self.arquivo.name.endswith(('.xlsx', '.xls')):
                self.df = pd.read_excel(self.arquivo)
            else:
                self.resultados['erros_detalhados'].append({
                    'linha': 0,
                    'erro': 'Formato de arquivo não suportado. Use .xlsx, .xls ou .csv'
                })
                return False
            
            self.df = self.df.fillna('')  # Substitui NaN por string vazia
            self.resultados['total'] = len(self.df)
            logger.info(f"Arquivo carregado: {self.arquivo.name} com {len(self.df)} linhas")
            return True
            
        except Exception as e:
            self.resultados['erros_detalhados'].append({
                'linha': 0,
                'erro': f'Erro ao carregar arquivo: {str(e)}'
            })
            logger.error(f"Erro ao carregar arquivo: {e}")
            return False
    
    def normalizar_colunas(self) -> bool:
        """Normaliza nomes de colunas do arquivo para nomes padrão do modelo."""
        if self.df is None or self.df.empty:
            self.resultados['erros_detalhados'].append({
                'linha': 0,
                'erro': 'Arquivo vazio ou não carregado'
            })
            return False
        
        try:
            # Cria mapeamento reverso: nome_coluna_arquivo -> campo_modelo
            mapa = {}
            for campo, nomes_possiveis in self.MAPEAMENTO_COLUNAS.items():
                for col in self.df.columns:
                    if col in nomes_possiveis or col.lower() in [n.lower() for n in nomes_possiveis]:
                        mapa[col] = campo
                        break
            
            # Renomeia colunas
            self.df = self.df.rename(columns=mapa)
            
            # Valida colunas obrigatórias
            colunas_faltando = [col for col in self.COLUNAS_OBRIGATORIAS if col not in self.df.columns]
            if colunas_faltando:
                self.resultados['erros_detalhados'].append({
                    'linha': 0,
                    'erro': f'Colunas obrigatórias faltando: {", ".join(colunas_faltando)}'
                })
                return False
            
            logger.info(f"Colunas normalizadas. Encontradas: {list(self.df.columns)}")
            return True
            
        except Exception as e:
            self.resultados['erros_detalhados'].append({
                'linha': 0,
                'erro': f'Erro ao normalizar colunas: {str(e)}'
            })
            logger.error(f"Erro ao normalizar colunas: {e}")
            return False
    
    def _parsear_data(self, valor: str) -> datetime.date or None:
        """Parseia data em múltiplos formatos."""
        if not valor or valor == '':
            return None
        
        formatos = [
            '%d/%m/%Y', '%d/%m/%y',  # DD/MM/YYYY
            '%Y-%m-%d',               # YYYY-MM-DD
            '%d-%m-%Y',               # DD-MM-YYYY
            '%Y/%m/%d',               # YYYY/MM/DD
        ]
        
        valor_limpo = str(valor).strip()
        
        for fmt in formatos:
            try:
                return datetime.strptime(valor_limpo, fmt).date()
            except ValueError:
                continue
        
        # Retorna None se não conseguir parsear
        logger.warning(f"Não foi possível parsear data: {valor_limpo}")
        return None
    
    def _validar_linha(self, num_linha: int, dados: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Valida dados de uma linha."""
        erros = []
        
        # Converte todos os valores para string
        dados_str = {k: str(v).strip() if v else '' for k, v in dados.items()}
        
        # Valida código (obrigatório e único)
        codigo = dados_str.get('codigo', '').strip()
        if not codigo:
            erros.append("Código é obrigatório")
        elif not (3 <= len(codigo) <= 50):
            erros.append(f"Código deve ter entre 3 e 50 caracteres (atual: {len(codigo)})")
        
        # Valida nome (obrigatório)
        nome = dados_str.get('nome', '').strip()
        if not nome:
            erros.append("Nome é obrigatório")
        elif len(nome) > 200:
            erros.append(f"Nome não pode exceder 200 caracteres (atual: {len(nome)})")
        
        # Valida datas
        datas = ['ultima_revisao', 'data_aprovacao', 'proxima_revisao', 'data_validade']
        for campo_data in datas:
            valor = dados_str.get(campo_data, '')
            if valor and valor != '':
                data = self._parsear_data(valor)
                if data is None and valor:
                    erros.append(f"{campo_data.replace('_', ' ').title()}: formato de data inválido ({valor})")
        
        return len(erros) == 0, erros
    
    def _preparar_dados_linha(self, dados: Dict[str, str]) -> Dict[str, Any]:
        """Prepara dados de uma linha para salvar no modelo."""
        dados_preparados = {}
        
        # Converte todos os valores para string primeiro
        dados_str = {k: str(v).strip() if v else '' for k, v in dados.items()}
        
        # Campos de texto
        campos_texto = ['codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor', 'numero_revisao', 'documentos_controlados', 'matriz', 'sub_area', 'criticidade']
        for campo in campos_texto:
            valor = dados_str.get(campo, '').strip() if campo in dados_str else ''
            if valor:
                dados_preparados[campo] = valor
        
        # Campos de data
        campos_data = ['ultima_revisao', 'data_aprovacao', 'proxima_revisao', 'data_validade']
        for campo in campos_data:
            valor = dados_str.get(campo, '')
            if valor and valor != '':
                data = self._parsear_data(valor)
                if data:
                    dados_preparados[campo] = data
        
        return dados_preparados
    
    @transaction.atomic
    def processar(self, modo: str = 'upsert') -> Dict[str, Any]:
        """
        Processa o arquivo e importa procedimentos.
        
        Modos:
        - 'upsert': Cria novos e atualiza existentes (padrão)
        - 'create': Apenas cria novos, pula existentes
        - 'skip_duplicates': Pula linhas com código duplicado
        - 'dry_run': Simula importação sem salvar
        """
        
        # Carrega e normaliza arquivo
        if not self.carregar_arquivo():
            return self.resultados
        
        if not self.normalizar_colunas():
            return self.resultados
        
        codigos_processados = set()
        
        # Processa cada linha
        for idx, row in self.df.iterrows():
            num_linha = idx + 2  # +2 porque +1 para header e +1 para exibição
            
            try:
                # Converte para dicionário
                dados = row.to_dict()
                dados = {k: v for k, v in dados.items() if pd.notna(v) and v != ''}
                
                # Converte valores para string para evitar AttributeError
                dados = {k: str(v).strip() if v else '' for k, v in dados.items()}
                
                codigo = dados.get('codigo', '').strip()

                
                # Validação de duplicatas na mesma importação
                if modo == 'skip_duplicates' and codigo in codigos_processados:
                    self.resultados['erros_detalhados'].append({
                        'linha': num_linha,
                        'codigo': codigo,
                        'erro': 'Código duplicado na mesma importação'
                    })
                    self.resultados['erros'] += 1
                    continue
                
                codigos_processados.add(codigo)
                
                # Valida dados
                valido, erros_validacao = self._validar_linha(num_linha, dados)
                if not valido:
                    self.resultados['erros_detalhados'].append({
                        'linha': num_linha,
                        'codigo': codigo,
                        'erro': '; '.join(erros_validacao)
                    })
                    self.resultados['erros'] += 1
                    continue
                
                # Prepara dados
                dados_preparados = self._preparar_dados_linha(dados)
                
                # Processamento baseado no modo
                if modo == 'dry_run':
                    # Simula - apenas conta
                    existente = Procedimento.objects.filter(codigo=codigo).exists()
                    if existente and modo == 'create':
                        status = 'PULA (já existe)'
                    else:
                        status = 'ATUALIZA' if existente else 'CRIA'
                    
                    self.resultados['linhas_processadas'].append({
                        'linha': num_linha,
                        'codigo': codigo,
                        'nome': dados_preparados.get('nome'),
                        'status': f'{status} (DRY-RUN)'
                    })
                
                elif modo == 'create':
                    # Apenas cria novos
                    procedimento, criado = Procedimento.objects.get_or_create(
                        codigo=codigo,
                        defaults=dados_preparados
                    )
                    
                    if criado:
                        self.resultados['criados'] += 1
                        status = 'CRIADO'
                    else:
                        status = 'PULA (já existe)'
                    
                    self.resultados['linhas_processadas'].append({
                        'linha': num_linha,
                        'codigo': codigo,
                        'nome': procedimento.nome,
                        'status': status
                    })
                
                else:  # modo == 'upsert' ou padrão
                    # Cria ou atualiza
                    procedimento, criado = Procedimento.objects.get_or_create(
                        codigo=codigo,
                        defaults=dados_preparados
                    )
                    
                    if not criado:
                        # Atualiza campos existentes
                        atualizou = False
                        for campo, valor in dados_preparados.items():
                            if campo != 'codigo' and getattr(procedimento, campo, None) != valor:
                                setattr(procedimento, campo, valor)
                                atualizou = True
                        
                        if atualizou:
                            procedimento.save()
                            self.resultados['atualizados'] += 1
                            status = 'ATUALIZADO'
                        else:
                            status = 'SEM MUDANÇAS'
                    else:
                        self.resultados['criados'] += 1
                        status = 'CRIADO'
                    
                    self.resultados['linhas_processadas'].append({
                        'linha': num_linha,
                        'codigo': codigo,
                        'nome': procedimento.nome,
                        'status': status
                    })
                
            except Exception as e:
                self.resultados['erros_detalhados'].append({
                    'linha': num_linha,
                    'codigo': dados.get('codigo', 'N/A'),
                    'erro': f'Erro ao processar: {str(e)}'
                })
                self.resultados['erros'] += 1
                logger.error(f"Erro ao processar linha {num_linha}: {e}")
        
        logger.info(f"Importação concluída: {self.resultados['criados']} criados, "
                   f"{self.resultados['atualizados']} atualizados, {self.resultados['erros']} erros")
        
        return self.resultados
    
    def gerar_relatorio_html(self) -> str:
        """Gera relatório em HTML para exibição."""
        html = f"""
        <div class="importacao-relatorio">
            <h4>📊 Relatório de Importação</h4>
            
            <div class="row mb-3">
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="text-primary">{self.resultados['total']}</h5>
                            <small>Total Linhas</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="text-success">{self.resultados['criados']}</h5>
                            <small>✅ Criados</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="text-info">{self.resultados['atualizados']}</h5>
                            <small>🔄 Atualizados</small>
                        </div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="card text-center">
                        <div class="card-body">
                            <h5 class="text-danger">{self.resultados['erros']}</h5>
                            <small>❌ Erros</small>
                        </div>
                    </div>
                </div>
            </div>
        """
        
        # Tabela de sucessos
        if self.resultados['linhas_processadas']:
            html += """
            <div class="mt-4">
                <h5>✅ Linhas Processadas com Sucesso</h5>
                <div class="table-responsive">
                    <table class="table table-sm table-hover">
                        <thead class="table-light">
                            <tr>
                                <th>Linha</th>
                                <th>Código</th>
                                <th>Nome</th>
                                <th>Status</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for item in self.resultados['linhas_processadas']:
                html += f"""
                        <tr>
                            <td>{item['linha']}</td>
                            <td><code>{item['codigo']}</code></td>
                            <td>{item['nome']}</td>
                            <td><span class="badge bg-success">{item['status']}</span></td>
                        </tr>
                """
            
            html += """
                        </tbody>
                    </table>
                </div>
            </div>
            """
        
        # Tabela de erros
        if self.resultados['erros_detalhados']:
            html += """
            <div class="mt-4">
                <h5>❌ Linhas com Erro</h5>
                <div class="table-responsive">
                    <table class="table table-sm table-hover">
                        <thead class="table-light">
                            <tr>
                                <th>Linha</th>
                                <th>Código</th>
                                <th>Erro</th>
                            </tr>
                        </thead>
                        <tbody>
            """
            
            for item in self.resultados['erros_detalhados']:
                html += f"""
                        <tr>
                            <td>{item['linha']}</td>
                            <td><code>{item.get('codigo', 'N/A')}</code></td>
                            <td><small class="text-danger">{item['erro']}</small></td>
                        </tr>
                """
            
            html += """
                        </tbody>
                    </table>
                </div>
            </div>
            """
        
        html += "</div>"
        return html
