# CHANGELOG - CalibraWeb

Todas as alterações importantes do CalibraWeb são documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/) e usa [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [Unreleased]

### 🔄 Em Desenvolvimento
Alterações que ainda não foram lançadas em uma versão oficial.

---

## [1.0.0] - 2026-08-19

### ✨ Adicionado
- Sistema integrado de gestão metrológica (CalibraWeb)
- Módulo de Calibração e Instrumentos (metrologia)
- Módulo de Recursos Humanos (rh)
- Módulo de Procedimentos, Treinamentos e Cotações (procedures)
- Dashboard principal com estatísticas
- Autenticação de usuários com roles e permissões
- Integração com AWS S3 para armazenamento de arquivos
- Sistema de cache com Redis
- Processamento assíncrono com Celery
- Deploy automático na Vercel
- Banco de dados PostgreSQL (Neon)

### 🎨 Interface
- Design responsivo com Bootstrap 5
- Templates reutilizáveis
- Sistema de navegação intuitivo

### 🔧 Infraestrutura
- Configuração para Vercel + Neon + Redis
- Variáveis de ambiente seguras
- Arquivo vercel.json para CI/CD automático

### 🧪 Qualidade
- Testes iniciais com pytest
- Linting com flake8 e black
- Checklist pré-deploy

---

## Guia de Uso

### Para Desenvolvedores

Ao fazer alterações no projeto, siga estes passos:

1. **Edite este arquivo** antes de fazer o commit
2. **Adicione sua mudança** na seção correspondente:
   - `✨ Adicionado` - para novas funcionalidades
   - `🔄 Alterado` - para mudanças em funcionalidades existentes
   - `🐛 Corrigido` - para bugs corrigidos
   - `🗑️ Removido` - para funcionalidades removidas
   - `⚠️ Descontinuado` - para funcionalidades que serão removidas
   - `🔒 Segurança` - para correções de segurança

3. **Use versionamento semântico**:
   - **MAJOR** (ex: 2.0.0) - mudanças incompatíveis
   - **MINOR** (ex: 1.1.0) - novas funcionalidades compatíveis
   - **PATCH** (ex: 1.0.1) - correções de bugs

4. **Exemplo de entrada**:
   ```markdown
   ### ✨ Adicionado
   - Nova funcionalidade X que faz Y
   - Integração com serviço Z
   
   ### 🐛 Corrigido
   - Erro ao salvar dados em procedimentos
   - Validação de formulário em treinamentos
   ```

### Para Usuários Finais

Verifique o CHANGELOG para ver:
- Quando novas funcionalidades estarão disponíveis
- O que foi corrigido na última versão
- O que mudou que possa afetar seu uso do sistema

---

## Versão Atual
- **Última Atualização**: 19 de Agosto de 2026
- **Versão**: 1.0.0
- **Status**: ✅ Em Produção

---

## Links Relacionados
- 🌐 [CalibraWeb Online](https://calibra-web.vercel.app)
- 📚 [Documentação](docs/README.md)
- 🐛 [Issues & Bugs](https://github.com/vmotasilva/CalibraWeb/issues)
- 🔀 [Pull Requests](https://github.com/vmotasilva/CalibraWeb/pulls)
