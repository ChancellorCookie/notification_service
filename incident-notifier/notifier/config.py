"""Konfiguration laden (YAML) mit Umgebungsvariablen-Substitution.

Geheimnisse (Tokens, Passwoerter) gehoeren NICHT in die YAML-Datei,
sondern als ${VAR} referenziert und ueber eine EnvironmentFile in systemd
gesetzt (siehe README).
"""
import os
import re
import yaml

_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _sub_env(value):
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _sub_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sub_env(v) for v in value]
    return value


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return _sub_env(raw or {})


def get_by_path(data, path: str):
    """Folgt einem gepunkteten Pfad ('data.incidents') in verschachtelten dicts."""
    if not path:
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur
