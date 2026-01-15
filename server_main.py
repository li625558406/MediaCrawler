# -*- coding: utf-8 -*-
"""MediaCrawler API Server

A FastAPI service that provides HTTP endpoints for controlling
the MediaCrawler with multi-platform, multi-round keyword crawling support.
"""
import sys
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from server.models import CrawlRequest, CrawlResponse, TaskStatusResponse
from server.task_runner import TaskExecutor
from server.db_handler import MediaCrawlerDBHandler
from tools import utils
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configure logger
utils.logger.info("Initializing MediaCrawler API Server...")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    utils.logger.info("MediaCrawler API Server starting up...")
    yield
    # Shutdown
    utils.logger.info("MediaCrawler API Server shutting down...")
    # Clean up any remaining tasks
    if TaskExecutor.is_running():
        utils.logger.warning("A task is still running. Forcing cleanup...")


# Create FastAPI app
app = FastAPI(
    title="MediaCrawler API",
    description="Multi-platform social media crawler API with MongoDB storage",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint - API information"""
    return {
        "name": "MediaCrawler API Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "start_crawl": "POST /start_crawl",
            "task_status": "GET /task_status/{task_id}",
            "is_running": "GET /is_running",
            "platforms": "GET /platforms"
        }
    }


@app.get("/platforms", tags=["Info"])
async def get_platforms():
    """Get list of supported platforms"""
    return {
        "platforms": [
            {"code": "xhs", "name": "小红书 (Xiaohongshu)"},
            {"code": "dy", "name": "抖音 (Douyin)"},
            {"code": "ks", "name": "快手 (Kuaishou)"},
            {"code": "bili", "name": "哔哩哔哩 (Bilibili)"},
            {"code": "wb", "name": "微博 (Weibo)"},
            {"code": "tieba", "name": "百度贴吧 (Tieba)"},
            {"code": "zhihu", "name": "知乎 (Zhihu)"}
        ]
    }


@app.get("/is_running", tags=["Info"])
async def check_if_running():
    """Check if a crawl task is currently running"""
    is_running = TaskExecutor.is_running()
    task_status = None

    if is_running:
        from server.task_runner import TaskExecutor as TE
        if TE._current_task:
            task_status = TE._current_task.to_dict()

    return {
        "is_running": is_running,
        "current_task": task_status
    }


@app.post(
    "/start_crawl",
    response_model=CrawlResponse,
    tags=["Crawl"],
    responses={
        200: {"description": "Task started successfully"},
        423: {"description": "Task queue is full (another task is running)"},
        400: {"description": "Invalid request parameters"}
    }
)
async def start_crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks
):
    """Start a multi-round crawl task

    This endpoint accepts a crawl request with multiple platforms and keyword groups.
    The task will be executed in the background with the following logic:

    1. For each round (keyword group):
       - For each platform:
         - Inject platform-specific configuration
         - Start crawler with current keywords
         - Collect posts and comments
         - Save to MongoDB (collection: {platform}_media_crawler)
         - Sleep 60-120 seconds between platforms
       - Sleep 300-600 seconds between rounds

    Args:
        request: Crawl request with platforms, keyword groups, and config
        background_tasks: FastAPI background tasks handler

    Returns:
        CrawlResponse with task_id and status

    Raises:
        HTTPException 423: If another task is currently running
        HTTPException 400: If request validation fails
    """
    try:
        # Check if another task is running
        if TaskExecutor.is_running():
            return JSONResponse(
                status_code=status.HTTP_423_LOCKED,
                content={
                    "detail": "Task queue is full. Another task is currently running.",
                    "current_task": TaskExecutor._current_task.to_dict() if TaskExecutor._current_task else None
                }
            )

        # Validate platforms
        valid_platforms = {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}
        invalid_platforms = set(request.platforms) - valid_platforms
        if invalid_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid platforms: {invalid_platforms}. Valid platforms: {valid_platforms}"
            )

        # Validate keyword groups
        if not request.keyword_groups or all(not kg for kg in request.keyword_groups):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one non-empty keyword group is required"
            )

        # Flatten keyword groups for validation
        all_keywords = [kw for group in request.keyword_groups for kw in group]
        if not all_keywords:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one keyword is required"
            )

        # Execute task
        task_id = await TaskExecutor.execute_crawl_task(request)

        utils.logger.info(f"[API] Task {task_id} started successfully")

        return CrawlResponse(
            task_id=task_id,
            status="started",
            message="Crawl task started successfully",
            platforms=request.platforms,
            total_rounds=len(request.keyword_groups)
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {e}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        utils.logger.error(f"[API] Error starting crawl task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.get(
    "/task_status/{task_id}",
    response_model=TaskStatusResponse,
    tags=["Task"]
)
async def get_task_status(task_id: str):
    """Get the status of a crawl task

    Args:
        task_id: The task ID returned by /start_crawl

    Returns:
        TaskStatusResponse with current task status

    Raises:
        HTTPException 404: If task is not found
    """
    try:
        task_status = TaskExecutor.get_task_status(task_id)

        if not task_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found or has expired"
            )

        return TaskStatusResponse(**task_status)

    except HTTPException:
        raise
    except Exception as e:
        utils.logger.error(f"[API] Error getting task status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/data/{platform}", tags=["Data"])
async def get_platform_data(
    platform: str,
    limit: int = 100,
    skip: int = 0
):
    """Get crawled data for a specific platform

    Args:
        platform: Platform code (xhs, dy, ks, etc.)
        limit: Maximum number of posts to return (default: 100)
        skip: Number of posts to skip (default: 0)

    Returns:
        List of posts with comments

    Raises:
        HTTPException 400: If platform is invalid
    """
    try:
        valid_platforms = {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}
        if platform not in valid_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid platform: {platform}. Valid platforms: {valid_platforms}"
            )

        db_handler = MediaCrawlerDBHandler()
        posts = await db_handler.get_posts_by_platform(platform, limit, skip)

        return {
            "platform": platform,
            "count": len(posts),
            "data": posts
        }

    except HTTPException:
        raise
    except Exception as e:
        utils.logger.error(f"[API] Error getting platform data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/stats/{platform}", tags=["Data"])
async def get_platform_stats(platform: str):
    """Get statistics for a specific platform

    Args:
        platform: Platform code (xhs, dy, ks, etc.)

    Returns:
        Statistics including total posts and comments

    Raises:
        HTTPException 400: If platform is invalid
    """
    try:
        valid_platforms = {"xhs", "dy", "ks", "bili", "wb", "tieba", "zhihu"}
        if platform not in valid_platforms:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid platform: {platform}. Valid platforms: {valid_platforms}"
            )

        db_handler = MediaCrawlerDBHandler()
        stats = await db_handler.get_stats_by_platform(platform)

        return stats

    except HTTPException:
        raise
    except Exception as e:
        utils.logger.error(f"[API] Error getting platform stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "MediaCrawler API Server"
    }


def main():
    """Run the API server"""
    import uvicorn
    # On Windows, we need to ensure WindowsProactorEventLoopPolicy is used
    # to support Playwright subprocess creation. We need to disable reload
    # mode because it's incompatible with WindowsProactorEventLoopPolicy.
    # If you need auto-reload during development, consider using tools like
    # watchfiles or nodemon instead.
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False,  # Must be False on Windows for Playwright to work
        log_level="info"
    )


if __name__ == "__main__":
    main()
