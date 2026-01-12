# 🚀 GUIA RÁPIDO - EXPORTAÇÃO DE MATRIZES

## ⚡ Comece Já!

### 1️⃣ Acesse a Tela
```
http://127.0.0.1:8000/procedures/matrizes/
```

### 2️⃣ Clique em "Exportar"
Botão amarelo na barra superior

### 3️⃣ Escolha o Formato
- **CSV** → Arquivo leve, compatível com Python/análise
- **Excel** → Arquivo formatado, professional

### 4️⃣ Pronto!
Arquivo baixa automaticamente em Downloads

---

## 📊 Formatos

### CSV
```
Matriz Código|Matriz Nome|...|Colaborador Nome|...
MAT001|Operação|...|João Silva|...
MAT001|Operação|...|Maria Santos|...
```
✅ Abrir em: Excel, Google Sheets, Python Pandas, Editor Texto

### Excel
```
[Spreadsheet formatado]
├─ Cabeçalho azul
├─ Dados organizados
├─ Borders em tudo
└─ Primeira linha congelada
```
✅ Abrir em: Excel, Google Sheets, LibreOffice

---

## 🎯 Casos de Uso

| Caso | Formato | Como |
|------|---------|------|
| Análise Python | CSV | Exportar → CSV → `pd.read_csv()` |
| Apresentação | Excel | Exportar → Excel → Abrir em Excel |
| Backup | Ambos | Salvar em pasta segura |
| Compartilhamento | Excel | Enviar por email |
| Integração | CSV | Processar em script |

---

## 🐛 Erro? Isso é Raro!

| Erro | Solução |
|------|---------|
| Botão não aparece | Limpar cache (Ctrl+Shift+R) |
| Não baixa | Desbloquear pop-ups no navegador |
| Arquivo vazio | Criar matriz de teste |
| Não abre em Excel | Usar Google Sheets (online) |
| Caracteres estranhos | Abrir em UTF-8 no Excel |

👉 Ver [TROUBLESHOOTING](./TROUBLESHOOTING_EXPORTACAO_MATRIZES.md) para mais

---

## 💡 Dica Pro

Se está testando e não tem dados:

1. Acesse: `/procedures/matrizes/importacao/`
2. Download template CSV
3. Use arquivo de teste: `template_teste_importacao.csv`
4. Faça import (3 matrizes, 7 disciplinas, 4 colaboradores)
5. Volta e exporta!

---

## 📞 Precisa de Mais?

- [Guia Completo](./EXPORTACAO_MATRIZES_GUIA_COMPLETO.md) - Tudo sobre exportação
- [Troubleshooting](./TROUBLESHOOTING_EXPORTACAO_MATRIZES.md) - Problemas e soluções
- [Status Técnico](./STATUS_EXPORTACAO_MATRIZES.md) - Detalhes de implementação

---

**✅ Sistema pronto! Comece a exportar agora!**
