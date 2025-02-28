# Requisitos Previos

Antes de comenzar con la configuración y despliegue del agente, asegúrate de tener instalado lo siguiente:

- [Python](https://www.python.org/) (versión 3.x o superior)
- [pip](https://pip.pypa.io/) (gestor de paquetes de Python)
- [Nuitka](https://nuitka.net/) (para compilar el proyecto)

# Configuración

## 1. Clonar el Repositorio

Primero, clona el repositorio en tu máquina local:

```bash
git clone https://github.com/D-Antonio/bk-agent.git
cd bk-agent
```
## 2. Instalar Dependencias

Instala las dependencias necesarias utilizando `pip`:

```bash
pip install -r requirements.txt
```
## 3. Configurar el Proyecto

Asegúrate de que el archivo de configuración `src/config.json` esté correctamente configurado según tus necesidades. Este archivo contiene las configuraciones específicas del agente.
# Compilación

Para compilar el proyecto, utiliza el siguiente comando:

```bash
python -m nuitka --standalone --enable-plugin=multiprocessing --include-package=websockets --include-package=websockets.legacy --include-package=websockets.extensions --include-package=websockets.sync --follow-imports --include-package=src --include-data-files=src/config.json=config.json --no-pyi-file --remove-output --assume-yes-for-downloads --output-dir=dist src/main.py
```
Este comando generará una versión compilada del proyecto en la carpeta `dist`.
# Ejecución

## Ejecución Directa

Para ejecutar el agente directamente desde el código fuente, utiliza el siguiente comando:

```bash
python src/main.py
```
