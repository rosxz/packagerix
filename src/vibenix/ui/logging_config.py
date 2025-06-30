from loguru import logger
import sys
from collections import deque
from threading import Lock

# Configure loguru
logger.remove()  # Remove default handler

# Create a custom handler that stores logs in memory for the UI
class LogCapture:
    def __init__(self, max_logs=1000):
        self.logs = deque(maxlen=max_logs)
        self.lock = Lock()
        
    def write(self, message):
        with self.lock:
            self.logs.append(message.rstrip())
            
    def get_logs(self):
        with self.lock:
            return list(self.logs)
            
    def clear(self):
        with self.lock:
            self.logs.clear()

# Global log capture instance
log_capture = LogCapture()

# Only add the capture handler for UI
# Console handler will be added conditionally by the main app
logger.add(log_capture.write, format="{time:HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}", level="DEBUG")

# Function to enable console logging (for non-UI mode)
def enable_console_logging():
    logger.add(sys.stderr, format="{time:HH:mm:ss} | {level} | {message}", level="INFO")

# Export logger for use in other modules
__all__ = ['logger', 'log_capture', 'enable_console_logging']