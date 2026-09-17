"""Configuracao compartilhada da sessao WAHA, sem expor credenciais."""
import json


def session_name(root):
    path = root / 'runtime/waha/session.json'
    if not path.exists():
        return 'default'
    value = json.loads(path.read_text(encoding='utf-8'))['name']
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        raise ValueError('Nome da sessao WAHA invalido.')
    return value
