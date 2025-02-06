import os
import sys
import json
import logging
import asyncio
from pathlib import Path

# Change to relative imports
from utils.logger import setup_logging
from service.service_handler import ServiceHandler
from encryption.encryption_handler import EncryptionHandler
from backup.backup_manager import BackupManager
from ui.console_interface import ConsoleInterface
from service.agent import Agent
from utils.file_handler import FileHandler

def load_config():
    """Load configuration from config.json file."""
    config_path = FileHandler.get_paht('config.json')
    try:
        logging.info(f"load_config {config_path}")
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        FileNotFoundError(f"Configuration file not found at {config_path}")
        logging.error(f"Configuration file not found at {config_path}")
    except json.JSONDecodeError:
        ValueError("Invalid JSON in configuration file")
        logging.error("Invalid JSON in configuration file")

async def main():
    setup_logging()
    
    try:
        config = load_config()
        
        logging.info(f"Config {config}")

        encryption_handler = EncryptionHandler(config['encryption']['key'])
        
        # Initialize backup_manager
        backup_manager = BackupManager(
            encryption_handler=encryption_handler,
            config=config
        )

        service_handler = ServiceHandler()

        agent = Agent(backup_manager, config['email'], config['server'], service_handler)
        
        # Initialize and run console interface
        console = ConsoleInterface(agent)
        await console.run()
        
    except Exception as e:
        logging.error(f"Application error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 