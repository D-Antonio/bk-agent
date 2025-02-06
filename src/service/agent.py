import asyncio
import os
import sys
import json
import logging
import platform
import socket
import uuid
from typing import Dict, Any, TypedDict, Optional
import signal
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from backup.backup_manager import BackupManager
from service.service_handler import ServiceHandler
from service.connection_manager import ConnectionManager
from service.notifier import Notifier
from service.process_manager import ProcessManager
#from backup.backup_manifest import DatabaseHandler
from data.database_handler import DatabaseHandler
from data.database_operations import DatabaseOperations
from utils.file_handler import FileHandler
from utils.logger import setup_logging

class BackupTask(TypedDict):
    id: int
    source_path: str
    encrypt: bool
    frequency: str
    provider: str
    backup_limit: int
    agent_id: str
    start_date: str
    is_active: bool
    is_directory: bool
    last_run: Optional[str]

class Agent:
    def __init__(self, backup_manager: BackupManager, email_config: Dict[str, str], server_config: Dict[str, str], service_handler: ServiceHandler):
        self.agent_id = self.load_or_create_agent_id()
        self.backup_manager = backup_manager
        self.connection_manager = ConnectionManager(server_config)
        self.notifier = Notifier(email_config)
        self.service_handler = service_handler
        self.db_operations = DatabaseOperations()  # Instancia de DatabaseOperations
        setup_logging()
        
    def load_or_create_agent_id(self) -> str:
        """Loads existing GUID or creates a new one"""
        logging.info(f"Loads existing GUID or creates a new one") # Borrar
        id_file = FileHandler.get_paht("agent_id.txt") # os.path.join(ROOT_DIR, "agent_id.txt")
        
        try:
            if os.path.exists(id_file):
                with open(id_file, 'r') as f:
                    agent_id = f.read().strip()
                    uuid.UUID(agent_id)  # Validate GUID
                    return agent_id
        except (ValueError, IOError) as e:
            logging.error(f"Error loading agent ID: {e}")
        
        new_id = str(uuid.uuid4())
        try:
            with open(id_file, 'w') as f:
                f.write(new_id)
        except IOError as e:
            logging.error(f"Error saving agent ID: {e}")
        
        return new_id

    async def start(self, providers_status: Dict):
        """Starts the client service"""
        # Inicializar el servicio en segundo plano
        #print("Iniciando servicio del cliente...")
        logging.info("Iniciando servicio del cliente...")
        
        # Create task for checking daily backups
        asyncio.create_task(self.check_daily_tasks())
        
        try:
            while self.service_handler.is_running:
                connected = await self.connection_manager.connect_with_retry(
                    self.agent_id,
                    providers_status,
                    self.send_agent_info,
                    self.handle_command
                )
                
                if not connected:
                    error_message = f"Failed to connect after {self.connection_manager.MAX_RETRIES} attempts"
                    try:
                        self.notifier.send_error_email(self.agent_id, error_message)
                    except Exception as e:
                        logging.error(f"Error en el servicio: {e}")

                    self.service_handler.process_manager.kill_process(
                        pid=self.service_handler.process_manager.pid
                    )
                    break
                
                await asyncio.sleep(1)  # Pequeña pausa para no consumir CPU

        except KeyboardInterrupt:
            print("\nServicio terminado por el usuario")
            logging.info("Servicio terminado por el usuario")
        except Exception as e:
            print(f"Error en el servicio: {e}")
            logging.error(f"Error en el servicio: {e}")
        finally:
            logging.warning(f"Start in finally") # Borrar
            self.service_handler.process_manager.kill_process(
                pid=self.service_handler.process_manager.pid
            )

    async def send_agent_info(self, ws, providers_status: Dict):
        """Sends agent information to the server"""
        available_providers = []
        
        for provider_id, provider_info in providers_status.items():
            available_providers.append({
                "providers": provider_id,
                "name": provider_info.get("name", ""),
                "active": provider_info.get("active", False)
            })

        await self.connection_manager.send_response(
            {
                "command": "info",
                "parameters": {
                    "agentId": self.agent_id,
                    "name": socket.gethostname(),
                    "ipAddress": socket.gethostbyname(socket.gethostname()),
                    "osType": sys.platform,
                    "status": "online",
                    "hostname": socket.gethostname(),
                    "platform": {
                        "system": platform.system(),
                        "release": platform.release(),
                        "version": platform.version(),
                        "machine": platform.machine(),
                        "processor": platform.processor()
                    },
                    "availableProviders": available_providers
                },
                "agentId": self.agent_id
            }
        )

        logging.info("Agent info sent successfully")

    async def handle_command(self, command_data: Dict):
        """Handles commands received through WebSocket"""
        try:
            command = command_data.get('command')
            parameters = command_data.get('parameters', {})

            if command == "New_Task":
                await self.handle_new_task(parameters)
            elif command == "Delete_Backup":
                await self.handle_delete_backup(parameters)
            elif command == "Delete_Task":
                await self.handle_delete_task(parameters)
            elif command == "Restore_Backup":
                await self.handle_restore_backup(parameters)
            # Handle other commands...
            
            # await self.connection_manager.send_response({
            #     'command': 'success',
            #     'parameters': command
            # })
                
        except Exception as e:
            logging.error(f"Error handling command: {e}")
            # await self.connection_manager.send_response({
            #     'command': 'error',
            #     'parameters': {'command': command_data.get('command'), 'message': str(e)}
            # })

    async def handle_new_task(self, parameters: Dict):
        try:
            source_path = Path(parameters['SourcePath'].strip())
            if not source_path.exists():
                raise FileNotFoundError(f"Source path not found: {source_path}")

            start_date = datetime.fromisoformat(parameters['StartDate'].replace('Z', '+00:00'))
            last_run = None
            if parameters.get('LastRun'):
                last_run = datetime.fromisoformat(parameters['LastRun'].replace('Z', '+00:00'))

            data = {
                'id': parameters['BackupTaskId'],
                'source_path': parameters['SourcePath'].strip(),
                'encrypt': parameters['Encrypt'],
                'frequency': parameters['Frequency'].lower(),
                'provider': parameters['Provider'],
                'backup_limit': parameters['BackupLimit'],
                'agent_id': parameters['AgentId'],
                'start_date': start_date.isoformat(),
                'is_active': parameters['IsActive'],
                'is_directory': source_path.is_dir(),
                'last_run': last_run.isoformat() if last_run else None
            }
            
            self.db_operations.add_backup_task(data)
            
            backup_result = await self._execute_backup_task(data, datetime.now())
            
            await self.connection_manager.send_response({
                'command': 'Backup_History',
                'parameters': {
                   'backup_results': [backup_result]
                },
                "agentId": self.agent_id
            })

        except Exception as e:
            await self.connection_manager.send_response({
                'command': 'Delete_Task',
                'parameters': {'BackupTaskId':parameters['BackupTaskId']},
                "agentId": self.agent_id
            })
            logging.error(f"Error creating new task: {e}")
            raise

    async def send_result(self, backup_results):
        while not self.connection_manager.is_active:
            await self.connection_manager.send_response({
                'command': 'Backup_History',
                'parameters': {
                    'backup_results': backup_results
                },
                "agentId": self.agent_id
            })
            await asyncio.sleep(30)
        return 0

    async def check_daily_tasks(self):
        while True:
            try:
                if not self.connection_manager.is_enable:
                    return 0
                
                current_date = datetime.now()
                logging.info(current_date)
                tasks = self.db_operations.fetch_daily_tasks(current_date)

                backup_results = []

                logging.info(f"BackupTask: {tasks}")

                for task in tasks:
                    task_dict: BackupManager = {
                        'id': task[0],
                        'source_path': task[1],
                        'encrypt': task[2],
                        'frequency': task[3],
                        'provider': task[4],
                        'backup_limit': task[5],
                        'agent_id': task[6],
                        'start_date': task[7],
                        'is_active': task[8],
                        'last_run': task[9]
                    }
                    
                    backup_history = self.db_operations.get_backup_history(task_dict['id'])                 
                    
                    if len(backup_history) >= task_dict['backup_limit']:
                        # Delete oldest backups to maintain the limit
                        for backup in backup_history[:len(backup_history) - task_dict['backup_limit'] + 1]:
                            backup_id = backup[0]
                            await self.handle_delete_backup({'backupId': backup_id})
                    
                    result = await self._execute_backup_task(task_dict, current_date)
                    if result:
                        backup_results.append(result)
                    
                # Send results through WebSocket if there were any backups
                if len(backup_results) > 0:
                    asyncio.create_task(self.send_result(backup_results))
                
                # Sleep until next day
                tomorrow = (current_date + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                sleep_seconds = (tomorrow - current_date).total_seconds()
                next_check = current_date + timedelta(seconds=sleep_seconds)
                logging.info(f"Próxima verificación de tareas programada para: {next_check.strftime("%Y-%m-%dT%H:%M:%SZ")}")
                
                await asyncio.sleep(sleep_seconds)
                
            except Exception as e:
                logging.error(f"Error checking daily tasks: {e}")
                await asyncio.sleep(3600)  # Retry in 1 hour if there's an error

    async def _execute_backup_task(self, task_dict: BackupTask, current_date: datetime) -> Dict | None:
        """Execute a single backup task and return the result"""
        try:
            
            await self.backup_manager.set_cloud_provider(task_dict['provider'])
            backup_id = await self.backup_manager.create_backup(
                task_dict['source_path'],
                encrypt=task_dict['encrypt']
            )
            
            try:
                start_date = datetime.fromisoformat(task_dict['start_date'])
            except ValueError:
                cleaned_date = task_dict['start_date'].split('.')[0]
                start_date = datetime.fromisoformat(cleaned_date)
                
            next_run = self.calculate_next_run(task_dict['frequency'], start_date)
            current_date_str = current_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            next_run_str = next_run.strftime("%Y-%m-%dT%H:%M:%SZ")
            
            self.db_operations.update_backup_task(task_dict['id'], current_date_str, next_run_str)
            self.db_operations.record_backup_history(task_dict['id'], backup_id, Path(task_dict['source_path']).name, current_date_str)
            
            return {
                'task_id': task_dict['id'],
                'backup_id': backup_id,
                'original_name': Path(task_dict['source_path']).name,
                'timestamp': current_date_str,
                'status': 'completed'
            }
                
        except Exception as e:
            logging.error(f"Error executing backup task {task_dict['id']}: {e}")
            return None

    def calculate_next_run(self, frequency: str, current_date: datetime) -> datetime:
        if frequency == 'daily':
            return current_date + timedelta(days=1)
        elif frequency == 'weekly':
            return current_date + timedelta(weeks=1)
        elif frequency == 'monthly':
            if current_date.month == 12:
                year = current_date.year + 1
                month = 1
            else:
                year = current_date.year
                month = current_date.month + 1
                
            try:
                return current_date.replace(year=year, month=month)
            except ValueError:
                if month == 12:
                    next_month = datetime(year + 1, 1, 1)
                else:
                    next_month = datetime(year, month + 1, 1)
                return next_month - timedelta(days=1)
                
        elif frequency == 'yearly':
            return current_date.replace(year=current_date.year + 1)
        return current_date

    async def handle_delete_backup(self, parameters: Dict):
        try:
            backup_info = self.db_operations.get_backup_info(parameters['backupId'])
            
            if backup_info:

                await self.backup_manager.delete_backup(parameters['backupId'], backup_info[2])
                self.db_operations.delete_backup(parameters['backupId'])
                
                logging.info(f"Backup {parameters['backupId']} deleted successfully")
            else: 
                logging.error(f"Backup {parameters['backupId']} no found")
            
            await self.connection_manager.send_response({
                'command': 'Delete_Backup',
                'parameters': {'BackupId': parameters['backupId']},
                "agentId": self.agent_id
            })
        except Exception as e:
            logging.error(f"Error deleting backup: {e}")
            raise

    async def handle_delete_task(self, parameters: Dict):
        try:
            backups = self.db_operations.get_backup_history(parameters['backupTaskId'])
            
            logging.info(f"delete_backup {backups}")
            if backups:
                for backup in backups:
                    await self.handle_delete_backup({'backupId': backup[0]})
            
            self.db_operations.delete_task(parameters['backupTaskId'])
            logging.info(f"Task {parameters['backupTaskId']} and its backups deleted successfully")

            await self.connection_manager.send_response({
                'command': 'Delete_Task',
                'parameters': {'BackupTaskId': parameters['backupTaskId']},
                "agentId": self.agent_id
            })

        except Exception as e:
            logging.error(f"Error deleting task: {e}")
            raise

    async def handle_restore_backup(self, parameters: Dict):
        try:
            backup_info = self.db_operations.get_backup_info(parameters['backupId'])
            logging.info(f"backup_info: {backup_info}")
            await self.backup_manager.restore_backup({
                'source_path': backup_info[0],
                'is_directory':backup_info[1],
                'provider': backup_info[2],
                'is_encrypted': backup_info[3],
                'timestamp': backup_info[4],
                'original_name': backup_info[5],
                'backup_id': parameters['backupId'],
                })
            
            await self.connection_manager.send_response({
                'command': 'Restore_Backup',
                'parameters': {'BackupId': parameters['backupId']},
                "agentId": self.agent_id
            })
            logging.info(f"Backup {parameters['backupId']} restored successfully to {backup_info[0]}")
            
        except Exception as e:
            logging.error(f"Error restoring backup: {e}")
            raise
