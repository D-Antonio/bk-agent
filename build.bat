@echo off
echo Instalando dependencias...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo Compilando aplicacion...

python -m nuitka --standalone --enable-plugin=multiprocessing --include-package=websockets --include-package=websockets.legacy --include-package=websockets.extensions --include-package=websockets.sync --follow-imports --include-package=src --include-data-files=src/config.json=config.json --no-pyi-file --remove-output --assume-yes-for-downloads --output-dir=dist src/main.py

if errorlevel 1 (
    echo Error durante la compilacion
    pause
    exit /b 1
)

echo.
echo Compilacion completada!
echo Presione cualquier tecla para salir...
pause
