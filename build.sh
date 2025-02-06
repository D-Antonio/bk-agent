#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt
echo "Building application..."
python -m nuitka --standalone --enable-plugin=multiprocessing --include-package=websockets --include-package=websockets.legacy --include-package=websockets.extensions --include-package=websockets.sync --follow-imports --include-package=src --include-data-files=src/config.json=config.json --no-pyi-file --remove-output --assume-yes-for-downloads --output-dir=dist src/main.py
echo "Build complete!"