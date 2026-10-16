"""Resume a cobertura de testes por app a partir de um coverage.xml.

Uso: python scripts/cobertura_por_app.py coverage.xml
"""
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict


def main(caminho):
    raiz = ET.parse(caminho).getroot()
    linhas = defaultdict(lambda: [0, 0])  # app -> [linhas, cobertas]
    for classe in raiz.iter("class"):
        arquivo = classe.get("filename", "")
        app = arquivo.split("/")[0] if "/" in arquivo else "(raiz)"
        for linha in classe.iter("line"):
            linhas[app][0] += 1
            if int(linha.get("hits", "0")) > 0:
                linhas[app][1] += 1

    total = sum(v[0] for v in linhas.values())
    cobertas = sum(v[1] for v in linhas.values())
    saida = ["| App | Linhas | Cobertas | Cobertura |", "| :-- | --: | --: | --: |"]
    for app, (n, c) in sorted(linhas.items(), key=lambda kv: -kv[1][1] / max(kv[1][0], 1)):
        saida.append(f"| {app} | {n} | {c} | {100 * c / n:.1f}% |")
    saida.append(f"| **Total** | {total} | {cobertas} | {100 * cobertas / max(total, 1):.1f}% |")
    print("\n".join(saida))


if __name__ == "__main__":
    main(sys.argv[1])
