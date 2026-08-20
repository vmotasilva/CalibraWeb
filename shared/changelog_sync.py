"""
Parser e sincronizador de CHANGELOG.md para changelog.json
Converte o CHANGELOG.md em um JSON estruturado para exibição web.
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


class ChangelogParser:
    """Parse CHANGELOG.md seguindo o formato Keep a Changelog"""

    def __init__(self, changelog_path: str = None):
        """
        Inicializa o parser com o caminho do CHANGELOG.md

        Args:
            changelog_path: Caminho para o CHANGELOG.md. Se None, busca na raiz do projeto.
        """
        if changelog_path is None:
            from django.conf import settings
            changelog_path = Path(settings.BASE_DIR) / "CHANGELOG.md"

        self.changelog_path = Path(changelog_path)
        self.content = self._read_file()

    def _read_file(self) -> str:
        """Lê o arquivo CHANGELOG.md"""
        if not self.changelog_path.exists():
            raise FileNotFoundError(f"CHANGELOG.md não encontrado em {self.changelog_path}")
        
        with open(self.changelog_path, 'r', encoding='utf-8') as f:
            return f.read()

    def parse(self) -> List[Dict[str, Any]]:
        """
        Faz parse do CHANGELOG.md e retorna lista de versões

        Returns:
            Lista de dicionários com versão, data e mudanças
        """
        entries = []

        # Padrão: ## [1.0.0] - 2026-08-19
        version_pattern = r"^## \[(.+?)\] - (.+?)$"
        # Padrão: ### ✨ Adicionado
        category_pattern = r"^### (.+?)$"
        # Padrão: - Item da lista
        item_pattern = r"^- (.+?)$"

        lines = self.content.split('\n')
        current_version = None
        current_date = None
        current_category = None
        current_changes = []

        for i, line in enumerate(lines):
            # Verifica versão
            version_match = re.match(version_pattern, line)
            if version_match:
                # Salva versão anterior se existir
                if current_version and current_changes:
                    entries.append({
                        "version": current_version,
                        "date": current_date,
                        "changes": current_changes
                    })

                current_version = version_match.group(1)
                current_date = version_match.group(2)
                current_changes = []
                continue

            # Se estamos em uma versão, processa itens
            if current_version:
                category_match = re.match(category_pattern, line)
                if category_match:
                    current_category = category_match.group(1)
                    continue

                item_match = re.match(item_pattern, line)
                if item_match:
                    item_text = item_match.group(1).strip()
                    
                    # Limpa emoji e emojis de categoria se houver
                    # Ex: "✨ Adicionado" → remove
                    if current_category:
                        current_changes.append(item_text)

        # Salva última versão
        if current_version and current_changes:
            entries.append({
                "version": current_version,
                "date": current_date,
                "changes": current_changes
            })

        return entries

    def sync_to_json(self, output_path: str = None) -> str:
        """
        Sincroniza CHANGELOG.md para changelog.json

        Args:
            output_path: Caminho para salvar changelog.json. Se None, usa BASE_DIR/changelog.json

        Returns:
            Caminho do arquivo gerado
        """
        if output_path is None:
            from django.conf import settings
            output_path = Path(settings.BASE_DIR) / "changelog.json"

        entries = self.parse()

        # Escreve JSON com formatação legível
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)

        return str(output_path)


def sync_changelog():
    """
    Função utilitária para sincronizar CHANGELOG.md → changelog.json
    Pode ser chamada de views, commands ou hooks
    """
    try:
        parser = ChangelogParser()
        output_file = parser.sync_to_json()
        return {
            "success": True,
            "message": f"Changelog sincronizado com sucesso para {output_file}",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }


if __name__ == "__main__":
    # Pode ser executado diretamente como script
    result = sync_changelog()
    print(json.dumps(result, ensure_ascii=False, indent=2))
