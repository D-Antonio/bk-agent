# service_handler.py
import asyncio
import os
import sys
import logging
import signal
from multiprocessing import Process, freeze_support
import psutil
from service.process_manager import ProcessManager
from utils.logger import setup_logging

logger = logging.getLogger(__name__)

def run_async_function(func):
    """Función global para ejecutar código asíncrono"""
    asyncio.run(func())

class ServiceHandler:
    def __init__(self):
        self.process = None
        self.is_running = True
        self.process_manager = ProcessManager()
        setup_logging()
    
    def daemonize(self, func):
        """Inicia el proceso en segundo plano"""
        logging.info(f"Inicia el proceso en segundo plano")
        try:
            # Verificar si el proceso ya está en ejecución
            current_pid = self.process_manager.pid
            if current_pid and self.process_manager.is_pid_running(current_pid):
                logging.info(f"Ya existe un proceso con el PID {current_pid}, no se creará uno nuevo.")
                return current_pid
            
            self.process = self.process_manager.create_process(run_async_function, (func,), True) 
            
            #self.process.start()
            
            if self.process:
                new_pid = self.process.pid
                self.process_manager.save_pid(new_pid)
                self.is_running = True
                return new_pid
            
            return None
            
        except Exception as e:
            logging.error(f"Error al iniciar el servicio: {str(e)}")
            self.is_running = False
            return None

    def handle_signals(self):
        """Setup signal handlers"""
        logging.info(f"Setup signal handlers")
        signal.signal(signal.SIGTERM, self.handle_sigterm)

    def handle_sigterm(self, signo, frame):
        """Maneja la señal SIGTERM (terminación)"""
        logging.info("Recibida señal de terminación (SIGTERM). Cerrando el servicio...")
        self.process_manager.delete_pid()
        os._exit(0)