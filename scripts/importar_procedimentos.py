"""
Script para importar procedimentos do JSON para o banco de dados Django
Execução: python manage.py shell < scripts/importar_procedimentos.py
"""

import json
import os
import django
from pathlib import Path
from typing import Dict, Any


# Setup Django
try:
    BASE_DIR = Path(__file__).resolve().parent.parent
except NameError:
    # __file__ não existe no shell interativo, usa cwd
    BASE_DIR = Path.cwd()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from qms.models import Procedimento

TRAINING_TYPES = {"POP", "IT", "INS"}  # Tipos que exigem treinamento automaticamente

def mapear_tipo_documento(tipo: str, classificacao: str) -> str:
    """Mapeia o tipo de documento para um título legível (não persiste, apenas info)."""
    mapeamento = {
        "POP": "Procedimento Operacional Padrão",
        "DOC": "Documento",
        "FOR": "Formulário",
        "TAB": "Tabela",
        "IT": "Instrução de Trabalho",
        "DEX": "Documento Externo",
        "INS": "Instrução",
    }
    return mapeamento.get(tipo, classificacao or "Documento")


def importar_procedimentos(dry_run: bool = False):
    """Importa procedimentos do JSON sem sobrescrever revisão existente.

    Regras:
      - Se já existe, só atualiza título (mantém revisao_atual).
      - Define aplica_treinamento=True somente para tipos em TRAINING_TYPES.
      - Nunca força revisao_atual para '00' em registros existentes.
    """
    json_path = BASE_DIR / "database" / "procedimentos_extraidos.json"

    print(f"📂 Lendo arquivo: {json_path}")

    with open(json_path, "r", encoding="utf-8") as f:
        procedimentos_data: Dict[str, Any] = json.load(f)

    print(f"📋 Total de {len(procedimentos_data)} procedimentos no JSON\n")

    criados = 0
    atualizados_titulo = 0
    ajustados_flag_treinamento = 0
    erros = 0

    for proc_data in procedimentos_data:
        try:
            codigo = proc_data["codigo"].strip().upper()
            nome = proc_data["nome"].strip()
            tipo = proc_data.get("tipo", "").strip().upper()
            classificacao = proc_data.get("classificacao", "Documento")
            aplica_treinamento = tipo in TRAINING_TYPES

            procedimento, created = Procedimento.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "titulo": nome[:200],
                    "revisao_atual": "00",  # só para novos
                    "aplica_treinamento": aplica_treinamento,
                },
            )

            if created:
                criados += 1
                msg_tipo = mapear_tipo_documento(tipo, classificacao)
                print(
                    f"✅ CRIADO: {codigo} - {nome[:50]}... | Tipo: {msg_tipo} | Treinamento: {aplica_treinamento}"
                )
            else:
                # Atualiza título se mudou
                novos_dados = []
                if procedimento.titulo != nome[:200]:
                    procedimento.titulo = nome[:200]
                    novos_dados.append("titulo")
                # Ajusta flag aplica_treinamento se necessário
                if procedimento.aplica_treinamento != aplica_treinamento:
                    procedimento.aplica_treinamento = aplica_treinamento
                    ajustados_flag_treinamento += 1
                    novos_dados.append("aplica_treinamento")
                if novos_dados and not dry_run:
                    procedimento.save(update_fields=novos_dados)
                if "titulo" in novos_dados:
                    atualizados_titulo += 1
                if novos_dados:
                    print(
                        f"🔄 ATUALIZADO: {codigo} ({', '.join(novos_dados)}) - Treinamento: {procedimento.aplica_treinamento}"
                    )
        except Exception as e:
            erros += 1
            print(f"❌ ERRO em {proc_data.get('codigo', 'DESCONHECIDO')}: {e}")

    print("\n" + "=" * 70)
    print("📊 RELATÓRIO DE IMPORTAÇÃO")
    print("=" * 70)
    print(f"✅ Criados: {criados}")
    print(f"🔄 Títulos atualizados: {atualizados_titulo}")
    print(f"🛠️ Flags treinamento ajustadas: {ajustados_flag_treinamento}")
    print(f"❌ Erros: {erros}")
    print(f"📦 Total processado: {len(procedimentos_data)}")
    print("=" * 70)

    total_banco = Procedimento.objects.count()
    print(f"\n🗄️  Total de procedimentos no banco: {total_banco}")

    print("\n📌 Distribuição por tipo (prefixo código):")
    tipos_count = {}
    for codigo in Procedimento.objects.values_list("codigo", flat=True):
        prefixo = codigo.split(".")[0]
        tipos_count[prefixo] = tipos_count.get(prefixo, 0) + 1
    for prefixo, count in sorted(tipos_count.items()):
        print(f"   {prefixo}: {count} procedimentos")

    print("\n✨ Importação concluída!" + (" (dry-run)" if dry_run else ""))


if __name__ == "__main__":
    # Permite dry-run via variável de ambiente DRY_RUN=1 para rodar seguro
    dry_run = os.getenv("DRY_RUN", "0") in {"1", "true", "True"}
    print(
        f"🚀 Iniciando importação de procedimentos... (dry_run={dry_run})\nTipos com treinamento automático: {', '.join(sorted(TRAINING_TYPES))}\n"
    )
    importar_procedimentos(dry_run=dry_run)
