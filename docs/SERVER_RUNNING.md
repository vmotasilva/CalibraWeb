# SERVIDOR RODANDO - TESTE PRONTO

## Status: ✓ ONLINE

Django server está rodando em: **http://127.0.0.1:8000/**

---

## Login Admin

```
URL:      http://127.0.0.1:8000/admin/
Username: admin
Password: admin123
```

---

## Para PARAR o servidor:
Pressione `CTRL+BREAK` no terminal

---

## Para REINICIAR o servidor:
```bash
python manage.py runserver --settings=config.settings_local 8000
```

---

## Próximos Testes:

### 1. Verify Login Works
- Abra http://127.0.0.1:8000/admin/
- Entre com admin/admin123
- Explore o dashboard

### 2. Run Tests
```bash
python manage.py test qms --settings=config.settings_test -v 2
```

### 3. Check Cache
- Monitore cache hits/misses em tempo real
- Verifique invalidação automática

---

## Troubleshooting

**Porta 8000 em uso?**
```bash
python manage.py runserver 8001
```

**Precisa resetar senha?**
```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> u = User.objects.get(username='admin')
>>> u.set_password('novaSenha123')
>>> u.save()
```

---

**Server Started:** 10:52 UTC
**Settings:** config.settings_local (in-memory cache)
