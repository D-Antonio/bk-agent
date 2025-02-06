import logging
import asyncio
import websockets
import ssl
import json
from typing import Dict, Any
from utils.logger import setup_logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.MAX_RETRIES = 10
        self.RETRY_DELAY = 30
        self.connection_attempts = 0
        self.ws = None
        self.is_active = False
        self.is_enable = True
        setup_logging()

    async def connect_with_retry(self, agent_id: str, providers_status: Dict, agent_info_callback, command_handler):
        """Attempts to connect to WebSocket with retry logic"""
        while self.connection_attempts < self.MAX_RETRIES:
            try:
                self.connection_attempts += 1
                logger.info(f"Connection attempt {self.connection_attempts} of {self.MAX_RETRIES}")
                
                await self.connect_websocket(agent_id, providers_status, agent_info_callback, command_handler)
                self.connection_attempts = 0  # Reset counter on successful connection
                return True
                
            except Exception as e:
                logger.error(f"Connection attempt {self.connection_attempts} failed: {e}")
                self.is_active = False
                if self.connection_attempts >= self.MAX_RETRIES:
                    self.is_enable = False
                    return False
                
                logger.info(f"Waiting {self.RETRY_DELAY} seconds before next attempt...")
                await asyncio.sleep(self.RETRY_DELAY)

    async def connect_websocket(self, agent_id: str, providers_status: Dict, agent_info_callback, command_handler):
        """Establishes WebSocket connection with the server"""
        ws_url = f"wss://{self.config['host']}/ws?connectionId={agent_id}"
        logger.info(f"Attempting to connect to WebSocket at: {ws_url}")
        
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE  # Solo para desarrollo

        try:
            self.ws = await websockets.connect(ws_url, ssl=ssl_context)
            self.is_active = True
            logger.info("WebSocket connection established successfully")
            
            await agent_info_callback(self.ws, providers_status)
            await self.listen_for_commands(command_handler)
            
        except Exception as e:
            self.is_active = False
            logger.error(f"WebSocket connection error: {e}")
            raise

    async def listen_for_commands(self, command_handler):
        """Listens for incoming WebSocket commands"""
        try:
            logger.info("Starting command listener...")
            async for message in self.ws:
                try:
                    command_data = json.loads(message)
                    logger.info(f"Processing command: {command_data}")
                    await command_handler(command_data)
                except json.JSONDecodeError:
                    logger.error("Received invalid JSON message")
                    # await self.send_response({
                    #     'status': 'error',
                    #     'message': 'Invalid JSON format'
                    # })
                    
        except websockets.exceptions.ConnectionClosed as e:
            self.is_active = False
            logger.error(f"WebSocket connection closed: {e}")

        except Exception as e:
            logger.error(f"Error in command listener: {e}")
            raise

    async def send_response(self, response_data: Dict):
        """Sends a response through the WebSocket"""
        try:
            await self.ws.send(json.dumps(response_data))
            logger.info(f"Send data to API: {response_data}")
        except Exception as e:
            logger.error(f"Error sending response: {e}")