import os
import re
from pathlib import Path
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from rh.models import Colaborador


def limpar_cpf(valor):
    if not valor or pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return None
    digitos = digitos.zfill(11)
    if len(digitos) > 11:
        digitos = digitos[-11:]
    return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"


class Command(BaseCommand):
    help = "Atualiza os CPFs dos colaboradores na base de dados (Produção/Local) a partir de uma planilha Excel"

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            type=str,
            default="colaboradores_atualizado_com_cpf.xlsx",
            help="Caminho do arquivo Excel com os dados atualizados",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa uma simulação sem persistir alterações no banco de dados",
        )
        parser.add_argument(
            "--criar-se-nao-existir",
            action="store_true",
            help="Cria o colaborador se a matrícula não for encontrada na base",
        )

    def handle(self, *args, **options):
        caminho_arquivo = Path(options["arquivo"])
        dry_run = options["dry_run"]
        criar = options["criar_se_nao_existir"]

        if not caminho_arquivo.exists():
            raise CommandError(f"Arquivo não encontrado: {caminho_arquivo.resolve()}")

        self.stdout.write(self.style.NOTICE(f"Iniciando leitura do arquivo: {caminho_arquivo.name}"))
        
        try:
            df = pd.read_excel(caminho_arquivo, dtype=str)
        except Exception as e:
            raise CommandError(f"Erro ao ler arquivo Excel: {str(e)}")

        df.columns = [str(c).strip().upper() for c in df.columns]

        col_matricula = next((c for c in df.columns if "MATRICULA" in c), None)
        col_cpf = next((c for c in df.columns if "CPF" in c), None)
        col_nome = next((c for c in df.columns if "NOME" in c), None)

        if not col_matricula or not col_cpf:
            raise CommandError(f"Colunas obrigatórias não encontradas no Excel. Colunas disponíveis: {list(df.columns)}")

        total_registros = len(df)
        atualizados = 0
        criados = 0
        inalterados = 0
        erros = 0

        self.stdout.write(f"Total de registros na planilha: {total_registros}")
        if dry_run:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN ATIVADO: Nenhuma alteração será gravada no banco."))

        with transaction.atomic():
            for idx, row in df.iterrows():
                matricula = str(row[col_matricula]).strip() if pd.notna(row[col_matricula]) else ""
                cpf_bruto = row[col_cpf]
                nome = str(row[col_nome]).strip() if col_nome and pd.notna(row[col_nome]) else ""
                
                cpf_formatado = limpar_cpf(cpf_bruto)

                if not matricula:
                    self.stdout.write(self.style.WARNING(f"Linha {idx + 2}: Matrícula vazia. Ignorando."))
                    erros += 1
                    continue

                try:
                    colaborador = Colaborador.objects.filter(matricula=matricula).first()
                    
                    if not colaborador and nome:
                        # Tenta buscar por nome se a matrícula não bater
                        colaborador = Colaborador.objects.filter(nome_completo__iexact=nome).first()

                    if colaborador:
                        if colaborador.cpf != cpf_formatado:
                            colaborador.cpf = cpf_formatado
                            if not dry_run:
                                colaborador.save(update_fields=["cpf"])
                            atualizados += 1
                            self.stdout.write(f"[ATUALIZADO] Matrícula: {matricula} | Nome: {colaborador.nome_completo} | CPF: {cpf_formatado}")
                        else:
                            inalterados += 1
                    else:
                        if criar:
                            if not dry_run:
                                Colaborador.objects.create(
                                    matricula=matricula,
                                    nome_completo=nome or f"Colaborador {matricula}",
                                    cpf=cpf_formatado,
                                    grupo="GERAL",
                                )
                            criados += 1
                            self.stdout.write(f"[CRIADO] Matrícula: {matricula} | Nome: {nome} | CPF: {cpf_formatado}")
                        else:
                            self.stdout.write(self.style.WARNING(f"[NÃO ENCONTRADO] Matrícula: {matricula} | Nome: {nome}"))
                            erros += 1

                except Exception as ex:
                    self.stdout.write(self.style.ERROR(f"Erro ao processar matrícula {matricula}: {str(ex)}"))
                    erros += 1

            if dry_run:
                self.stdout.write(self.style.WARNING("Transação desfeita (dry-run)."))
                transaction.set_rollback(True)

        self.stdout.write("\n" + "=" * 40)
        self.stdout.write(self.style.SUCCESS("RESUMO DA EXECUÇÃO:"))
        self.stdout.write(f"Atualizados: {atualizados}")
        self.stdout.write(f"Criados:     {criados}")
        self.stdout.write(f"Inalterados: {inalterados}")
        self.stdout.write(f"Não achados: {erros}")
        self.stdout.write("=" * 40)
