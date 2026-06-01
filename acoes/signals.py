from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.conf import settings
from .models import AcaoCorretiva
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=AcaoCorretiva)
def sync_acao_to_appwrite(sender, instance, **kwargs):
    from core.appwrite_client import APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY
    if getattr(settings, 'TESTING', False) or not (APPWRITE_ENDPOINT and APPWRITE_PROJECT and APPWRITE_API_KEY):
        return

    try:
        from core.appwrite_client import db, APPWRITE_DATABASE_ID
        from core.appwrite_client import patch_appwrite_requests
        from appwrite.exception import AppwriteException

        patch_appwrite_requests()
        collection_id = 'acoes'
        doc_id = f"django_{instance.id}"

        data = {
            'numero_registro': instance.numero_registro or '',
            'ano': instance.ano or 0,
            'unidade': instance.unidade or '',
            'titulo': instance.titulo or '',
            'descricao': instance.descricao or '',
            'tipo': instance.tipo or 'corretiva',
            'tipo_solucao': instance.tipo_solucao or '',
            'prioridade': instance.prioridade or 'media',
            'origem': instance.origem or '',
            'causa_raiz': instance.causa_raiz or '',
            'status': instance.status or 'aberta',
            'data_abertura': str(instance.data_abertura) if instance.data_abertura else '',
            'data_vencimento': str(instance.data_vencimento) if instance.data_vencimento else '',
            'data_conclusao': str(instance.data_conclusao) if instance.data_conclusao else '',
            'criado_por': instance.criado_por.nome_completo if instance.criado_por else '',
            'responsavel': instance.responsavel.nome_completo if instance.responsavel else '',
            'responsavel_id': str(instance.responsavel.id) if instance.responsavel else '',
            'acoes_status_resumo': '',
        }

        for key, val in list(data.items()):
            if val is None:
                data[key] = ''

        try:
            db.get_document(
                database_id=APPWRITE_DATABASE_ID,
                collection_id=collection_id,
                document_id=doc_id
            )
            db.update_document(
                database_id=APPWRITE_DATABASE_ID,
                collection_id=collection_id,
                document_id=doc_id,
                data=data
            )
            logger.info(f"Appwrite sync: Document {doc_id} updated successfully.")
        except AppwriteException as ex:
            if ex.code == 404 or "not found" in str(ex).lower():
                db.create_document(
                    database_id=APPWRITE_DATABASE_ID,
                    collection_id=collection_id,
                    document_id=doc_id,
                    data=data
                )
                logger.info(f"Appwrite sync: Document {doc_id} created successfully.")
            else:
                raise ex

    except Exception as e:
        logger.error(f"Appwrite sync failed for AcaoCorretiva {instance.id}: {e}", exc_info=True)


@receiver(post_delete, sender=AcaoCorretiva)
def delete_acao_from_appwrite(sender, instance, **kwargs):
    from core.appwrite_client import APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY
    if getattr(settings, 'TESTING', False) or not (APPWRITE_ENDPOINT and APPWRITE_PROJECT and APPWRITE_API_KEY):
        return

    try:
        from core.appwrite_client import db, APPWRITE_DATABASE_ID
        from core.appwrite_client import patch_appwrite_requests
        from appwrite.exception import AppwriteException

        patch_appwrite_requests()
        collection_id = 'acoes'
        doc_id = f"django_{instance.id}"

        try:
            db.delete_document(
                database_id=APPWRITE_DATABASE_ID,
                collection_id=collection_id,
                document_id=doc_id
            )
            logger.info(f"Appwrite sync: Document {doc_id} deleted successfully.")
        except AppwriteException as ex:
            if ex.code == 404 or "not found" in str(ex).lower():
                pass
            else:
                raise ex
    except Exception as e:
        logger.error(f"Appwrite sync delete failed for AcaoCorretiva {instance.id}: {e}", exc_info=True)


def sync_all_acoes_to_appwrite():
    """Sincroniza todas as Acoes Corretivas do banco local para o Appwrite"""
    from core.appwrite_client import db, APPWRITE_DATABASE_ID, APPWRITE_ENDPOINT, APPWRITE_PROJECT, APPWRITE_API_KEY
    from core.appwrite_client import patch_appwrite_requests
    from appwrite.exception import AppwriteException

    if getattr(settings, 'TESTING', False) or not (APPWRITE_ENDPOINT and APPWRITE_PROJECT and APPWRITE_API_KEY):
        logger.warning("Appwrite credentials not set or in testing mode. Skipping bulk sync.")
        return

    patch_appwrite_requests()
    collection_id = 'acoes'
    acoes = AcaoCorretiva.objects.all()
    logger.info(f"Bulk sync to Appwrite: syncing {len(acoes)} records...")

    success = 0
    errors = 0

    for acao in acoes:
        doc_id = f"django_{acao.id}"
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
            'acoes_status_resumo': '',
        }

        for key, val in list(data.items()):
            if val is None:
                data[key] = ''

        try:
            try:
                db.get_document(
                    database_id=APPWRITE_DATABASE_ID,
                    collection_id=collection_id,
                    document_id=doc_id
                )
                db.update_document(
                    database_id=APPWRITE_DATABASE_ID,
                    collection_id=collection_id,
                    document_id=doc_id,
                    data=data
                )
            except AppwriteException as ex:
                if ex.code == 404 or "not found" in str(ex).lower():
                    db.create_document(
                        database_id=APPWRITE_DATABASE_ID,
                        collection_id=collection_id,
                        document_id=doc_id,
                        data=data
                    )
                else:
                    raise ex
            success += 1
        except Exception as e:
            logger.error(f"Bulk sync to Appwrite: failed for document {doc_id}: {e}")
            errors += 1

    logger.info(f"Bulk sync completed: {success} successes, {errors} errors.")
