from dataclasses import dataclass
import yaml
from pathlib import Path

@dataclass
class BackupConfig:
    compression: bool
    retention_days: int
    backup_folder: str
    exclude_patterns: list[str]

class ConfigLoader:
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = Path(config_path)

    def load_config(self) -> BackupConfig:
        if not self.config_path.exists():
            FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config_data = yaml.safe_load(f)
            
        backup_config = config_data.get('backup', {})
        return BackupConfig(
            compression=backup_config.get('compression', True),
            retention_days=backup_config.get('retention_days', 30),
            backup_folder=backup_config.get('backup_folder', 'backups'),
            exclude_patterns=backup_config.get('exclude_patterns', [])
        ) 