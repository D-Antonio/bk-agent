import os
import sys
import asyncio
import logging

from utils.logger import setup_logging
from service.agent import Agent
from cloud.cloud_factory import CloudFactory

logger = logging.getLogger(__name__)

class ConsoleInterface:
    def __init__(self, agent: Agent):
        self.agent = agent
        self.cloud_factory = CloudFactory()
        self.providers_status = None


    async def connect_websocket(self):
        """Interface to connect to WebSocket server"""
        try:
            setup_logging()
            #print("\nConectando al servidor WebSocket...")
            if self.agent:
                await self.agent.start(self.providers_status)
                # Esperar indefinidamente mientras se mantiene la conexión
                while True:
                    await asyncio.sleep(1)
            else:
                print("Error: Agent no inicializado")
        except Exception as e:
            logging.error(f"Error connecting to WebSocket: {e}")
            print(f"Error de conexión: {e}")

    async def check_providers_status(self):
        """Check status of all cloud providers"""
        providers_status = {}
        available_providers = self.cloud_factory.get_available_providers()
        
        print("\nVerificando estado de proveedores de nube...")
        for provider_id, provider_name in available_providers.items():
            try:
                credentials = self.agent.backup_manager.config.get(provider_id, {})
                is_active = await self.cloud_factory.check_provider_status(provider_id, credentials)
                providers_status[provider_id] = {
                    "name": provider_name,
                    "active": is_active
                }
            except Exception as e:
                providers_status[provider_id] = {
                    "name": provider_name,
                    "active": False
                }
        
        return providers_status
    
    def limpiar_terminal(self):
        """Limpia la terminal dependiendo del sistema operativo."""
        sistema = os.name  # 'posix' para Linux/Mac, 'nt' para Windows
        if sistema == 'posix':
            os.system('clear')  # Comando para limpiar en sistemas tipo Unix (Linux, macOS)
        elif sistema == 'nt':
            os.system('cls')  # Comando para limpiar en Windows

    async def display_providers_menu(self):
        """Display and handle provider authentication menu"""
        continue_app = False
        while True:

            if not continue_app:
                providers_status = await self.check_providers_status()
            else:
                continue_app = False

            print(f"\nAgent ID: {self.agent.agent_id}")
            
            
            print("\nEstado de Proveedores de Nube:")
            for provider_id, info in providers_status.items():
                status = "✓ Activo" if info["active"] else "✗ Inactivo"
                print(f"{info['name']}: {status}")
            
            self.providers_status = providers_status

            print("\nEstado del Servicio de Backups: ")
            if self.agent.service_handler.process_manager.pid:
                if self.agent.service_handler.process_manager.is_pid_running(self.agent.service_handler.process_manager.pid):
                    print(f"El servicio está en ejecución (PID: {self.agent.service_handler.process_manager.pid})")
                else:
                    self.agent.service_handler.process_manager.kill_process(
                        pid=self.agent.service_handler.process_manager.pid
                    )
                    print("El servicio no está en ejecución")
            else:
                print("No se ha iniciado ningún servicio")
            
            print("\nOpciones:")
            print("1. Activar proveedor")
            print("2. Iniciar Servicio de Backups")
            print("3. Detener Servicio de Backups")
            print("4. Salir")
            
            choice = input("\nSeleccione una opción (1-4): ")

            if choice == "1":
                self.limpiar_terminal()

                print("\nSeleccione el proveedor a activar:")
                inactive_providers = {pid: info for pid, info in providers_status.items() 
                                   if not info["active"]}
                
                if not inactive_providers:
                    print("No hay proveedores inactivos para activar.")
                    continue_app = True
                    continue
                
                for i, (provider_id, info) in enumerate(inactive_providers.items(), 1):
                    print(f"{i}. {info['name']}")
                
                provider_choice = input("\nIngrese el número del proveedor: ")
                try:
                    provider_index = int(provider_choice) - 1
                    provider_id = list(inactive_providers.keys())[provider_index]
                    await self.agent.backup_manager.set_cloud_provider(provider_id)
                    print(f"\n{providers_status[provider_id]['name']} activado exitosamente!")
                except (ValueError, IndexError):
                    print("\nOpción inválida.")
                    continue_app = True
                except Exception as e:
                    continue_app = True
                    print(f"\nError al activar proveedor: {e}")

            elif choice == "2":
                self.limpiar_terminal()

                active_providers = [p for p, info in providers_status.items() if info["active"]]
                if not active_providers:
                    print("\n⚠️ Advertencia: No hay proveedores activos. Se recomienda activar al menos uno.")
                    if input("¿Desea continuar de todos modos? (s/n): ").lower() != 's':
                        continue_app = True
                        continue

                if self.agent.service_handler.process_manager.pid:
                    if self.agent.service_handler.process_manager.is_pid_running(self.agent.service_handler.process_manager.pid):
                        print("\n⚠️ Advertencia: Ya existe un servicio en segundo plano en ejecución.")
                        if input("¿Desea continuar de todos modos? (s/n): ").lower() != 's':
                            print(f"El servicio está en ejecución (PID: {self.agent.service_handler.process_manager.pid})")
                            continue_app = True
                            continue
                        else:
                            self.agent.service_handler.process_manager.kill_process(
                                pid=self.agent.service_handler.process_manager.pid
                            )

                print("\nIniciando daemon...")

                current_pid = self.agent.service_handler.daemonize(self.connect_websocket)
                if current_pid:
                    print(f"Servicio iniciado con PID: {current_pid}")
                else:
                    print("Error al iniciar el servicio")
                continue_app = True
                continue

            elif choice == "3":
                self.limpiar_terminal()

                if self.agent.service_handler.process_manager.pid:
                    if self.agent.service_handler.process_manager.is_pid_running(self.agent.service_handler.process_manager.pid):
                        print("\n⚠️ ¡Advertencia! Estás a punto de detener el servicio en segundo plano. ")
                        if input("¿Desea continuar de todos modos? (s/n): ").lower() == 's':
                            self.agent.service_handler.process_manager.kill_process(
                                pid=self.agent.service_handler.process_manager.pid
                            )
                    else:
                        print("El servicio no está en ejecución")
                continue_app = True
                continue

            elif choice == "4":
                self.limpiar_terminal()
                print("\n¡Gracias por usar la aplicación!")
                os._exit(0)

            else:
                continue_app = True
                print("\nOpción inválida. Por favor, intente nuevamente.")
                

    async def run(self):
        """Run the main console interface"""
        await self.display_providers_menu()
        