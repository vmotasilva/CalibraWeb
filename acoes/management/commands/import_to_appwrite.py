import os
from django.core.management.base import BaseCommand
from acoes.models import AcaoCorretiva
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.exception import AppwriteException

class Command(BaseCommand):
    help = 'Exporta ações corretivas da base relacional local para a coleção acoes no Appwrite.'

    def handle(self, *args, **options):
        # 1. Carregar variáveis
        from dotenv import load_dotenv
        load_dotenv()
        
        endpoint = os.getenv('APPWRITE_ENDPOINT')
        project = os.getenv('APPWRITE_PROJECT')
        api_key = os.getenv('APPWRITE_API_KEY')
        database_id = os.getenv('APPWRITE_DATABASE_ID', 'default')

        if not all([endpoint, project, api_key]):
            self.stdout.write(self.style.ERROR(
                'Erro: As variáveis de ambiente do Appwrite (APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY) não estão configuradas.'
            ))
            return

        # 2. Inicializar Appwrite
        client = Client()
        client.set_endpoint(endpoint)
        client.set_project(project)
        client.set_key(api_key)
        db_service = Databases(client)

        collection_id = 'acoes'

        # 3. Buscar todas as ações no banco local
        acoes = AcaoCorretiva.objects.all()
        total_acoes = acoes.count()
        self.stdout.write(f'Encontradas {total_acoes} ações corretivas locais. Iniciando exportação para o Appwrite...')

        success_count = 0
        error_count = 0

        for acao in acoes:
            # Construir dados no formato esperado no Appwrite
            data = {
                'numero_registro': acao.numero_registro or '',
                'ano': acao.ano or 0,
                'unidade': acao.unidade or '',
                'titulo': acao.titulo or '',
                'descricao': acao.descricao or '',
                'tipo': acao.tipo or 'corretiva',
                'tipo_solucao': acao.tipo_solucao or '',
                'prioridade': acao.prioridade or 'media',
                'origem': acao.origem or '',
                'causa_raiz': acao.causa_raiz or '',
                'status': acao.status or 'aberta',
                'data_abertura': str(acao.data_abertura) if acao.data_abertura else '',
                'data_vencimento': str(acao.data_vencimento) if acao.data_vencimento else '',
                'data_conclusao': str(acao.data_conclusao) if acao.data_conclusao else '',
                'criado_por': acao.criado_por.nome_completo if acao.criado_por else '',
                'responsavel': acao.responsavel.nome_completo if acao.responsavel else '',
                'responsavel_id': str(acao.responsavel.id) if acao.responsavel else '',
                'acoes_status_resumo': '', # Pode ser computado depois
            }

            # Garantir que não passamos None
            for key, val in list(data.items()):
                if val is None:
                    data[key] = ''

            # Enviar para o Appwrite
            try:
                # Usar id único baseado na chave primária do Django para garantir idempotência
                doc_id = f"django_{acao.id}"
                
                try:
                    db_service.get_document(
                        database_id=database_id,
                        collection_id=collection_id,
                        document_id=doc_id
                    )
                    # Se não deu erro, já existe. Vamos atualizar.
                    db_service.update_document(
                        database_id=database_id,
                        collection_id=collection_id,
                        document_id=doc_id,
                        data=data
                    )
                    self.stdout.write(f'  [Atualizado] Ação {acao.numero_registro} (ID: {doc_id})')
                except AppwriteException as ex:
                    if ex.code == 404 or "not found" in str(ex).lower():
                        # Não encontrado, criar novo
                        db_service.create_document(
                            database_id=database_id,
                            collection_id=collection_id,
                            document_id=doc_id,
                            data=data
                        )
                        self.stdout.write(f'  [Criado] Ação {acao.numero_registro} (ID: {doc_id})')
                    else:
                        raise ex

                success_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'  [Erro] Falha ao exportar ação {acao.numero_registro or acao.id}: {e}'
                ))
                error_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nExportação concluída! Sucesso: {success_count}/{total_acoes}, Erros: {error_count}'
        ))
