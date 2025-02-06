import os
import sys
import shutil
from pathlib import Path
import logging
from typing import List
import fnmatch

logger = logging.getLogger(__name__)

# Add the root directory to PYTHONPATH
ROOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)
sys.path.append(str(Path(__file__).resolve().parent.parent))

class FileHandler:
    @staticmethod
    def get_paht(path: str) -> str:
        return os.path.join(ROOT_DIR, path)

    @staticmethod
    def create_directory(path: str) -> bool:
        """Create directory if it doesn't exist"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logging.error(f"Failed to create directory {path}: {e}")
            return False

    @staticmethod
    def get_files_to_backup(source_path: str, exclude_patterns: List[str] = None) -> List[Path]:
        """Get list of files to backup, excluding patterns"""
        if exclude_patterns is None:
            exclude_patterns = []

        files = []
        try:
            source_path = Path(source_path)
            for item in source_path.rglob("*"):
                if item.is_file():
                    # Check if file matches any exclude pattern
                    if not any(fnmatch.fnmatch(str(item), pattern) for pattern in exclude_patterns):
                        files.append(item)
        except Exception as e:
            logging.error(f"Error scanning directory {source_path}: {e}")
            

        return files

    @staticmethod
    def compress_directory(source_path: str, output_path: str) -> str:
        """Compress directory into zip file"""
        try:
            return shutil.make_archive(output_path, 'zip', source_path)
        except Exception as e:
            logging.error(f"Failed to compress directory {source_path}: {e}")
            

    @staticmethod
    def extract_archive(archive_path: str, extract_path: str):
        """Extract compressed archive"""
        try:
            shutil.unpack_archive(archive_path, extract_path)
        except Exception as e:
            logging.error(f"Failed to extract archive {archive_path}: {e}")
            