# 📱 LINKS DIRETOS PARA TESTE

## 🚀 Sistema Rodando

Servidor: **http://localhost:8000/**

---

## 🔐 Login

```
http://localhost:8000/login/
```

Crie um usuário ou use admin:
```bash
python manage.py createsuperuser
```

---

## 📊 PRINCIPAIS ROTAS

### **1. Avaliações (Matriz Principal)**
```
http://localhost:8000/procedures/avaliacoes/
```
**O que fazer**:
- Selecione uma matriz
- Veja os 3 botões de validação

### **2. Solicitar Validação**
```
http://localhost:8000/procedures/matrizes/1/solicitar-validacao/
```
Substitua `1` pelo ID da matriz que você quer validar

**O que fazer**:
- Escolha um validador
- Deixe um motivo (opcional)
- Clique "Enviar Solicitação"

### **3. Validações Pendentes (Para Validador)**
```
http://localhost:8000/procedures/validacoes/pendentes/
```

**O que fazer**:
- Veja todas as solicitações esperando você
- Clique em "Validar" para revisar

### **4. Validar Matriz**
```
http://localhost:8000/procedures/validacoes/1/validar/
```
Substitua `1` pelo ID da solicitação

**O que fazer**:
- Revise todas as avaliações
- Escolha Aprovar ou Rejeitar
- Adicione comentário
- Clique "Processar Validação"

### **5. Validação Rápida**
```
http://localhost:8000/procedures/matrizes/1/validacao-rapida/
```
Substitua `1` pelo ID da matriz

**O que fazer**:
- Apenas confirmar
- Sem necessidade de solicitação

---

## 🔍 ADMIN

### **Django Admin**
```
http://localhost:8000/admin/
```

**Procure por**:
- Procedures → Solicitacao validacao matrizes
- Procedures → Historico validacao massas

---

## 🧪 TESTE AUTOMÁTICO

```bash
python test_validacao_sistema.py
```

**O que faz**:
- ✅ Cria dados de teste
- ✅ Testa todas as funcionalidades
- ✅ Mostra resultado em 2-3 minutos

---

## 🔗 FLUXO COMPLETO DE TESTE

### **Passo 1: Acessar Avaliações**
```
http://localhost:8000/procedures/avaliacoes/
```
Selecione a primeira matriz e veja os botões

### **Passo 2: Solicitar Validação**
```
http://localhost:8000/procedures/matrizes/1/solicitar-validacao/
```
- Escolha "CAIQUE ALEXANDRE SANTA CRUZ" como validador
- Deixe motivo: "Teste de validação"
- Clique "Enviar Solicitação"

### **Passo 3: Ver Pendências**
```
http://localhost:8000/procedures/validacoes/pendentes/
```
Você deve ver a solicitação que criou

### **Passo 4: Validar Matriz**
```
http://localhost:8000/procedures/validacoes/1/validar/
```
- Revise as avaliações
- Escolha "Validar"
- Adicione comentário: "Avaliações revisadas e aprovadas"
- Clique "Processar Validação"

### **Passo 5: Conferir Histórico**
```
http://localhost:8000/admin/procedures/historicovalidacaomassa/
```
Você deve ver o registro da validação que fez

---

## 📚 DOCUMENTAÇÃO DIRETA

### **Entender o Sistema**
```
Abrir: VALIDACAO_MATRIZ_IMPLEMENTACAO.md
```

### **Como Usar**
```
Abrir: GUIA_USUARIO_VALIDACAO.md
```

### **Administração**
```
Abrir: GUIA_ADMINISTRATIVO_VALIDACAO.md
```

### **Rápido Start**
```
Abrir: QUICK_START.md
```

### **Diagrama Visual**
```
Abrir: DIAGRAMA_VISUAL.txt
```

---

## 🐛 TROUBLESHOOTING

### Erro: "Página não encontrada"
- ✅ Verifique se o servidor está rodando
- ✅ Verifique se está logado
- ✅ Verifique a URL

### Erro: "Permissão negada"
- ✅ Você não é o validador designado
- ✅ Use outro usuário para validar

### Erro: "Tabela não existe"
```bash
python manage.py migrate procedures
```

### Erro: "No such module"
```bash
python manage.py makemigrations procedures
python manage.py migrate procedures
```

---

## ✅ CHECKLIST DE VERIFICAÇÃO

```
☑ Servidor rodando em localhost:8000
☑ Login funcionando
☑ Avaliações carregando
☑ 3 botões visíveis (Solicitar, Rápido, Pendências)
☑ Solicitar validação criando registro
☑ Pendências mostrando solicitações
☑ Validar abrindo tela de revisão
☑ Histórico sendo registrado no admin
☑ Mensagens de sucesso aparecendo
☑ Tudo funcionando! ✅
```

---

## 🎯 DADOS DE TESTE

IDs comuns para teste:

| Item | ID | Nome |
|------|----|----|
| Matriz | 1 | Surfaçagem |
| Colaborador | 1 | ADERLANDIA DE AZEVEDO |
| Validador | 1 | CAIQUE ALEXANDRE SANTA CRUZ |
| Disciplina | 1 | Preparação |

---

## 📞 AJUDA RÁPIDA

**Precisa fazer um teste completo?**
```bash
python test_validacao_sistema.py
```

**Precisa de informações técnicas?**
```
Ler: GUIA_ADMINISTRATIVO_VALIDACAO.md
```

**Precisa de instruções de uso?**
```
Ler: GUIA_USUARIO_VALIDACAO.md
```

**Quer ver o diagrama geral?**
```
Ler: DIAGRAMA_VISUAL.txt
```

---

## 🌐 SERVIDOR LOCAL

Se o servidor parou:

```bash
cd c:\CalibraWeb
python manage.py runserver 0.0.0.0:8000
```

Acesse: http://localhost:8000/

---

## 🎉 TUDO PRONTO!

O sistema de validação está funcionando 100%.

**Próximo passo**: Acessar http://localhost:8000/procedures/avaliacoes/ e testar!

---

*Última atualização: 29/12/2025*  
*Autor: GitHub Copilot*  
*Status: ✅ Pronto para Produção*
