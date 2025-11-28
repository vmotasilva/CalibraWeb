
import pandas as pd
import os

# Caminhos relativos ao diretório atual
BASE_DIR = os.getcwd()
ARQUIVO_ENTRADA = os.path.join(BASE_DIR, 'procedimentos_export (1).csv')
ARQUIVO_SAIDA = os.path.join(BASE_DIR, 'procedimentos_para_importar.csv')

# Ordem e nomes das colunas do template
colunas_template = [
    'no', 'codigo', 'nome', 'descricao', 'pasta', 'classificacao', 'autor',
    'numero_revisao', 'ultima_revisao', 'data_aprovacao', 'proxima_revisao',
    'data_validade', 'documentos_controlados', 'matriz', 'sub_area'
]

# Mapeamento de nomes do export para o template
mapa_colunas = {
    'CODIGO': 'codigo',
    'NOME': 'nome',
    'CLASSIFICACAO': 'classificacao',
    'NUMERO_REVISAO': 'numero_revisao',
    'ULTIMA_REVISAO': 'ultima_revisao',
    'DATA_APROVACAO': 'data_aprovacao',PS D:\Usuarios\ADM\Documents\Python\Calibra> python manage.py runserver
Watching for file changes with StatReloader
Performing system checks...

Exception in thread django-main-thread:
Traceback (most recent call last):
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\threading.py", line 1052, in _bootstrap_inner
    self.run()
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\threading.py", line 989, in run
    self._target(*self._args, **self._kwargs)
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\utils\autoreload.py", line 64, in wrapper
    fn(*args, **kwargs)
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\core\management\commands\runserver.py", line 133, in inner_run
    self.check(display_num_errors=True)
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\core\management\base.py", line 486, in check
    all_issues = checks.run_checks(
                 ^^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\core\checks\registry.py", line 88, in run_checks
    new_errors = check(app_configs=app_configs, databases=databases)
                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\core\checks\urls.py", line 14, in check_url_config
    return check_resolver(resolver)
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\core\checks\urls.py", line 24, in check_resolver
    return check_method()
           ^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\urls\resolvers.py", line 519, in check
    for pattern in self.url_patterns:
                   ^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\utils\functional.py", line 47, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
                                         ^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\urls\resolvers.py", line 738, in url_patterns
    patterns = getattr(self.urlconf_module, "urlpatterns", self.urlconf_module)
                       ^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\utils\functional.py", line 47, in __get__
    res = instance.__dict__[self.name] = self.func(instance)
                                         ^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\site-packages\django\urls\resolvers.py", line 731, in urlconf_module
    return import_module(self.urlconf_name)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "C:\Users\ADM\AppData\Local\Programs\Python\Python312\Lib\importlib\__init__.py", line 90, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1381, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1354, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1325, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 929, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 994, in exec_module
  File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
  File "D:\Usuarios\ADM\Documents\Python\Calibra\calibra\urls.py", line 34, in <module>
    from calibra.views_site import (
  File "D:\Usuarios\ADM\Documents\Python\Calibra\calibra\views_site.py", line 555, in <module>
    @require_POST
     ^^^^^^^^^^^^
NameError: name 'require_POST' is not defined

    'PROXIMA_REVISAO': 'proxima_revisao',
    'DATA_VALIDADE': 'data_validade',
    'PASTA': 'pasta',
    'AUTOR': 'autor',
    'DOCUMENTOS_CONTROLADOS': 'documentos_controlados',
    'MATRIZ': 'matriz',
    'SUB_AREA': 'sub_area',
}

def adaptar_csv():
    # Lê o CSV exportado
    df = pd.read_csv(ARQUIVO_ENTRADA, sep=';', dtype=str)
    # Renomeia as colunas
    df = df.rename(columns=mapa_colunas)
    # Adiciona coluna descricao vazia
    df['descricao'] = ''
    # Adiciona coluna no sequencial
    df['no'] = range(1, len(df) + 1)
    # Garante que todas as colunas do template existem
    for col in colunas_template:
        if col not in df.columns:
            df[col] = ''
    # Reordena as colunas
    df = df[colunas_template]
    # Salva o novo CSV
    df.to_csv(ARQUIVO_SAIDA, sep=';', index=False)
    print(f'Arquivo adaptado salvo como: {ARQUIVO_SAIDA}')

if __name__ == '__main__':
    adaptar_csv()
