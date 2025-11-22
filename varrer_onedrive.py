import os
import pandas as pd
from datetime import datetime

# --- CONFIGURAÇÃO ---
# O caminho da sua pasta (Use r antes das aspas para o Windows aceitar as barras)
CAMINHO_RAIZ = r"D:\OneDrive\OneDrive - Luxottica Group S.p.A\Tecnolens\Calibração e Verificação - Equipamentos de Medição\Certificados de Calibração"

def varrer_pastas():
    print(f"Iniciando varredura em: {CAMINHO_RAIZ}")
    
    dados = []
    
    # Caminha por todas as pastas e subpastas
    for pasta_atual, subpastas, arquivos in os.walk(CAMINHO_RAIZ):
        for arquivo in arquivos:
            # Só queremos PDFs ou Imagens
            if arquivo.lower().endswith(('.pdf', '.jpg', '.png', '.jpeg')):
                caminho_completo = os.path.join(pasta_atual, arquivo)
                
                # LÓGICA DE DETECÇÃO INTELIGENTE
                caminho_str = caminho_completo.upper()
                
                # 1. Tenta descobrir se é RBC pelo nome da pasta
                is_rbc = "NÃO" # Padrão
                tipo = "RASTREADO"
                
                if "RBC" in caminho_str or "ACREDITADO" in caminho_str:
                    is_rbc = "SIM"
                    tipo = "RBC"
                
                # 2. Tenta descobrir o Número do Certificado (Pega o nome do arquivo sem extensão)
                nome_sem_ext = os.path.splitext(arquivo)[0]
                
                # Tenta limpar nomes comuns (ex: "Certificado 1234" vira "1234")
                n_cert = nome_sem_ext.replace("Certificado", "").replace("Calibração", "").strip()
                
                dados.append({
                    "NOME_ARQUIVO": arquivo,
                    "PROVAVEL_CERTIFICADO": n_cert,
                    "PASTA_PAI": os.path.basename(pasta_atual),
                    "TEM_SELO_RBC": is_rbc,
                    "TIPO_DETECTADO": tipo,
                    "CAMINHO_COMPLETO": caminho_completo
                })

    # Gera o Excel
    if dados:
        df = pd.DataFrame(dados)
        nome_saida = "Mapeamento_OneDrive.xlsx"
        df.to_excel(nome_saida, index=False)
        print(f"\nSUCESSO! Encontrados {len(dados)} arquivos.")
        print(f"Arquivo gerado: {nome_saida}")
        print("Agora abra esse arquivo, copie as colunas e cole no template de importação do sistema.")
    else:
        print("Nenhum arquivo encontrado. Verifique o caminho.")

if __name__ == "__main__":
    varrer_pastas()