"""
Sistema simplificado de permissões baseado em módulos.
Define grupos de permissões para cada módulo da aplicação.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

# Definição dos módulos e suas permissões
MODULES_PERMISSIONS = {
    'metrologia': {
        'name': 'Metrologia - Calibração de Instrumentos',
        'permissions': [
            'add_instrumento',
            'change_instrumento',
            'delete_instrumento',
            'view_instrumento',
            'add_historicocalibracao',
            'change_historicocalibracao',
            'delete_historicocalibracao',
            'view_historicocalibracao',
            'add_solicitacaocotacao',
            'change_solicitacaocotacao',
            'delete_solicitacaocotacao',
            'view_solicitacaocotacao',
        ]
    },
    'rh': {
        'name': 'Recursos Humanos',
        'permissions': [
            'add_colaborador',
            'change_colaborador',
            'delete_colaborador',
            'view_colaborador',
            'add_ocorrencia',
            'change_ocorrencia',
            'delete_ocorrencia',
            'view_ocorrencia',
        ]
    },
    'procurements': {
        'name': 'Procurement / Compras',
        'permissions': [
            'add_solicitacaoinstrumento',
            'change_solicitacaoinstrumento',
            'delete_solicitacaoinstrumento',
            'view_solicitacaoinstrumento',
        ]
    },
    'organization': {
        'name': 'Organização',
        'permissions': [
            'add_setor',
            'change_setor',
            'delete_setor',
            'view_setor',
        ]
    },
    'auditoria': {
        'name': 'Auditoria',
        'permissions': [
            'add_modeloauditoria',
            'change_modeloauditoria',
            'delete_modeloauditoria',
            'view_modeloauditoria',
            'add_perguntaauditoria',
            'change_perguntaauditoria',
            'delete_perguntaauditoria',
            'view_perguntaauditoria',
            'add_registroauditoria',
            'change_registroauditoria',
            'delete_registroauditoria',
            'view_registroauditoria',
            'add_respostaauditoria',
            'change_respostaauditoria',
            'delete_respostaauditoria',
            'view_respostaauditoria',
        ]
    },
    'insumos': {
        'name': 'Insumos',
        'permissions': [
            'add_modeloauditoria',
            'change_modeloauditoria',
            'delete_modeloauditoria',
            'view_modeloauditoria',
            'add_perguntaauditoria',
            'change_perguntaauditoria',
            'delete_perguntaauditoria',
            'view_perguntaauditoria',
            'add_registroauditoria',
            'change_registroauditoria',
            'delete_registroauditoria',
            'view_registroauditoria',
            'add_respostaauditoria',
            'change_respostaauditoria',
            'delete_respostaauditoria',
            'view_respostaauditoria',
        ]
    },
    'procedures': {
        'name': 'Procedimentos / Treinamentos',
        'permissions': []
    },
    'fornecedores': {
        'name': 'Fornecedores',
        'permissions': []
    },
    'acoes': {
        'name': 'Ações Corretivas',
        'permissions': []
    },
}

def setup_module_groups():
    """
    Cria grupos de permissões para cada módulo.
    Execute esto com: python manage.py shell < setup_permissions.py
    ou via comando customizado: python manage.py setup_module_groups
    """
    for module_key, module_info in MODULES_PERMISSIONS.items():
        group, created = Group.objects.get_or_create(name=module_info['name'])
        
        # Limpar permissões antigas
        group.permissions.clear()
        
        # Adicionar novas permissões
        for perm_codename in module_info['permissions']:
            try:
                # Tentar obter a permissão
                app_label, permission = perm_codename.split('_', 1)
                perm = Permission.objects.get(
                    content_type__app_label=module_key,
                    codename=perm_codename
                )
                group.permissions.add(perm)
            except (Permission.DoesNotExist, ValueError):
                print(f"⚠️  Permissão não encontrada: {module_key}.{perm_codename}")
        
        status = "✓ Criado" if created else "✓ Atualizado"
        print(f"{status}: Grupo '{group.name}' com {group.permissions.count()} permissões")

def get_module_key(view_module):
    """
    Extrai o módulo (chave) a partir do caminho do módulo da view.
    Ex: 'metrologia.views.novo_fluxo_cotacao' -> 'metrologia'
    """
    return view_module.split('.')[0] if '.' in view_module else view_module

def has_module_access(user, module_key):
    """
    Verifica se um usuário tem acesso a um módulo.
    Returns: Boolean
    """
    if user.is_superuser or user.is_staff:
        return True
    
    module_info = MODULES_PERMISSIONS.get(module_key)
    if not module_info:
        return False
    
    try:
        group = Group.objects.get(name=module_info['name'])
    except Group.DoesNotExist:
        return False

    return user.groups.filter(id=group.id).exists()
