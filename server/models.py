# -*- coding: utf-8 -*-
"""Pydantic models for MediaCrawler API requests"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CrawlerConfig(BaseModel):
    """Crawler configuration model
    Supports all MediaCrawler config parameters with extra fields allowed
    """
    # Login configuration
    login_type: str = Field(default="qrcode", description="Login type: qrcode/phone/cookie")
    cookies: str = Field(default="", description="Cookies for login")

    # Crawler type configuration
    crawler_type: str = Field(default="search", description="Crawler type: search/detail/creator")
    sort_type: str = Field(default="general", description="Sort type for search results")

    # Browser configuration
    headless: bool = Field(default=False, description="Run browser in headless mode")
    enable_cdp_mode: bool = Field(default=True, description="Enable CDP mode for better anti-detection")

    # Proxy configuration
    enable_proxy: bool = Field(default=False, description="Enable IP proxy")
    ip_proxy_pool_count: int = Field(default=2, description="IP proxy pool count")

    # Data collection configuration
    max_scan_page: int = Field(default=10, description="Maximum pages to scan")
    max_notes_count: int = Field(default=20, description="Maximum notes to crawl")
    max_comments_per_note: int = Field(default=10, description="Maximum comments per note")
    enable_get_comments: bool = Field(default=True, description="Enable comment crawling")
    enable_get_sub_comments: bool = Field(default=False, description="Enable sub-comment crawling")

    # Sleep configuration
    max_sleep_sec: int = Field(default=2, description="Maximum sleep seconds between requests")

    # Allow extra fields for future compatibility
    model_config = {"extra": "allow"}


class CrawlRequest(BaseModel):
    """Request model for crawl task"""
    platforms: List[str] = Field(
        ...,
        description="Target platforms: xhs/dy/ks/bili/wb/tieba/zhihu",
        min_length=1
    )
    keyword_groups: List[List[str]] = Field(
        ...,
        description="Multiple keyword groups for multi-round crawling",
        min_length=1
    )
    config: CrawlerConfig = Field(
        default_factory=CrawlerConfig,
        description="Crawler configuration"
    )

    # Optional task metadata
    task_id: Optional[str] = Field(None, description="Custom task ID (auto-generated if not provided)")
    task_name: Optional[str] = Field(None, description="Task name for identification")


class CrawlResponse(BaseModel):
    """Response model for crawl task"""
    task_id: str
    status: str
    message: str
    platforms: List[str]
    total_rounds: int


class TaskStatusResponse(BaseModel):
    """Response model for task status query"""
    task_id: str
    status: str
    current_round: Optional[int] = None
    current_platform: Optional[str] = None
    total_rounds: int
    progress: float = 0.0
    error_message: Optional[str] = None
