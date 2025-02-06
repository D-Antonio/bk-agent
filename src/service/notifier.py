import smtplib
import logging
from email.mime.text import MIMEText
from datetime import datetime
import socket
from typing import Dict

logger = logging.getLogger(__name__)

class Notifier:
    def __init__(self, email_config: Dict[str, str]):
        self.config = email_config

    def send_error_email(self, agent_id: str, error_message: str):
        """Sends error notification email"""
        try:
            msg = MIMEText(f"""
            Agent Connection Error Report
            
            Time: {datetime.now()}
            Agent ID: {agent_id}
            Host: {socket.gethostname()}
            Error: {error_message}
            
            The agent process will be terminated.
            """)

            msg['Subject'] = f'Agent Connection Error - {socket.gethostname()}'
            msg['From'] = self.config['sender_email']
            msg['To'] = self.config['receiver_email']

            with smtplib.SMTP(self.config['smtp_server'], self.config['smtp_port']) as server:
                server.starttls()
                server.login(self.config['sender_email'], self.config['password'])
                server.send_message(msg)
                logging.info("Error notification email sent successfully")
                
        except Exception as e:
            logging.error(f"Failed to send error email: {e}")