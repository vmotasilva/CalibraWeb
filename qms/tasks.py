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
    from .models import ImportJob
    from metrologia.models import Instrumento, CategoriaInstrumento, FaixaMedicao
    from organization.models import Setor
    from core.models import UnidadeMedida

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
    sample_errors = []

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
        try:
            df.columns = (df.columns
                          .str.normalize('NFKD')
                          .str.encode('ascii', errors='ignore')
                          .str.decode('utf-8'))
        except Exception:
            pass
        # Normalize accents to widen header matching
        try:
            df.columns = (df.columns
                          .str.normalize('NFKD')
                          .str.encode('ascii', errors='ignore')
                          .str.decode('utf-8'))
        except Exception:
            pass

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

        # Helper to find a matching category when not explicitly provided
        def infer_categoria(descricao, fabricante, modelo):
            try:
                texto = ' '.join([str(x) for x in [descricao, fabricante, modelo] if x]).upper()
                if not texto:
                    return None
                # simple contains match against existing CategoriaInstrumento names
                for cat in CategoriaInstrumento.objects.all():
                    nome = (cat.nome or '').upper()
                    if nome and nome in texto:
                        return cat
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
                    if len(sample_errors) < 5:
                        sample_errors.append('Linha sem TAG; ignorada.')
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
                    # Add months using relativedelta for calendar accuracy
                    try:
                        from dateutil.relativedelta import relativedelta
                        data_prox = dt_ult_calib + relativedelta(months=+frequencia_meses)
                    except Exception:
                        from datetime import timedelta
                        data_prox = dt_ult_calib + timedelta(days=frequencia_meses * 30)

                # Faixa e Unidade
                faixa_txt = get_val(['FAIXA', 'INTERVALO'])
                unidade_txt = get_val(['UNIDADE', 'UNID.', 'UNID'])
                unidade_obj = None
                if unidade_txt:
                    unidade_nome = str(unidade_txt).upper()
                    unidade_obj, created_um = UnidadeMedida.objects.get_or_create(
                        nome=unidade_nome
                    )

                # Categoria: infer from descricao maybe
                categoria_nome = get_val(['CATEGORIA', 'TIPO'])
                categoria_obj = None
                if categoria_nome:
                    categoria_obj, _ = CategoriaInstrumento.objects.get_or_create(nome=str(categoria_nome).upper())
                else:
                    # Try infer by description/manufacturer/model
                    categoria_obj = infer_categoria(descricao, fabricante, modelo)

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
                    except Exception as e:
                        if len(sample_errors) < 5:
                            sample_errors.append(f'Faixa inválida para {tag}: {faixa_txt}')

                # If no faixa provided and categoria has unidade_padrao, create a placeholder faixa
                try:
                    if not faixa_txt and categoria_obj and getattr(categoria_obj, 'unidade_padrao', None):
                        FaixaMedicao.objects.get_or_create(
                            instrumento=obj,
                            unidade=categoria_obj.unidade_padrao,
                            defaults={'valor_minimo': None, 'valor_maximo': None}
                        )
                except Exception:
                    pass

        job.status = 'SUCCESS'
        msg = f'Instruments: {count_new} new, {count_upd} updated, {count_faixas} ranges'
        if sample_errors:
            msg += f" | Samples: {', '.join(sample_errors)}"
        job.result = msg
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS', 'imported': count_new, 'updated': count_upd, 'faixas': count_faixas}

    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error importing instruments: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}


@shared_task
def import_historico_task(job_id, filepath):
    import logging
    logger = logging.getLogger("qms.import_historico")
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
    from .models import ImportJob
    from metrologia.models import Instrumento, HistoricoCalibracao
    
    # Converter job_id para string se necessário (pode vir como UUID)
    try:
        job_id = str(job_id)
    except Exception:
        pass

    try:
        job = ImportJob.objects.get(id=job_id)
        job.status = 'STARTED'
        job.save()
    except ImportJob.DoesNotExist:
        logger.error(f"Job não encontrado com ID: {job_id}")
        return {'error': 'job not found', 'job_id': job_id}
    except Exception as e:
        logger.error(f"Erro ao buscar job: {str(e)}")
        return {'error': f'Error fetching job: {str(e)}', 'job_id': job_id}

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
    sample_errors = []

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
                    if len(sample_errors) < 5:
                        sample_errors.append('Linha sem TAG; ignorada.')
                    continue
                inst = Instrumento.objects.filter(tag=tag).first()
                if not inst:
                    errors += 1
                    if len(sample_errors) < 5:
                        sample_errors.append(f'TAG não encontrado: {tag}')
                    continue

                dt_cal = excel_date_to_date(row.get('DATA CALIBRAÇÃO') or row.get('DATA CALIBRACAO'))
                dt_apr = excel_date_to_date(row.get('DATA APROVAÇÃO') or row.get('DATA APROVACAO')) or dt_cal
                n_cert = get_val(row, ['N CERTIFICADO', 'Nº CERTIFICADO', 'NUMERO CERTIFICADO']) or 'S/N'
                cert_path = get_val(row, ['CAMINHO DO CERTIFICADO', 'CAMINHO CERTIFICADO', 'CERTIFICADO'])
                erro_faixa = get_val(row, ['ERRO ENCONTRADO', 'ERRO'])
                inc_faixa = get_val(row, ['INCERTEZA', 'U'])
                tol_faixa = get_val(row, ['TOLERANCIA PROCESSO (+/-)', 'TOLERANCIA PROCESSO', 'TOLERANCIA', 'TOLERANCIA (+/-)'])
                # Para o histórico principal, use os mesmos valores (ou None)
                erro = erro_faixa
                inc = inc_faixa
                tol = tol_faixa
                rbc = (get_val(row, ['RBC (SIM/NAO)', 'RBC', 'SELO RBC']) or '').upper()
                tem_rbc = True if 'SIM' in rbc or 'YES' in rbc else False
                resultado = (get_val(row, ['RESULTADO']) or 'APROVADO').upper()
                fornecedor = get_val(row, ['FORNECEDOR', 'LABORATORIO', 'LABORATÓRIO'])
                responsavel = get_val(row, ['RESPONSÁVEL', 'RESPONSAVEL'])
                obs = get_val(row, ['OBSERVAÇÕES', 'OBSERVACOES', 'OBS'])

                # Compute próxima calibração based on instrument frequency
                prox = None
                if dt_cal:
                    try:
                        if inst.frequencia_meses and int(inst.frequencia_meses) > 0:
                            try:
                                from dateutil.relativedelta import relativedelta
                                prox = dt_cal + relativedelta(months=+int(inst.frequencia_meses))
                            except Exception:
                                from datetime import timedelta
                                prox = dt_cal + timedelta(days=int(inst.frequencia_meses) * 30)
                    except Exception:
                        prox = None

                defaults = {
                    'data_aprovacao': dt_apr,
                    'numero_certificado': n_cert,
                    'erro_encontrado': float(erro.replace(',', '.')) if erro else None,
                    'incerteza': float(inc.replace(',', '.')) if inc else None,
                    'tolerancia_usada': float(tol.replace(',', '.')) if tol else None,
                    'tem_selo_rbc': tem_rbc,
                    'resultado': ('REPROVADO' if 'REPRO' in resultado else ('APROVADO_COM_CORRECAO' if 'COND' in resultado else 'APROVADO_SEM_CORRECAO')),
                    'fornecedor': fornecedor,
                    'responsavel': responsavel,
                    'observacoes': obs,
                    'proxima_calibracao': prox,
                }

                if not dt_cal:
                    errors += 1
                    if len(sample_errors) < 5:
                        sample_errors.append(f'Data calibração ausente para TAG {tag}')
                    continue


                obj, was_created = HistoricoCalibracao.objects.update_or_create(
                    instrumento=inst,
                    data_calibracao=dt_cal,
                    numero_certificado=n_cert,
                    defaults=defaults,
                )

                # Process certificate file if provided
                if cert_path:
                    import os
                    from django.core.files import File
                    try:
                        # Check if cert_path is an absolute path or relative path
                        cert_file_path = cert_path
                        if not os.path.isabs(cert_file_path):
                            # Try common relative paths
                            possible_paths = [
                                os.path.join(os.getcwd(), cert_file_path),
                                os.path.join(os.path.dirname(filepath), cert_file_path),
                            ]
                            for possible in possible_paths:
                                if os.path.isfile(possible):
                                    cert_file_path = possible
                                    break
                        
                        if os.path.isfile(cert_file_path):
                            with open(cert_file_path, 'rb') as f:
                                # Get the original filename
                                cert_filename = os.path.basename(cert_file_path)
                                # Save to certificado field
                                obj.certificado.save(cert_filename, File(f), save=True)
                                logger.info(f"Certificado associado ao histórico {obj.id}: {cert_filename}")
                        else:
                            logger.warning(f"Arquivo de certificado não encontrado: {cert_path}")
                    except Exception as cert_error:
                        logger.error(f"Erro ao processar certificado para TAG {tag}: {str(cert_error)}")

                # NOVO: Associar faixa e unidade ao histórico
                faixa_txt = get_val(row, ['FAIXA'])
                unidade_txt = get_val(row, ['UNIDADE DE MEDIDA', 'UNIDADE', 'UNID.', 'UNID'])
                faixa_obj = None
                unidade_obj = None
                if unidade_txt:
                    from core.models import UnidadeMedida
                    unidade_nome = str(unidade_txt).upper()
                    unidade_obj, _ = UnidadeMedida.objects.get_or_create(nome=unidade_nome)
                if faixa_txt and unidade_obj:
                    from metrologia.models import FaixaMedicao
                    import re
                    rng = re.findall(r"[-+]?[0-9]*\.?[0-9]+", faixa_txt)
                    faixa_obj = None
                    if len(rng) >= 2:
                        valor_minimo = float(rng[0])
                        valor_maximo = float(rng[1])
                        faixa_obj = FaixaMedicao.objects.filter(
                            instrumento=inst,
                            unidade=unidade_obj,
                            valor_minimo=valor_minimo,
                            valor_maximo=valor_maximo,
                        ).first()
                        if not faixa_obj:
                            faixa_obj = FaixaMedicao.objects.create(
                                instrumento=inst,
                                unidade=unidade_obj,
                                valor_minimo=valor_minimo,
                                valor_maximo=valor_maximo,
                            )
                
                # Se nenhuma faixa foi criada pela planilha, usar as faixas existentes do instrumento
                from metrologia.models import FaixaMedicao, ResultadoFaixaCalibracao
                faixas_instrumento = FaixaMedicao.objects.filter(instrumento=inst)
                
                try:
                    if faixas_instrumento.exists():
                        # Criar resultado para cada faixa existente
                        def safe_float(val):
                            try:
                                return float(str(val).replace(",", "."))
                            except Exception:
                                return None
                        
                        erro_val = safe_float(erro_faixa) if erro_faixa else None
                        inc_val = safe_float(inc_faixa) if inc_faixa else None
                        
                        logger.info(f"TAG {tag}: Criando resultados para {faixas_instrumento.count()} faixas. Erro: {erro_val}, Incerteza: {inc_val}")
                        
                        for faixa in faixas_instrumento:
                            resultado_obj, created = ResultadoFaixaCalibracao.objects.update_or_create(
                                historico=obj,
                                faixa=faixa,
                                defaults={
                                    "valor_minimo": faixa.valor_minimo,
                                    "valor_maximo": faixa.valor_maximo,
                                    "erro_max": erro_val,
                                    "erro_min": erro_val if erro_val else None,
                                    "incerteza": inc_val,
                                },
                            )
                            logger.info(f"  Faixa {faixa.valor_minimo}-{faixa.valor_maximo}: {'CREATED' if created else 'UPDATED'} resultado {resultado_obj.id}")
                            # Força recálculo do resultado
                            resultado_obj.save()
                    elif faixa_obj:
                        # Criar resultado para a faixa da planilha
                        def safe_float(val):
                            try:
                                return float(str(val).replace(",", "."))
                            except Exception:
                                return None
                        
                        erro_val = safe_float(erro_faixa) if erro_faixa else None
                        inc_val = safe_float(inc_faixa) if inc_faixa else None
                        
                        logger.info(f"TAG {tag}: Criando resultado para faixa da planilha {faixa_obj.valor_minimo}-{faixa_obj.valor_maximo}")
                        
                        resultado_obj, created = ResultadoFaixaCalibracao.objects.update_or_create(
                            historico=obj,
                            faixa=faixa_obj,
                            defaults={
                                "valor_minimo": faixa_obj.valor_minimo,
                                "valor_maximo": faixa_obj.valor_maximo,
                                "erro_max": erro_val,
                                "erro_min": erro_val if erro_val else None,
                                "incerteza": inc_val,
                            },
                        )
                        logger.info(f"  Resultado criado: {resultado_obj.id}")
                        resultado_obj.save()
                except Exception as faixa_error:
                    logger.error(f"Erro ao criar resultados de faixa para TAG {tag}: {str(faixa_error)}", exc_info=True)

                # Ensure Instrumento fields reflect latest calibration
                try:
                    if dt_cal:
                        inst.data_ultima_calibracao = max(filter(None, [inst.data_ultima_calibracao, dt_cal])) if inst.data_ultima_calibracao else dt_cal
                    if prox:
                        inst.data_proxima_calibracao = prox
                    elif dt_cal and inst.frequencia_meses:
                        # fallback computed above already handled
                        pass
                    fields = [f for f in ['data_ultima_calibracao','data_proxima_calibracao'] if getattr(inst, f) is not None]
                    if fields:
                        inst.save(update_fields=fields)
                    else:
                        inst.save()
                except Exception:
                    pass

                if was_created:
                    created += 1
                else:
                    updated += 1

        job.status = 'SUCCESS'
        msg = f'Historico: {created} new, {updated} updated, {errors} ignored (missing TAG/date)'
        if sample_errors:
            msg += f" | Samples: {', '.join(sample_errors)}"
        job.result = msg
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS', 'created': created, 'updated': updated, 'ignored': errors}

    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error importing historico: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}


@shared_task
def import_colab_task(job_id, filepath):
    """Importa colaboradores (RH) a partir de planilha."""
    import re
    import pandas as pd
    from django.db import transaction
    from .models import ImportJob
    from rh.models import Colaborador
    from organization.models import Setor, CentroCusto

    try:
        job = ImportJob.objects.get(id=job_id)
        job.status = 'STARTED'
        job.save()
    except ImportJob.DoesNotExist:
        return {'error': 'job not found', 'job_id': job_id}

    try:
        if filepath.endswith('.csv'):
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
            except Exception:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.upper()
        df.columns = df.columns.str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')

        count_new = 0
        count_upd = 0
        count_lider = 0
        count_super = 0
        count_gerente = 0
        sample_errors = []

        with transaction.atomic():
            for _, row in df.iterrows():
                def get_val(keys):
                    for k in keys:
                        for col in df.columns:
                            if k in col and pd.notna(row[col]):
                                return str(row[col]).strip()
                    return None

                matricula = get_val(["MATRICULA", "MAT", "RE"]) or ''
                matricula = matricula.split('.') [0]
                nome = get_val(["NOME", "COLABORADOR", "FUNCIONARIO"])
                if not matricula or not nome:
                    if len(sample_errors) < 5:
                        sample_errors.append('Linha sem matrícula ou nome; ignorada.')
                    continue
                cpf_raw = get_val(["CPF", "DOC"])
                cpf = None
                if cpf_raw:
                    limpo = re.sub(r"[^0-9]", "", str(cpf_raw))
                    if len(limpo) == 11 and limpo != "00000000000" and limpo != "00":
                        cpf = limpo
                setor_nome = get_val(["SETOR", "DEPARTAMENTO", "AREA"]) or None
                setor_obj = None
                if setor_nome:
                    setor_obj, _ = Setor.objects.get_or_create(nome=setor_nome.upper())
                cc_raw = get_val(["CENTRO DE CUSTO", "CC"]) or None
                cc_obj = None
                if cc_raw and setor_obj:
                    parts = cc_raw.split("-")
                    c_code = parts[0].strip()
                    c_desc = parts[1].strip() if len(parts) > 1 else "Importado"
                    cc_obj, _ = CentroCusto.objects.get_or_create(codigo=c_code, setor=setor_obj, defaults={'descricao': c_desc})

                turno_raw = str(get_val(["TURNO", "HORARIO"]) or "ADM").upper()
                turno = "ADM"
                if "1" in turno_raw:
                    turno = "TURNO_1"
                elif "2" in turno_raw:
                    turno = "TURNO_2"
                elif "3" in turno_raw:
                    turno = "TURNO_3"
                elif "12" in turno_raw:
                    turno = "12X36"

                status_raw = str(get_val(["STATUS"]) or "ATIVO").upper()
                is_active = False if ("INATIVO" in status_raw or "DEMITIDO" in status_raw) else True

                sal_raw = get_val(["SALARIO"]) or None
                salario = float(str(sal_raw).replace(',', '.')) if sal_raw else None

                obj, created = Colaborador.objects.update_or_create(
                    matricula=matricula,
                    defaults={
                        'nome_completo': nome.upper(),
                        'cpf': cpf,
                        'cargo': get_val(["CARGO", "FUNCAO"]) or "Não Informado",
                        'grupo': get_val(["GRUPO", "MACRO"]) or "Geral",
                        'setor': setor_obj,
                        'centro_custo': cc_obj,
                        'turno': turno,
                        'salario': salario,
                        'is_active': is_active,
                    }
                )
                if created:
                    count_new += 1
                else:
                    count_upd += 1

            # vínculo liderança
            from rh.models import Colaborador as C
            for _, row in df.iterrows():
                def get_val_h(keys):
                    for k in keys:
                        for col in df.columns:
                            if k in col and pd.notna(row[col]):
                                return str(row[col]).strip()
                    return None
                matricula = (get_val_h(["MATRICULA", "MAT", "RE"]) or '').split('.')[0]
                def norm_mat(v):
                    return v.split('.') [0] if v else None
                mat_lider = norm_mat(get_val_h(["MAT_LIDER", "LIDER", "COD_LIDER"]))
                mat_super = norm_mat(get_val_h(["MAT_SUPERVISOR", "SUPERVISOR", "COD_SUPERVISOR"]))
                mat_ger = norm_mat(get_val_h(["MAT_GERENTE", "GERENTE", "COD_GERENTE"]))
                if matricula:
                    colab = C.objects.filter(matricula=matricula).first()
                    if not colab:
                        continue
                    update_fields = []
                    if mat_lider and mat_lider != matricula:
                        lider = C.objects.filter(matricula=mat_lider).first()
                        if lider:
                            colab.lider = lider; update_fields.append('lider'); count_lider += 1
                    if mat_super and mat_super != matricula:
                        superv = C.objects.filter(matricula=mat_super).first()
                        if superv:
                            colab.supervisor = superv; update_fields.append('supervisor'); count_super += 1
                    if mat_ger and mat_ger != matricula:
                        ger = C.objects.filter(matricula=mat_ger).first()
                        if ger:
                            colab.gerente = ger; update_fields.append('gerente'); count_gerente += 1
                    if update_fields:
                        colab.save(update_fields=update_fields)

        job.status = 'SUCCESS'
        msg = (f"RH: {count_new} Novos, {count_upd} Atualizados, "
               f"{count_lider} líderes, {count_super} supervisores, {count_gerente} gerentes vinculados.")
        if sample_errors:
            msg += f" | Samples: {', '.join(sample_errors)}"
        job.result = msg
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS'}
    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}


@shared_task
def import_hierarquia_task(job_id, filepath):
    """Importa hierarquia Setor/Turno (RH) a partir de planilha."""
    import pandas as pd
    from django.db import transaction
    from .models import ImportJob
    from rh.models import Colaborador
    from organization.models import Setor, HierarquiaSetor

    try:
        job = ImportJob.objects.get(id=job_id)
        job.status = 'STARTED'
        job.save()
    except ImportJob.DoesNotExist:
        return {'error': 'job not found', 'job_id': job_id}

    try:
        if filepath.endswith('.csv'):
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
            except Exception:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.upper()

        def get_val(row, keys):
            for k in keys:
                if k in df.columns and pd.notna(row.get(k)):
                    return str(row.get(k)).strip()
            return None

        count = 0
        sample_errors = []
        with transaction.atomic():
            for _, row in df.iterrows():
                setor_nome = get_val(row, ["SETOR", "DEPARTAMENTO", "AREA", "ÁREA"]) or None
                turno_raw = (get_val(row, ["TURNO"]) or "ADM").upper()
                turno = "ADM"
                if "1" in turno_raw:
                    turno = "TURNO_1"
                elif "2" in turno_raw:
                    turno = "TURNO_2"
                elif "3" in turno_raw:
                    turno = "TURNO_3"
                elif "12" in turno_raw:
                    turno = "12X36"
                if not setor_nome:
                    if len(sample_errors) < 5:
                        sample_errors.append('Linha sem setor; ignorada.')
                    continue
                setor_obj, _ = Setor.objects.get_or_create(nome=str(setor_nome).upper())
                def norm_mat(v):
                    return v.split('.') [0] if v else None
                mat_lider = norm_mat(get_val(row, ["MAT_LIDER", "LIDER", "COD_LIDER"]))
                mat_super = norm_mat(get_val(row, ["MAT_SUPERVISOR", "SUPERVISOR", "COD_SUPERVISOR"]))
                mat_ger = norm_mat(get_val(row, ["MAT_GERENTE", "GERENTE", "COD_GERENTE"]))
                mat_dir = norm_mat(get_val(row, ["MAT_DIRETOR", "DIRETOR", "COD_DIRETOR"]))
                def find_colab(mat):
                    if not mat:
                        return None
                    return Colaborador.objects.filter(matricula=mat).first()
                HierarquiaSetor.objects.update_or_create(
                    setor=setor_obj,
                    turno=turno,
                    defaults={
                        'lider': find_colab(mat_lider),
                        'supervisor': find_colab(mat_super),
                        'gerente': find_colab(mat_ger),
                        'diretor': find_colab(mat_dir),
                    }
                )
                count += 1

        job.status = 'SUCCESS'
        msg = f"Hierarquia importada: {count} linhas processadas."
        if sample_errors:
            msg += f" | Samples: {', '.join(sample_errors)}"
        job.result = msg
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS', 'processed': count}
    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error importing hierarquia: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}


@shared_task
def import_ferias_task(job_id, filepath):
    """Importa férias (RH) a partir de planilha."""
    import pandas as pd
    from django.db import transaction
    from .models import ImportJob
    from rh.models import Colaborador, Ferias

    try:
        job = ImportJob.objects.get(id=job_id)
        job.status = 'STARTED'
        job.save()
    except ImportJob.DoesNotExist:
        return {'error': 'job not found', 'job_id': job_id}

    def parse_date(val):
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

    try:
        if filepath.endswith('.csv'):
            try:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='latin1')
            except Exception:
                df = pd.read_csv(filepath, sep=None, engine='python', encoding='utf-8')
        else:
            df = pd.read_excel(filepath)

        df.columns = df.columns.str.strip().str.upper()

        count = 0
        sample_errors = []
        with transaction.atomic():
            for _, row in df.iterrows():
                matricula = str(row.get('MATRICULA') or '').strip()
                if not matricula:
                    if len(sample_errors) < 5:
                        sample_errors.append('Linha sem matrícula; ignorada.')
                    continue
                colab = Colaborador.objects.filter(matricula=matricula.split('.') [0]).first()
                if not colab:
                    if len(sample_errors) < 5:
                        sample_errors.append(f'Colaborador não encontrado: {matricula}')
                    continue
                dt_aq_ini = parse_date(row.get('AQUISITIVO_INICIO'))
                dt_aq_fim = parse_date(row.get('AQUISITIVO_FIM'))
                dt_ini = parse_date(row.get('DATA_INICIO'))
                dt_fim = parse_date(row.get('DATA_FIM'))
                dias_vend = row.get('DIAS_VENDIDOS')
                try:
                    dias_vend = int(float(dias_vend)) if dias_vend not in [None, ''] else 0
                except Exception:
                    dias_vend = 0
                if not dt_aq_fim:
                    if len(sample_errors) < 5:
                        sample_errors.append(f'Período aquisitivo fim ausente para {matricula}')
                    continue
                Ferias.objects.update_or_create(
                    colaborador=colab,
                    periodo_aquisitivo_fim=dt_aq_fim,
                    defaults={
                        'periodo_aquisitivo_inicio': dt_aq_ini,
                        'data_inicio': dt_ini,
                        'data_fim': dt_fim,
                        'dias_vendidos': dias_vend,
                        'status': (str(row.get('STATUS') or 'PROGRAMADAS').strip() or 'PROGRAMADAS'),
                    }
                )
                count += 1

        job.status = 'SUCCESS'
        msg = f"{count} registros de férias importados!"
        if sample_errors:
            msg += f" | Samples: {', '.join(sample_errors)}"
        job.result = msg
        job.save()
        return {'job_id': str(job_id), 'status': 'SUCCESS', 'processed': count}
    except Exception as exc:
        job.status = 'FAILURE'
        job.result = f'Error importing ferias: {str(exc)}'
        job.save()
        return {'job_id': str(job_id), 'status': 'FAILURE', 'error': str(exc)}


# ==============================================================================
# SCHEDULED REPORTS TASKS - FASE 5
# ==============================================================================

@shared_task
def gerar_relatorio_diario_vencidos():
    """
    Gera relatório diário de instrumentos vencidos.
    Pode ser agendado via Celery Beat.
    """
    from datetime import date
    from django.core.mail import EmailMessage
    from metrologia.models import Instrumento
    from metrologia.exportadores import ExportadorInstrumentos
    from io import BytesIO
    
    try:
        # Obter instrumentos vencidos
        today = date.today()
        vencidos = Instrumento.objects.filter(
            data_proxima_calibracao__lt=today,
            ativo=True
        ).select_related('setor', 'categoria').order_by('data_proxima_calibracao')
        
        if vencidos.count() == 0:
            return {
                'status': 'SUCCESS',
                'message': 'Nenhum instrumento vencido encontrado'
            }
        
        # Gerar Excel
        exportador = ExportadorInstrumentos(vencidos)
        response = exportador.exportar_excel()
        
        # Preparar email
        email = EmailMessage(
            subject=f'[CalibraWeb] Relatório de Instrumentos Vencidos - {today.strftime("%d/%m/%Y")}',
            body=f'Relatório diário com {vencidos.count()} instrumentos com calibração vencida.\n\nAnexo: vencidos.xlsx',
            from_email='calibra@empresa.com',
            to=['gestor@empresa.com'],  # Configurar emails reais
        )
        
        # Adicionar attachment
        email.attach('vencidos.xlsx', response.content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        # Enviar
        email.send()
        
        return {
            'status': 'SUCCESS',
            'message': f'Relatório enviado com {vencidos.count()} instrumentos vencidos',
            'count': vencidos.count()
        }
    
    except Exception as e:
        return {
            'status': 'FAILURE',
            'message': str(e),
            'error': type(e).__name__
        }


@shared_task
def gerar_relatorio_semanal_estatisticas():
    """
    Gera relatório semanal com estatísticas completas.
    Pode ser agendado via Celery Beat (toda segunda-feira).
    """
    from datetime import date, timedelta
    from django.core.mail import EmailMessage
    from django.db.models import Q, Count
    from metrologia.models import Instrumento, CategoriaInstrumento, HistoricoCalibracao
    from organization.models import Setor
    from metrologia.exportadores import ExportadorEstatisticas
    
    try:
        today = date.today()
        
        # Calcular estatísticas
        total_instrumentos = Instrumento.objects.count()
        total_vencidos = Instrumento.objects.filter(
            data_proxima_calibracao__lt=today,
            ativo=True
        ).count()
        
        vencer_30_dias = Instrumento.objects.filter(
            data_proxima_calibracao__gte=today,
            data_proxima_calibracao__lte=today + timedelta(days=30),
            ativo=True
        ).count()
        
        total_vigentes = Instrumento.objects.filter(
            data_proxima_calibracao__gte=today,
            ativo=True
        ).count()
        
        total_historicos = HistoricoCalibracao.objects.count()
        aprovados = HistoricoCalibracao.objects.filter(
            resultado='APROVADO_SEM_CORRECAO'
        ).count()
        
        # Preparar dados
        data = {
            'total_instrumentos': total_instrumentos,
            'total_vencidos': total_vencidos,
            'vencer_30_dias': vencer_30_dias,
            'total_vigentes': total_vigentes,
            'total_historicos': total_historicos,
            'aprovados': aprovados,
            'com_correcao': HistoricoCalibracao.objects.filter(resultado='APROVADO_COM_CORRECAO').count(),
            'reprovados': HistoricoCalibracao.objects.filter(resultado='REPROVADO').count(),
            'por_categoria': CategoriaInstrumento.objects.annotate(
                total=Count('instrumento__id'),
                vencidos=Count('instrumento', filter=Q(instrumento__data_proxima_calibracao__lt=today, instrumento__ativo=True))
            ).filter(total__gt=0),
            'por_setor': Setor.objects.annotate(
                total=Count('instrumento__id'),
                vencidos=Count('instrumento', filter=Q(instrumento__data_proxima_calibracao__lt=today, instrumento__ativo=True))
            ).filter(total__gt=0),
            'percentage_vencidos': round((total_vencidos / total_instrumentos * 100) if total_instrumentos > 0 else 0, 1),
            'percentage_aprovados': round((aprovados / total_historicos * 100) if total_historicos > 0 else 0, 1),
        }
        
        # Gerar Excel
        exportador = ExportadorEstatisticas(data)
        response = exportador.exportar_excel()
        
        # Preparar email
        email = EmailMessage(
            subject=f'[CalibraWeb] Relatório Semanal de Estatísticas - Semana de {today.strftime("%d/%m/%Y")}',
            body=f'''
Relatório Semanal de Calibração

Resumo:
- Total de Instrumentos: {total_instrumentos}
- Vencidos: {total_vencidos} ({data['percentage_vencidos']}%)
- A Vencer (30 dias): {vencer_30_dias}
- Vigentes: {total_vigentes}

- Total de Calibrações: {total_historicos}
- Aprovadas: {aprovados} ({data['percentage_aprovados']}%)

Arquivo em anexo: estatisticas.xlsx
            ''',
            from_email='calibra@empresa.com',
            to=['gestor@empresa.com'],  # Configurar emails reais
        )
        
        # Adicionar attachment
        email.attach('estatisticas.xlsx', response.content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        
        # Enviar
        email.send()
        
        return {
            'status': 'SUCCESS',
            'message': 'Relatório semanal enviado',
            'total_instrumentos': total_instrumentos,
            'total_vencidos': total_vencidos,
        }
    
    except Exception as e:
        return {
            'status': 'FAILURE',
            'message': str(e),
            'error': type(e).__name__
        }


@shared_task
def gerar_relatorio_alerta_critico():
    """
    Gera alerta imediato se houver instrumentos com data vencida.
    Pode ser executado a cada 4 horas via Celery Beat.
    """
    from datetime import date
    from django.core.mail import EmailMessage
    from metrologia.models import Instrumento
    
    try:
        today = date.today()
        
        # Verificar instrumentos vencidos HOJE (criação de alerta crítico)
        vencidos_hoje = Instrumento.objects.filter(
            data_proxima_calibracao=today,
            ativo=True
        ).count()
        
        vencidos_total = Instrumento.objects.filter(
            data_proxima_calibracao__lt=today,
            ativo=True
        ).count()
        
        if vencidos_total == 0:
            return {'status': 'NO_ALERTS', 'message': 'Nenhum instrumento vencido'}
        
        # Enviar alerta se houver vencidos
        email = EmailMessage(
            subject='[ALERTA CRÍTICO] Instrumentos com Calibração Vencida - Ação Imediata Necessária!',
            body=f'''
ATENÇÃO: EXISTEM INSTRUMENTOS COM CALIBRAÇÃO VENCIDA

⚠️ Total de Instrumentos Vencidos: {vencidos_total}

Este é um alerta automático do sistema CalibraWeb.
Acesse o sistema imediatamente para consultar detalhes e tomar ações corretivas.

URL: https://seu-dominio.com/api/metrologia/vencidos/

---
Alerta gerado automaticamente pelo CalibraWeb em {today.strftime("%d/%m/%Y %H:%M")}
            ''',
            from_email='calibra@empresa.com',
            to=['gestor@empresa.com', 'supervisor@empresa.com'],  # Configurar emails reais
        )
        
        email.send()
        
        return {
            'status': 'ALERT_SENT',
            'message': f'Alerta enviado: {vencidos_total} instrumentos vencidos',
            'vencidos_count': vencidos_total
        }
    
    except Exception as e:
        return {
            'status': 'FAILURE',
            'message': str(e),
            'error': type(e).__name__
        }

