"""
Script para extrair todos os procedimentos do PDF de Lista Mestra
e salvar em formato JSON estruturado para importação no Django.
"""

import PyPDF2
import re
import json
from pathlib import Path

def extrair_procedimentos_pdf(pdf_path):
    """
    Extrai todos os códigos de procedimentos do PDF
    Retorna lista de dicionários com: codigo, nome, tipo, autor, revisao, data
    """
    procedimentos = []
    
    with open(pdf_path, 'rb') as pdf_file:
        reader = PyPDF2.PdfReader(pdf_file)
        total_paginas = len(reader.pages)
        
        print(f"📄 Processando {total_paginas} páginas...")
        
        for num_pagina in range(total_paginas):
            texto = reader.pages[num_pagina].extract_text()
            
            # Padrão para capturar:
            # Código (POP.xxx, DOC.xxx, etc.) + Nome + Tipo + Autor + Revisão + Data
            # Exemplo: POP.514 Control Diario DSPC Procedimento Operacional Padrão Rômulo Cursino 1 16/12/2019
            
            linhas = texto.split('\n')
            
            for i, linha in enumerate(linhas):
                # Procura por códigos de procedimento
                match_codigo = re.match(r'^(POP|DOC|FOR|TAB|IT|DEX|INS)\.(\d+)', linha.strip())
                
                if match_codigo:
                    codigo_completo = match_codigo.group(0)
                    tipo_doc = match_codigo.group(1)
                    numero = match_codigo.group(2)
                    
                    # Tenta extrair nome (próxima parte da linha ou próxima linha)
                    resto_linha = linha[match_codigo.end():].strip()
                    
                    # Tenta pegar o nome até encontrar palavras-chave de tipo
                    tipos_doc = [
                        'Procedimento Operacional Padrão',
                        'Procedimento Operacional',
                        'Documentos Externos',
                        'Documentos',
                        'Formulário',
                        'Tabela',
                        'Instrução'
                    ]
                    
                    nome = ""
                    tipo_classificacao = ""
                    
                    for tipo in tipos_doc:
                        if tipo in resto_linha:
                            partes = resto_linha.split(tipo)
                            nome = partes[0].strip()
                            tipo_classificacao = tipo
                            break
                    
                    if not nome and resto_linha:
                        # Se não encontrou tipo, pega até 80 caracteres
                        nome = resto_linha[:80].strip()
                        tipo_classificacao = "Documento"
                    
                    # Limpa caracteres especiais do nome
                    nome = re.sub(r'\s+', ' ', nome).strip()
                    
                    if nome:  # Só adiciona se encontrou um nome
                        procedimento = {
                            'codigo': codigo_completo,
                            'numero': numero,
                            'tipo': tipo_doc,
                            'nome': nome,
                            'classificacao': tipo_classificacao,
                            'pagina_pdf': num_pagina + 1
                        }
                        
                        procedimentos.append(procedimento)
                        print(f"  ✓ {codigo_completo}: {nome[:60]}...")
        
        print(f"\n✅ Total de {len(procedimentos)} procedimentos extraídos!")
        return procedimentos


def salvar_json(procedimentos, output_path):
    """Salva os procedimentos em formato JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(procedimentos, f, ensure_ascii=False, indent=2)
    print(f"💾 Arquivo salvo em: {output_path}")


def gerar_relatorio(procedimentos):
    """Gera relatório estatístico dos procedimentos"""
    print("\n" + "="*60)
    print("📊 RELATÓRIO DE PROCEDIMENTOS")
    print("="*60)
    
    # Contagem por tipo
    tipos_count = {}
    for proc in procedimentos:
        tipo = proc['tipo']
        tipos_count[tipo] = tipos_count.get(tipo, 0) + 1
    
    print("\n📌 Por Tipo de Documento:")
    for tipo, count in sorted(tipos_count.items()):
        print(f"   {tipo}: {count} documentos")
    
    # Contagem por classificação
    class_count = {}
    for proc in procedimentos:
        classe = proc.get('classificacao', 'Outros')
        class_count[classe] = class_count.get(classe, 0) + 1
    
    print("\n📁 Por Classificação:")
    for classe, count in sorted(class_count.items(), key=lambda x: -x[1]):
        print(f"   {classe}: {count} documentos")
    
    print(f"\n🔢 TOTAL GERAL: {len(procedimentos)} procedimentos")
    print("="*60)


if __name__ == "__main__":
    # Caminho do PDF
    pdf_path = r"C:\Users\Vinícius Mota\Downloads\document.pdf"
    
    # Caminho de saída
    output_json = r"C:\Users\Vinícius Mota\Documents\PYTHON\CalibraWeb\database\procedimentos_extraidos.json"
    
    print("🚀 Iniciando extração de procedimentos...\n")
    
    # Extrai procedimentos
    procedimentos = extrair_procedimentos_pdf(pdf_path)
    
    # Remove duplicatas baseado no código
    procedimentos_unicos = {}
    for proc in procedimentos:
        codigo = proc['codigo']
        if codigo not in procedimentos_unicos:
            procedimentos_unicos[codigo] = proc
    
    lista_final = list(procedimentos_unicos.values())
    lista_final.sort(key=lambda x: (x['tipo'], int(x['numero'])))
    
    print(f"\n🔍 Removidas {len(procedimentos) - len(lista_final)} duplicatas")
    
    # Salva JSON
    salvar_json(lista_final, output_json)
    
    # Gera relatório
    gerar_relatorio(lista_final)
    
    print("\n✨ Processo concluído!")
