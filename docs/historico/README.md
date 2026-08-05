# CalibraWEB

Sistema integrado de gestão metrológica, recursos humanos e procedimentos com suporte a calibração, treinamentos e certificação digital.

**Status**: ✅ Em Produção (Vercel + Neon)

## Início Rápido

### Local
```bash
git clone https://github.com/seu-usuario/CalibraWeb.git
cd CalibraWeb
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Acesse: http://localhost:8000

### Deploy na Vercel
```bash
git push origin main
# Vercel detecta mudanças e faz deploy automático
```

## 📚 Documentação

- **[Arquitetura](docs/arquitetura.md)** - Stack tecnológico, estrutura de apps
- **[Setup Local](docs/setup.md)** - Instalação completa com Celery/Redis
- **[Fluxos de Negócio](docs/fluxos.md)** - Processos e integrações

## 🏗️ Estrutura do Projeto

```
├── config/          # Configurações Django
├── core/            # App principal
├── metrologia/      # Calibração e instrumentos
├── rh/              # Recursos humanos
├── procedures/      # Procedimentos
├── training/        # Treinamentos
├── organization/    # Estrutura org.
├── shared/          # Utilitários
├── docs/            # 📖 Documentação
└── vercel.json      # Configuração de deploy
```

## 🛠️ Tech Stack

- **Backend**: Django 5.0
- **Banco**: Neon PostgreSQL (prod) / SQLite (dev)
- **Cache**: Redis
- **Fila**: Celery + Beat
- **Frontend**: Bootstrap 5
- **Servidor**: Gunicorn
- **Armazenamento**: AWS S3

## 📋 Requisitos

- Python 3.11+
- PostgreSQL 14+
- Redis 6+

## 🚀 Deploy em Produção

1. Configurar variáveis na Vercel:
   - `DATABASE_URL`
   - `REDIS_URL`
   - `SECRET_KEY`
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

2. Push para main:
   ```bash
   git push origin main
   ```

3. Vercel faz build automático via `vercel.json`

## 📝 Testes

```bash
pytest                          # Todos os testes
pytest --cov=core --cov=rh     # Com cobertura
```

## 🔒 Segurança

- Autenticação por sessão
- Permissões baseadas em roles
- CSRF protection
- SSL/TLS em produção
- Variáveis sensíveis em `.env` (não versionadas)

## 🤝 Contribuindo

1. Crie uma branch: `git checkout -b feature/nova-funcionalidade`
2. Commit: `git commit -m "feat: descrição"`
3. Push: `git push origin feature/nova-funcionalidade`
4. Abra um Pull Request

## ✅ Checklist Pré-Deploy

- [ ] Testes passando: `pytest`
- [ ] Linting ok: `flake8` e `black`
- [ ] Migrações criadas: `python manage.py makemigrations`
- [ ] Variáveis `.env` configuradas
- [ ] Cache/Redis testado
- [ ] Arquivo estático atualizado: `python manage.py collectstatic`

## 📞 Suporte

Para dúvidas sobre deploy ou troubleshooting, consulte [Fluxos de Negócio](docs/fluxos.md).

---

**Última atualização**: Junho 2026 | **Ambiente**: Vercel + Neon + Redis + S3
