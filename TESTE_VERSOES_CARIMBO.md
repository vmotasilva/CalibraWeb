# Testando Duas Versões do Sistema de Carimbo

## 📋 Resumo

Criei **duas versões** do template para você testar:

### Versão Original
- **Arquivo**: `metrologia/templates/metrologia/editar_historico.html`
- **Status**: COM OFFSET CONHECIDO
- **Problema**: Preview mostra carimbo em lugar X, mas apply coloca em lugar Y

### Versão Simplificada  
- **Arquivo**: `metrologia/templates/metrologia/editar_historico_simplificado.html`
- **Status**: TESTE (objetivo: eliminar offset)
- **Abordagem**: Coordenadas PDF direto, sem conversões intermediárias

---

## 🚀 Como Testar

### Passo 1: Testar Versão Original (Baseline)

1. Certifique-se de que está rodando: `python manage.py runserver`

2. Abra o histórico 127:
   ```
   http://127.0.0.1:8000/metrologia/historico/127/editar/
   ```

3. **Teste o carimbo:**
   - Preencha os campos (Resultado, Data, Validador)
   - Clique em uma posição no PDF (anote a posição)
   - Observe o PREVIEW (retângulo cinza mostra onde vai)
   - Clique em "Aplicar Carimbo"
   - Baixe o PDF carimbado e verifique ONDE ficou o carimbo

4. **Resultado esperado (versão original):**
   - Preview mostra X, mas carimbo aparece offset (geralmente mais alto)

### Passo 2: Testar Versão Simplificada

Para usar a versão simplificada, você tem duas opções:

#### Opção A: Mudar temporariamente na view

1. Abra `qms/views.py` (linha ~420)

2. Encontre a função `editar_historico_calibracao`:

```python
def editar_historico_calibracao(request, id):
    # ... código existente ...
    
    # TEMPORÁRIA PARA TESTE: usar versão simplificada
    use_simplified = request.GET.get('use_simplified', 'false').lower() == 'true'
    
    return render(request, 
        'metrologia/editar_historico_simplificado.html' if use_simplified else 'metrologia/editar_historico.html',
        context)
```

3. Acesse a URL com parâmetro:
   ```
   http://127.0.0.1:8000/metrologia/historico/127/editar/?use_simplified=true
   ```

#### Opção B: Trocar permanentemente (para desenvolvedor)

1. Abra `qms/views.py` e mude:
   ```python
   return render(request, 'metrologia/editar_historico_simplificado.html', context)
   ```

2. Depois reverta quando terminar o teste

### Passo 3: Comparar Resultados

Use **a mesma posição** de clique nos **dois testes**:

| Métrica | Versão Original | Versão Simplificada |
|---------|-----------------|---------------------|
| X predito | ??? | ??? |
| Y predito | ??? | ??? |
| X aplicado | ??? | ??? |
| Y aplicado | ??? | ??? |
| Offset X | ??? | ??? |
| Offset Y | ??? | ??? |

---

## 🔍 Diferenças Técnicas

### Versão Original (Complexa)
```
Click em tela (px, py)
    ↓
Canvas rect (screen size)
    ↓
Scale = canvas_pixels / canvas_rect
    ↓
Canvas pixels (canvas_px, canvas_py)
    ↓
PDF coords (canvas_px / canvas_width * pdf_width)
    ↓
Y inversion (pdf_height - pdf_y)
    ↓
Boundedcoords (Math.max/min)
    ↓
Enviar ao backend
    ↓
Backend: rescale se dimensions diferem
    ↓
Draw no PyPDF com Y já invertido
```

**Pontos de falha possíveis**: 5+ conversões, scale factors, inversions duplas

---

### Versão Simplificada (Limpa)
```
Click em tela (px, py)
    ↓
Canvas rect (screen size)
    ↓
Scale = canvas_pixels / canvas_rect
    ↓
Canvas pixels (canvas_px, canvas_py)
    ↓
PDF coords (canvas_px / canvas_width * pdf_width)
    ↓
Y inversion (pdf_height - pdf_y) - UMA VEZ SÓ
    ↓
Bounded coords
    ↓
Enviar ao backend
    ↓
Backend: sem rescale (usa dimensions do próprio PDF)
    ↓
Draw no PyPDF com coordenadas já corretas
```

**Melhorias**: Menos passos, sem conversões redundantes

---

## 📊 Console Logs

Ambas as versões imprimem no console do navegador:

**Versão Original** (linhas 750-835):
```javascript
console.log('DEBUG: Click at screen=' + clickX + ',' + clickY);
console.log('DEBUG: PDF coords (after flip)=' + pdfXCorrect + ',' + pdfYCorrect);
console.log('=== PREVIEW DRAWING ===');
console.log('PREVIEW WILL DRAW AT: x=' + displayX + ', y=' + displayY);
```

**Versão Simplificada** (linhas 220-280):
```javascript
console.log('=== VERSÃO SIMPLIFICADA ===');
console.log('1. Click em coordenadas de tela:', clickScreenX, clickScreenY);
console.log('2. Canvas rect size:', canvasRect.width, 'x', canvasRect.height);
// ... mais steps ...
console.log('9. Coordenadas finais (bounded):', finalX, finalY);
```

**Como visualizar**: Abra `F12` → Aba Console → Role até encontrar os logs

---

## 🎯 O Que Procurar

### Offset Original
Se clicar em (450, 300) e:
- Preview mostra em (450, 300) ✓
- Carimbo aplicado aparece em (450, 250) ✗
- Então tem offset de ~50px em Y

### Versão Simplificada Funciona Se:
- Mesma posição de clique
- Preview em (450, 300)
- Carimbo aplicado também em (450, 300) ✓

---

## 💡 Próximas Etapas

### Se Simplificada Funciona:
1. Deletar arquivo `editar_historico.html`
2. Renomear `editar_historico_simplificado.html` → `editar_historico.html`
3. Testar com múltiplos certificados
4. Deploy

### Se Simplificada Também Tem Offset:
1. Problema provavelmente está no **backend**
2. Verificar `qms/views.py` linhas 420-475
3. Checar se `carimbo_pdf_width` e `carimbo_pdf_height` são usados corretamente

### Se Simplificada é Pior:
1. Reverter para original
2. Investigar método alternativo:
   - Usar `PDF.js` annotation system
   - Ou usar `PyPDF` diretamente sem ReportLab overlay

---

## 📝 Arquivo de Teste Script

```bash
python test_stamp_versions.py
```

Mostra:
- Comparação das duas versões
- Cálculo matemático de coordenadas
- URLs de teste prontas

---

## ⚠️ Checklist de Teste

- [ ] Versão Original: clique em 5 posições diferentes
- [ ] Anotar offset (se houver) em cada posição
- [ ] Versão Simplificada: testar mesmas 5 posições
- [ ] Comparar offsets
- [ ] Testar com zoom in/out em ambas
- [ ] Testar múltiplas páginas (se PDF tiver > 1 página)
- [ ] Documentar achados

---

## 🆘 Se Algo Quebrar

```bash
# Voltar para original
git checkout metrologia/templates/metrologia/editar_historico.html

# Ou trocar a view de volta
# qms/views.py linha ~420:
return render(request, 'metrologia/editar_historico.html', context)
```

---

## 📞 Dúvidas?

Coordenadas PDF:
- Y=0 na **BASE** (diferente de canvas)
- X aumenta para direita
- Y aumenta para cima

Conversão passo a passo nos console logs de ambas versões.
