from abc import ABC, abstractmethod

class CloudProvider(ABC):
    @abstractmethod
    async def upload_file(self, file_path, destination):
        pass

    @abstractmethod
    async def download_file(self, file_id, destination):
        pass
        
    @abstractmethod
    async def verify_connection(self):
        pass
        
    @abstractmethod
    async def refresh_token(self):
        pass
        
    @abstractmethod
    async def authenticate(self):
        pass 