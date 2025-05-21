from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
import time
import asyncio
from contextlib import asynccontextmanager

from app.database import get_db, engine
from app import models, schemas, crud, auth
from app.config import settings
from app.logger import logger, logging_middleware
from middleware.rate_limit import rate_limit_middleware
from app.cache import Cache

# Create database tables
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if they don't exist
    logger.info("Creating database tables if they don't exist")
    models.Base.metadata.create_all(bind=engine)
    
    # Initialize cache
    if settings.REDIS_ENABLED:
        if Cache.is_available():
            logger.info("Redis cache is available")
        else:
            logger.warning("Redis cache is not available, falling back to in-memory cache")
    
    # Start background worker if in production
    worker_task = None
    if settings.ENVIRONMENT == "production":
        from app.worker import worker_loop
        logger.info("Starting background worker")
        worker_task = asyncio.create_task(worker_loop())
    
    yield
    
    # Shutdown: Cancel background tasks
    if worker_task:
        logger.info("Stopping background worker")
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Add custom middleware
app.middleware("http")(logging_middleware)
if settings.RATE_LIMIT_ENABLED:
    app.middleware("http")(rate_limit_middleware)

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Include routers
from app.routers import posts, templates, analytics, users, schedules, bulk_operations, linkedin

app.include_router(users.router)
app.include_router(posts.router)
app.include_router(templates.router)
app.include_router(analytics.router)
app.include_router(schedules.router)
app.include_router(bulk_operations.router)
app.include_router(linkedin.router)

@app.get("/")
async def root():
    return {"message": "Welcome to LinkedIn Content Manager API", "version": settings.APP_VERSION}

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": time.time()
    }

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate access token
    access_token = auth.create_access_token(data={"sub": user.email})
    
    # Generate refresh token
    refresh_token = auth.create_refresh_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@app.post("/token/refresh", response_model=schemas.Token)
async def refresh_token(
    token: schemas.RefreshToken,
    db: Session = Depends(get_db)
):
    try:
        # Validate refresh token
        payload = auth.decode_token(token.refresh_token)
        email = payload.get("sub")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user
        user = crud.get_user_by_email(db, email=email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Generate new access token
        access_token = auth.create_access_token(data={"sub": user.email})
        
        # Generate new refresh token
        refresh_token = auth.create_refresh_token(data={"sub": user.email})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        workers=settings.WORKER_CONCURRENCY if settings.ENVIRONMENT == "production" else 1
    )
