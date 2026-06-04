"""
OntoDerive 配置系统
==================
支持 ontoderive.yaml 配置文件，合并链：defaults → project config → CLI args → env vars。
"""

import os
from pathlib import Path

DEFAULTS = {
    "toolforge_mode": "keyword",  # keyword | tfidf | hybrid
    "toolforge_top_n": 5,
    "check_thresholds": {
        "assertion_traceability": 0.30,
        "falsifiability": 0.15,
    },
    "derive_iterations": 3,
    "output_formats": ["json", "markdown"],
    "watch_interval": 5,
}


def _load_yaml(path):
    try:
        import yaml

        with open(path) as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        # 无 yaml 库时尝试 JSON
        import json

        try:
            return json.loads(open(path).read())
        except Exception:
            return {}
    except Exception:
        return {}


def _deep_merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = _deep_merge(base[k].copy(), v)
        else:
            base[k] = v
    return base


class Config:
    def __init__(self, project_root=None, cli_args=None):
        self._cfg = DEFAULTS.copy()
        self._cfg["project_root"] = project_root

        # 1. 项目级配置文件 ontoderive.yaml
        if project_root:
            config_path = Path(project_root) / "ontoderive.yaml"
            if not config_path.exists():
                config_path = Path(project_root) / "ontoderive.json"
            if config_path.exists():
                project_cfg = _load_yaml(config_path)
                self._cfg = _deep_merge(self._cfg, project_cfg)

        # 2. CLI 参数覆盖
        if cli_args:
            cli_dict = {k: v for k, v in vars(cli_args).items() if v is not None and v is not False}
            self._cfg = _deep_merge(self._cfg, cli_dict)

        # 3. 环境变量覆盖 (ONTO_ 前缀)
        for key in ["ONTO_TOOLFORGE_MODE", "ONTO_TOOLFORGE_TOP_N", "ONTO_DERIVE_ITERATIONS"]:
            env_val = os.environ.get(key)
            if env_val is not None:
                config_key = key.lower().replace("onto_", "")
                try:
                    env_val = int(env_val)
                except ValueError:
                    pass
                self._cfg[config_key] = env_val

    def get(self, key, default=None):
        return self._cfg.get(key, default)

    def __getitem__(self, key):
        return self._cfg[key]

    def __contains__(self, key):
        return key in self._cfg

    def to_dict(self):
        return self._cfg.copy()
