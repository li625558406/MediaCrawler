# -*- coding: utf-8 -*-
"""Dynamic task runner for MediaCrawler with multi-round scheduling"""

import asyncio
import copy
import random
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextvars import Token

import config
from var import crawler_type_var, source_keyword_var
from main import CrawlerFactory
from server.models import CrawlRequest, CrawlerConfig
from server.db_handler import MediaCrawlerDBHandler
from tools import utils


class TaskStatus:
    """Task status tracker"""
    def __init__(self, task_id: str, total_rounds: int):
        self.task_id = task_id
        self.total_rounds = total_rounds
        self.current_round = 0
        self.current_platform = None
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0.0
        self.error_message = None
        self.start_time = None
        self.end_time = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "current_round": self.current_round,
            "current_platform": self.current_platform,
            "total_rounds": self.total_rounds,
            "progress": self.progress,
            "error_message": self.error_message,
            "start_time": self.start_time,
            "end_time": self.end_time
        }


class ConfigInjector:
    """Dynamic configuration injector for MediaCrawler"""

    @staticmethod
    def inject_config(platform: str, keywords: List[str], crawler_config: CrawlerConfig) -> Dict[str, Token]:
        """Inject configuration into global config module
        Returns a dict of tokens for restoring original values
        """
        tokens = {}

        # Store original values and set new ones using contextvars
        # Note: We modify the config module directly
        original_platform = config.PLATFORM
        original_keywords = config.KEYWORDS
        original_login_type = config.LOGIN_TYPE
        original_crawler_type = config.CRAWLER_TYPE
        original_headless = config.HEADLESS
        original_enable_cdp = config.ENABLE_CDP_MODE
        original_enable_proxy = config.ENABLE_IP_PROXY
        original_max_notes = config.CRAWLER_MAX_NOTES_COUNT
        original_max_comments = config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES
        original_enable_comments = config.ENABLE_GET_COMMENTS
        original_enable_sub_comments = config.ENABLE_GET_SUB_COMMENTS
        original_sleep = config.CRAWLER_MAX_SLEEP_SEC

        # Set new values
        config.PLATFORM = platform
        config.KEYWORDS = ",".join(keywords)
        config.LOGIN_TYPE = crawler_config.login_type
        config.CRAWLER_TYPE = crawler_config.crawler_type
        config.HEADLESS = crawler_config.headless
        config.ENABLE_CDP_MODE = crawler_config.enable_cdp_mode
        config.ENABLE_IP_PROXY = crawler_config.enable_proxy
        config.IP_PROXY_POOL_COUNT = crawler_config.ip_proxy_pool_count
        config.CRAWLER_MAX_NOTES_COUNT = crawler_config.max_notes_count
        config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = crawler_config.max_comments_per_note
        config.ENABLE_GET_COMMENTS = crawler_config.enable_get_comments
        config.ENABLE_GET_SUB_COMMENTS = crawler_config.enable_get_sub_comments
        config.CRAWLER_MAX_SLEEP_SEC = crawler_config.max_sleep_sec

        # Store for restoration
        tokens["original_platform"] = original_platform
        tokens["original_keywords"] = original_keywords
        tokens["original_login_type"] = original_login_type
        tokens["original_crawler_type"] = original_crawler_type
        tokens["original_headless"] = original_headless
        tokens["original_enable_cdp"] = original_enable_cdp
        tokens["original_enable_proxy"] = original_enable_proxy
        tokens["original_max_notes"] = original_max_notes
        tokens["original_max_comments"] = original_max_comments
        tokens["original_enable_comments"] = original_enable_comments
        tokens["original_enable_sub_comments"] = original_enable_sub_comments
        tokens["original_sleep"] = original_sleep

        # Set contextvars
        tokens["crawler_type_token"] = crawler_type_var.set(crawler_config.crawler_type)

        # Handle sort_type for different platforms
        if hasattr(config, 'SORT_TYPE'):
            tokens["original_sort_type"] = config.SORT_TYPE
            config.SORT_TYPE = crawler_config.sort_type

        utils.logger.info(f"[ConfigInjector] Config injected for {platform}: keywords={keywords}")

        return tokens

    @staticmethod
    def restore_config(tokens: Dict[str, Token]):
        """Restore original configuration values"""
        if not tokens:
            return

        config.PLATFORM = tokens.get("original_platform", "xhs")
        config.KEYWORDS = tokens.get("original_keywords", "")
        config.LOGIN_TYPE = tokens.get("original_login_type", "qrcode")
        config.CRAWLER_TYPE = tokens.get("original_crawler_type", "search")
        config.HEADLESS = tokens.get("original_headless", False)
        config.ENABLE_CDP_MODE = tokens.get("original_enable_cdp", True)
        config.ENABLE_IP_PROXY = tokens.get("original_enable_proxy", False)
        config.CRAWLER_MAX_NOTES_COUNT = tokens.get("original_max_notes", 15)
        config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = tokens.get("original_max_comments", 10)
        config.ENABLE_GET_COMMENTS = tokens.get("original_enable_comments", True)
        config.ENABLE_GET_SUB_COMMENTS = tokens.get("original_enable_sub_comments", False)
        config.CRAWLER_MAX_SLEEP_SEC = tokens.get("original_sleep", 2)

        if "original_sort_type" in tokens:
            config.SORT_TYPE = tokens["original_sort_type"]

        # Reset contextvar
        if "crawler_type_token" in tokens:
            crawler_type_var.reset(tokens["crawler_type_token"])

        utils.logger.info("[ConfigInjector] Config restored to original values")


class CrawlerWrapper:
    """Wrapper for running crawler with custom keywords and data capture

    This wrapper intercepts the data storage process and returns
    crawled data instead of saving to file/database
    """

    def __init__(self, platform: str):
        self.platform = platform
        self.captured_posts: List[Dict[str, Any]] = []
        self.captured_comments: Dict[str, List[Dict[str, Any]]] = {}

    async def run_with_capture(self, keywords: List[str]) -> Dict[str, Any]:
        """Run crawler and capture data

        Returns:
            Dict containing:
                - posts: List of post data
                - comments: Dict mapping post_id to comment list
                - success: Boolean indicating if crawl succeeded
                - error: Error message if failed
        """
        try:
            utils.logger.info(f"[CrawlerWrapper] Starting crawl for {self.platform} with keywords: {keywords}")

            # Create crawler instance
            crawler = CrawlerFactory.create_crawler(self.platform)

            # Monkey-patch the store process to capture data
            # This is a bit hacky but allows us to capture data without modifying original code
            self._setup_data_capture()

            # Run the crawler
            await crawler.start()

            # Cleanup
            if hasattr(crawler, "browser_context"):
                try:
                    await crawler.browser_context.close()
                except:
                    pass

            utils.logger.info(f"[CrawlerWrapper] Crawl completed for {self.platform}: {len(self.captured_posts)} posts captured")

            return {
                "posts": self.captured_posts,
                "comments": self.captured_comments,
                "success": True,
                "error": None
            }

        except Exception as e:
            utils.logger.error(f"[CrawlerWrapper] Crawl failed for {self.platform}: {e}")
            return {
                "posts": [],
                "comments": {},
                "success": False,
                "error": str(e)
            }

    def _setup_data_capture(self):
        """Setup data capture by intercepting storage calls

        This method patches the storage implementations to capture data
        instead of saving to files/DB
        """
        # Import here to avoid circular imports
        import store.xhs as xhs_store
        import store.douyin as dy_store
        import store.bilibili as bili_store
        import store.weibo as wb_store
        import store.kuaishou as ks_store
        import store.tieba as tieba_store
        import store.zhihu as zhihu_store

        # Save original save methods
        original_methods = {}

        # Platform-specific store modules
        store_modules = {
            "xhs": xhs_store,
            "dy": dy_store,
            "bili": bili_store,
            "wb": wb_store,
            "ks": ks_store,
            "tieba": tieba_store,
            "zhihu": zhihu_store
        }

        if self.platform in store_modules:
            store_module = store_modules[self.platform]

            # Try to patch the save method
            if hasattr(store_module, "save_data"):
                original_methods["save_data"] = store_module.save_data
                store_module.save_data = self._capture_save_data

        self.original_methods = original_methods

    async def _capture_save_data(self, post_data: Dict[str, Any], comments_data: List[Dict[str, Any]]):
        """Capture method for saving data"""
        post_id = post_data.get("post_id") or post_data.get("note_id") or post_data.get("aweme_id") or post_data.get("id")

        if post_id:
            self.captured_posts.append(post_data)
            self.captured_comments[str(post_id)] = comments_data

        utils.logger.info(f"[CrawlerWrapper] Captured post: {self.platform}/{post_id}")


class TaskExecutor:
    """Main task executor for multi-round crawling"""

    # Global task lock
    _lock = asyncio.Lock()
    _current_task: Optional[TaskStatus] = None

    @classmethod
    async def execute_crawl_task(cls, request: CrawlRequest) -> str:
        """Execute crawl task with multi-round scheduling

        Returns:
            task_id: The ID of the started task
        """
        async with cls._lock:
            if cls._current_task and cls._current_task.status == "running":
                raise RuntimeError("Task queue is full. Another task is currently running.")

            # Generate task ID
            task_id = request.task_id or str(uuid.uuid4())
            total_rounds = len(request.keyword_groups)

            # Create task status
            task_status = TaskStatus(task_id, total_rounds)
            cls._current_task = task_status

        # Start task in background
        asyncio.create_task(cls._run_task_background(request, task_status))

        return task_id

    @classmethod
    async def _run_task_background(cls, request: CrawlRequest, task_status: TaskStatus):
        """Run task in background"""
        try:
            task_status.status = "running"
            task_status.start_time = datetime.now()

            utils.logger.info(f"=== Task {task_status.task_id} Started ===")
            utils.logger.info(f"Platforms: {request.platforms}")
            utils.logger.info(f"Total Rounds: {task_status.total_rounds}")

            db_handler = MediaCrawlerDBHandler()

            # Multi-round execution
            for round_idx, keyword_group in enumerate(request.keyword_groups, 1):
                task_status.current_round = round_idx
                utils.logger.info(f"=== Round {round_idx}/{task_status.total_rounds} Start ===")
                utils.logger.info(f"Keywords: {keyword_group}")

                for platform in request.platforms:
                    task_status.current_platform = platform
                    utils.logger.info(f"--- Processing Platform: {platform} ---")

                    try:
                        # Inject config
                        tokens = ConfigInjector.inject_config(
                            platform=platform,
                            keywords=keyword_group,
                            crawler_config=request.config
                        )

                        # Run crawler
                        wrapper = CrawlerWrapper(platform)
                        result = await wrapper.run_with_capture(keyword_group)

                        # Restore config
                        ConfigInjector.restore_config(tokens)

                        if result["success"]:
                            # Save to MongoDB
                            metadata = {
                                "task_id": task_status.task_id,
                                "round": round_idx,
                                "keywords": keyword_group,
                                "crawl_time": datetime.now()
                            }

                            saved_count = await db_handler.save_batch(
                                platform=platform,
                                posts_data=result["posts"],
                                comments_dict=result["comments"],
                                metadata=metadata
                            )

                            utils.logger.info(f"[Task] Saved {saved_count} posts for {platform}")
                        else:
                            utils.logger.error(f"[Task] Platform {platform} failed: {result['error']}")

                        # Create indexes if needed
                        await db_handler.create_indexes(platform)

                        # Sleep between platforms
                        if platform != request.platforms[-1]:
                            sleep_time = random.uniform(60, 120)
                            utils.logger.info(f"[Task] Sleeping {sleep_time:.1f}s before next platform...")
                            await asyncio.sleep(sleep_time)

                    except Exception as e:
                        utils.logger.error(f"[Task] Error processing {platform}: {e}")
                        ConfigInjector.restore_config({})

                # Update progress
                task_status.progress = (round_idx / task_status.total_rounds) * 100

                # Sleep between rounds
                if round_idx < task_status.total_rounds:
                    sleep_time = random.uniform(300, 600)
                    utils.logger.info(f"=== Round {round_idx} Completed. Sleeping {sleep_time:.1f}s before next round ===")
                    await asyncio.sleep(sleep_time)

            # Task completed successfully
            task_status.status = "completed"
            task_status.progress = 100.0
            task_status.end_time = datetime.now()
            utils.logger.info(f"=== Task {task_status.task_id} Completed Successfully ===")

        except Exception as e:
            task_status.status = "failed"
            task_status.error_message = str(e)
            task_status.end_time = datetime.now()
            utils.logger.error(f"=== Task {task_status.task_id} Failed: {e} ===")

        finally:
            async with cls._lock:
                if cls._current_task and cls._current_task.task_id == task_status.task_id:
                    cls._current_task = None

    @classmethod
    def get_task_status(cls, task_id: str) -> Optional[Dict[str, Any]]:
        """Get current task status"""
        if cls._current_task and cls._current_task.task_id == task_id:
            return cls._current_task.to_dict()
        return None

    @classmethod
    def is_running(cls) -> bool:
        """Check if any task is currently running"""
        return cls._current_task is not None and cls._current_task.status == "running"
