import logging
import json
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
import uuid
from fastapi import Request
import time
from app.config import settings

# Configure root logger
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

class StructuredLogger:
    """
    Structured logger that outputs JSON logs
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.request_id = None
    
    def _log(self, level: int, message: str, **kwargs):
        """
        Log a message with structured data
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": logging.getLevelName(level),
            "message": message,
            "service": settings.APP_NAME,
            "environment": settings.ENVIRONMENT,
        }
        
        # Add request ID if available
        if self.request_id:
            log_data["request_id"] = self.request_id
        
        # Add additional context
        if kwargs:
            log_data.update(kwargs)
        
        # Handle exceptions
        if "exc_info" in kwargs and kwargs["exc_info"]:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            if exc_type and exc_value:
                log_data["exception"] = {
                    "type": exc_type.__name__,
                    "message": str(exc_value),
                    "traceback": traceback.format_exception(exc_type, exc_value, exc_traceback)
                }
        
        # Log as JSON
        self.logger.log(level, json.dumps(log_data))
    
    def debug(self, message: str, **kwargs):
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        self._log(logging.CRITICAL, message, **kwargs)
    
    def set_request_id(self, request_id: str):
        """Set request ID for correlation"""
        self.request_id = request_id

# Create logger instance
logger = StructuredLogger("app")

async def logging_middleware(request: Request, call_next):
    """
    Middleware for request logging and timing
    """
    # Generate unique request ID
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Set request ID in logger
    logger.set_request_id(request_id)
    
    # Log request
    start_time = time.time()
    
    # Extract request details
    method = request.method
    url = str(request.url)
    client_ip = request.client.host
    user_agent = request.headers.get("User-Agent", "")
    
    logger.info(
        f"Request started: {method} {url}",
        method=method,
        url=url,
        client_ip=client_ip,
        user_agent=user_agent
    )
    
    # Process request
    try:
        response = await call_next(request)
        
        # Calculate request duration
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            f"Request completed: {method} {url}",
            method=method,
            url=url,
            status_code=response.status_code,
            duration=process_time
        )
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
    except Exception as e:
        # Log exception
        process_time = time.time() - start_time
        logger.error(
            f"Request failed: {method} {url}",
            method=method,
            url=url,
            duration=process_time,
            exc_info=True
        )
        raise
