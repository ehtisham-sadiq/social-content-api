from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings
import time
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True,  # Verify connections before using them
    echo=settings.DB_ECHO_SQL,  # Log SQL queries in development
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class
Base = declarative_base()

# Dependency to get DB session with retry logic
def get_db():
    db = SessionLocal()
    retries = 0
    max_retries = 3
    retry_delay = 0.5  # seconds
    
    while retries < max_retries:
        try:
            yield db
            break
        except Exception as e:
            retries += 1
            if retries >= max_retries:
                logger.error(f"Failed to connect to database after {max_retries} attempts: {str(e)}")
                raise
            logger.warning(f"Database connection error (attempt {retries}/{max_retries}): {str(e)}")
            time.sleep(retry_delay * (2 ** (retries - 1)))  # Exponential backoff
        finally:
            db.close()
