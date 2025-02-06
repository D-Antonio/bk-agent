import os
import sys
import signal
import logging
import psutil
from multiprocessing import Process, current_process
from utils.logger import setup_logging
from utils.file_handler import FileHandler

logger = logging.getLogger(__name__)

class ProcessManager:
    def __init__(self, pid_file: str = 'client_service.pid'):
        self.pid_file = FileHandler.get_paht(pid_file) 
        self.pid = self.load_pid()
        setup_logging()

    @staticmethod
    def create_process(target_func, args=None, daemon=False):
        """Creates and starts a new process"""
        logging.info(f"Creates and starts a new process") # Borrar
        try:
            current_process().name = "BackgroundServiceWorker"
            process = Process(target=target_func, args=args or (), daemon=daemon)
            process.start()
            return process
        except Exception as e:
            logging.error(f"Error creating process: {str(e)}")
            return None

    def load_pid(self) -> int | None:
        """Loads PID from file if it exists"""
        if os.path.exists(self.pid_file):
            with open(self.pid_file, "r") as x:
                saved_pid = int(x.read().strip())
            logging.info(f"PID recuperado: {saved_pid}")
            return saved_pid
        else:
            logging.info(f"El archivo {self.pid_file} no existe.")
            return None

    def save_pid(self, pid: int) -> None:
        """Saves PID to file"""
        try:
            with open(self.pid_file, "w") as x:
                x.write(str(pid))
            self.pid = pid
            logging.info(f"PID guardado en {self.pid_file}")
        except Exception as e:
            logging.error(f"Error al guardar PID: {str(e)}")

    def delete_pid(self) -> None:
        """Deletes the PID file if exists"""
        self.pid = None

        if os.path.exists(self.pid_file):
            os.remove(self.pid_file)
            logging.info(f"Archivo de PID {self.pid_file} eliminado.")

        else:
            logging.info(f"El archivo {self.pid_file} no existe para eliminarlo.")

    @staticmethod
    def is_pid_running(pid: int) -> bool:
        """Checks if a process with given PID is running"""
        logging.info(f"Checks if a process with given PID is running") # Borrar
        try:
            if not pid:
                return False
            process = psutil.Process(pid)
            return process.is_running()
        except psutil.NoSuchProcess:
            return False

    def kill_process(self, pid: int) -> bool:
        """Kills a process by PID"""
        try:
            logging.info(f"Intentando matar el proceso con PID: {pid}")
            proceso = psutil.Process(pid)
            if os.name == 'nt':
                proceso.terminate()
                try:
                    proceso.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proceso.kill()
            else:
                proceso.kill()
            
            logging.info(f"Proceso con PID {pid} terminado exitosamente")
            self.delete_pid()
            return True
        except psutil.NoSuchProcess:
            logging.error(f"No se encontró el proceso con PID {pid}")
            self.delete_pid()
            return False
        except Exception as e:
            logging.error(f"Error al matar el proceso {pid}: {str(e)}")
            return False

    @staticmethod
    def setup_signal_handlers(callback):
        """Sets up signal handlers"""
        signal.signal(signal.SIGTERM, callback)

    @staticmethod
    def terminate_process():
        """Terminates the current process"""
        sys.exit(0)