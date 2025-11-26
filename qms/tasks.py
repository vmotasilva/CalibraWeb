from celery import shared_task


@shared_task
def ping_task():
    """Simple task used for smoke-testing the worker.

    Returns a known value so tests and monitors can ensure Celery is functional.
    """
    return "pong"


@shared_task
def import_instruments_task(job_id, filepath):
    """Placeholder: this task should wrap the heavy import_instruments logic.

    Replace this with the real implementation or call a helper service to process uploads
    asynchronously. For now it just returns success so integration tests can be built.
    """
    import os
    import pandas as pd
    from django.db import transaction
    from .models import ImportJob, Instrumento, CategoriaInstrumento, Setor, UnidadeMedida, FaixaMedicao

    try:
        job = ImportJob.objects.get(id=job_id)
        job.status = 'STARTED'
        job.save()
    except ImportJob.DoesNotExist:
        # cannot proceed without job record
        return {'error': 'job not found', 'job_id': job_id}

    count_new = 0
    count_upd = 0
    count_faixas = 0

    try:
        # Read file
        df = None
        if filepath.endswith('.csv'):
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
            except Exception:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.upper()

        def excel_date_to_date(val):
            try:
                import pandas as pd
                if pd.isnull(val):
                    return None
                s = str(val).strip()
                if not s or s in {'-', 'NaT', 'nan'}:
                    return None
                # Try parse as date string first (dayfirst for BR)
                try:
                    return pd.to_datetime(s, dayfirst=True).date()
                except Exception:
                    pass
                # Then try excel serial
                try:
                    f = float(s)
                    from datetime import datetime, timedelta
                    return (datetime(1899, 12, 30) + timedelta(days=f)).date()
                except Exception:
                    return None
            except Exception:
                return None

        with transaction.atomic():
            for _, row in df.iterrows():
                def get_val(k_list):
                    for key in k_list:
                        if key in df.columns and pd.notna(row[key]):
                            return str(row[key]).strip()
                    return None

                tag = get_val(['TAG', 'IDENTIFICACAO', 'IDENTIFICAÇÃO', 'CODIGO', 'CÓDIGO'])
                if not tag:
                    continue

                descricao = get_val(['EQUIPAMENTO', 'DESCRIÇÃO', 'DESCRICAO']) or 'Sem Descrição'

                # Additional fields based on template
                status_txt = (get_val(['STATUS']) or '').upper()
                ativo = False if ('INATIVO' in status_txt or 'BAIXADO' in status_txt) else True

                fabricante = get_val(['FABRICANTE']) or None
                modelo = get_val(['MODELO']) or None
                n_serie = get_val(['N SERIE', 'N SÉRIE', 'Nº SERIE', 'Nº SÉRIE', 'SERIE', 'SÉRIE']) or None

                setor_nome = get_val(['SETOR', 'DEPARTAMENTO', 'AREA', 'ÁREA'])
                setor_obj = None
                if setor_nome:
                    setor_obj, _ = Setor.objects.get_or_create(nome=str(setor_nome).upper())

                localizacao = get_val(['LOCALIZACAO', 'LOCALIZAÇÃO', 'LOCAL']) or None

                # Frequência em meses
                freq_raw = get_val(['FREQUENCIA_MESES', 'FREQUÊNCIA_MESES', 'FREQUENCIA', 'FREQ (MESES)', 'FREQ'])
                frequencia_meses = None
                if freq_raw:
                    try:
                        frequencia_meses = int(float(str(freq_raw).replace(',', '.')))
                    except Exception:
                        frequencia_meses = None

                # Datas
                dt_ult_calib = excel_date_to_date(row.get('DATA_ULTIMA_CALIBRACAO')) if 'DATA_ULTIMA_CALIBRACAO' in df.columns else excel_date_to_date(get_val(['DATA ULTIMA CALIBRACAO','ULTIMA CALIBRACAO','ÚLTIMA CALIBRAÇÃO','ULTIMA CALIB.']))
                data_prox = None
                if dt_ult_calib and frequencia_meses:
                    from datetime import timedelta
                    data_prox = dt_ult_calib + timedelta(days=frequencia_meses * 30)

                # Faixa e Unidade
                faixa_txt = get_val(['FAIXA', 'INTERVALO'])
                unidade_txt = get_val(['UNIDADE', 'UNID.', 'UNID'])
                unidade_obj = None
                if unidade_txt:
                    sigla = str(unidade_txt).upper()
                    unidade_obj, created_um = UnidadeMedida.objects.get_or_create(
                        sigla=sigla,
                        defaults={'nome': sigla}
                    )

                # Categoria: infer from descricao maybe
                categoria_nome = get_val(['CATEGORIA', 'TIPO'])
                categoria_obj = None
                if categoria_nome:
                    categoria_obj, _ = CategoriaInstrumento.objects.get_or_create(nome=str(categoria_nome).upper())

                defaults_map = {
                    'descricao': descricao,
                    'fabricante': fabricante,
                    'modelo': modelo,
                    'serie': n_serie,
                    'setor': setor_obj,
                    'localizacao': localizacao,
                    'data_ultima_calibracao': dt_ult_calib,
                    'data_proxima_calibracao': data_prox,
                    'categoria': categoria_obj,
                    'ativo': ativo,
                }
                # Only set frequencia_meses when parsed; otherwise let model default apply
                if frequencia_meses is not None:
                    defaults_map['frequencia_meses'] = frequencia_meses

                obj, created = Instrumento.objects.update_or_create(
                    tag=tag,
                    defaults=defaults_map,
                )
                if created:
                    count_new += 1
                else:
                    count_upd += 1

                # Create/update faixa de medição if provided
                if faixa_txt:
                    try:
                        # Parse patterns like "0-10" or "0 a 100" optionally with unit already handled separately
                        import re
                        rng = re.findall(r"[-+]?[0-9]*\.?[0-9]+", faixa_txt)
                        minimo = None
                        maximo = None
                        if len(rng) == 1:
                            minimo = 0
                            maximo = float(rng[0])
                        elif len(rng) >= 2:
                            minimo = float(rng[0])
                            maximo = float(rng[1])
                        FaixaMedicao.objects.update_or_create(
                            instrumento=obj,
                            unidade=unidade_obj,
                            defaults={'valor_minimo': minimo, 'valor_maximo': maximo}
                        )
                        count_faixas += 1
                    except Exception:
                        pass

        job.status = 'SUCCESS'
        job.result = f'Imported: {count_new} new, {count_upd} updated, {count_faixas} faixas'
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS', 'imported': count_new, 'updated': count_upd, 'faixas': count_faixas}

    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}


@shared_task
def import_historico_task(job_id, filepath):
    """Importa histórico de calibração a partir de planilha.

    Campos esperados (ver `dl_template_historico`):
    - TAG
    - DATA CALIBRAÇÃO
    - DATA APROVAÇÃO
    - N CERTIFICADO
    - ERRO ENCONTRADO
    - INCERTEZA
    - TOLERANCIA PROCESSO (+/-)
    - RBC (SIM/NAO)
    - RESULTADO
    - FORNECEDOR
    - RESPONSÁVEL
    - OBSERVAÇÕES
    """
    import pandas as pd
    from django.db import transaction
    from .models import ImportJob, Instrumento, HistoricoCalibracao

    try:
        job = ImportJob.objects.get(id=job_id)
        job.status = 'STARTED'
        job.save()
    except ImportJob.DoesNotExist:
        return {'error': 'job not found', 'job_id': job_id}

    def excel_date_to_date(val):
        try:
            if pd.isnull(val):
                return None
            s = str(val).strip()
            if not s or s in {'-', 'NaT', 'nan'}:
                return None
            try:
                return pd.to_datetime(s, dayfirst=True).date()
            except Exception:
                pass
            try:
                f = float(s)
                from datetime import datetime, timedelta
                return (datetime(1899, 12, 30) + timedelta(days=f)).date()
            except Exception:
                return None
        except Exception:
            return None

    created = 0
    updated = 0
    errors = 0

    try:
        # Read file
        if filepath.endswith('.csv'):
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
            except Exception:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.upper()

        def get_val(row, k_list):
            for key in k_list:
                if key in df.columns and pd.notna(row.get(key)):
                    return str(row.get(key)).strip()
            return None

        with transaction.atomic():
            for _, row in df.iterrows():
                tag = get_val(row, ['TAG'])
                if not tag:
                    continue
                inst = Instrumento.objects.filter(tag=tag).first()
                if not inst:
                    errors += 1
                    continue

                dt_cal = excel_date_to_date(row.get('DATA CALIBRAÇÃO') or row.get('DATA CALIBRACAO'))
                dt_apr = excel_date_to_date(row.get('DATA APROVAÇÃO') or row.get('DATA APROVACAO')) or dt_cal
                n_cert = get_val(row, ['N CERTIFICADO', 'Nº CERTIFICADO', 'NUMERO CERTIFICADO']) or 'S/N'
                erro = get_val(row, ['ERRO ENCONTRADO', 'ERRO'])
                inc = get_val(row, ['INCERTEZA', 'U'])
                tol = get_val(row, ['TOLERANCIA PROCESSO (+/-)', 'TOLERANCIA PROCESSO', 'TOLERANCIA', 'TOLERANCIA (+/-)'])
                rbc = (get_val(row, ['RBC (SIM/NAO)', 'RBC', 'SELO RBC']) or '').upper()
                tem_rbc = True if 'SIM' in rbc or 'YES' in rbc else False
                resultado = (get_val(row, ['RESULTADO']) or 'APROVADO').upper()
                fornecedor = get_val(row, ['FORNECEDOR', 'LABORATORIO', 'LABORATÓRIO'])
                responsavel = get_val(row, ['RESPONSÁVEL', 'RESPONSAVEL'])
                obs = get_val(row, ['OBSERVAÇÕES', 'OBSERVACOES', 'OBS'])

                defaults = {
                    'data_aprovacao': dt_apr,
                    'numero_certificado': n_cert,
                    'erro_encontrado': float(erro.replace(',', '.')) if erro else None,
                    'incerteza': float(inc.replace(',', '.')) if inc else None,
                    'tolerancia_usada': float(tol.replace(',', '.')) if tol else None,
                    'tem_selo_rbc': tem_rbc,
                    'resultado': resultado if resultado in {'APROVADO','CONDICIONAL','REPROVADO'} else 'APROVADO',
                    'fornecedor': fornecedor,
                    'responsavel': responsavel,
                    'observacoes': obs,
                }

                if not dt_cal:
                    errors += 1
                    continue

                obj, was_created = HistoricoCalibracao.objects.update_or_create(
                    instrumento=inst,
                    data_calibracao=dt_cal,
                    numero_certificado=n_cert,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1

        job.status = 'SUCCESS'
        job.result = f'Historico: {created} novos, {updated} atualizados, {errors} ignorados'
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS', 'created': created, 'updated': updated, 'ignored': errors}

    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}
