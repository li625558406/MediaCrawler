# -*- coding: utf-8 -*-
"""MongoDB handler for storing crawl results with dynamic collection naming"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from database.mongodb_store_base import MongoDBConnection
from tools import utils


class MediaCrawlerDBHandler:
    """MongoDB handler for MediaCrawler API
    Dynamically creates collections based on platform name
    """

    def __init__(self):
        self._connection = MongoDBConnection()

    async def get_db(self) -> AsyncIOMotorDatabase:
        """Get MongoDB database instance"""
        return await self._connection.get_db()

    async def get_collection(self, platform: str) -> AsyncIOMotorCollection:
        """Get collection for specific platform
        Collection name: {platform}_media_crawler
        Example: xhs_media_crawler, dy_media_crawler
        """
        db = await self.get_db()
        collection_name = f"{platform}_media_crawler"
        return db[collection_name]

    async def save_post_with_comments(
        self,
        platform: str,
        post_data: Dict[str, Any],
        comments: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Save post with its comments
        Uses upsert to avoid duplicates based on post_id/note_id

        Args:
            platform: Platform name (xhs, dy, etc.)
            post_data: Post/note detail data
            comments: List of comment data
            metadata: Additional metadata (task_id, crawl_time, etc.)
        """
        try:
            collection = await self.get_collection(platform)

            # Build unique query based on platform-specific ID field
            # Different platforms use different field names for post ID
            post_id = post_data.get("post_id") or post_data.get("note_id") or post_data.get("aweme_id") or post_data.get("id")
            if not post_id:
                utils.logger.warning(f"[DBHandler] No post_id found in post_data for {platform}")
                return False

            query = {"post_id": str(post_id)}

            # Build document to save
            document = {
                "post_id": str(post_id),
                "post_detail": post_data,
                "comments": comments,
                "comment_count": len(comments),
                "crawl_metadata": metadata or {},
                "updated_at": datetime.now()
            }

            # Upsert operation
            result = await collection.update_one(
                query,
                {"$set": document},
                upsert=True
            )

            if result.upserted_id:
                utils.logger.info(f"[DBHandler] New post saved: {platform}/{post_id}")
            else:
                utils.logger.info(f"[DBHandler] Post updated: {platform}/{post_id}")

            return True

        except Exception as e:
            utils.logger.error(f"[DBHandler] Save failed for {platform}: {e}")
            return False

    async def save_batch(
        self,
        platform: str,
        posts_data: List[Dict[str, Any]],
        comments_dict: Dict[str, List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """Save batch of posts with comments
        Returns number of successfully saved posts
        """
        success_count = 0
        for post_data in posts_data:
            post_id = post_data.get("post_id") or post_data.get("note_id") or post_data.get("aweme_id") or post_data.get("id")
            if not post_id:
                continue

            comments = comments_dict.get(str(post_id), [])
            success = await self.save_post_with_comments(
                platform=platform,
                post_data=post_data,
                comments=comments,
                metadata=metadata
            )
            if success:
                success_count += 1

        utils.logger.info(f"[DBHandler] Batch save for {platform}: {success_count}/{len(posts_data)} posts")
        return success_count

    async def get_posts_by_platform(
        self,
        platform: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Get posts from platform collection"""
        try:
            collection = await self.get_collection(platform)
            cursor = collection.find().skip(skip).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            utils.logger.error(f"[DBHandler] Get posts failed for {platform}: {e}")
            return []

    async def get_post_by_id(self, platform: str, post_id: str) -> Optional[Dict[str, Any]]:
        """Get single post by ID"""
        try:
            collection = await self.get_collection(platform)
            return await collection.find_one({"post_id": str(post_id)})
        except Exception as e:
            utils.logger.error(f"[DBHandler] Get post failed for {platform}/{post_id}: {e}")
            return None

    async def create_indexes(self, platform: str):
        """Create indexes for platform collection"""
        try:
            collection = await self.get_collection(platform)
            await collection.create_index([("post_id", 1)], unique=True)
            await collection.create_index([("updated_at", -1)])
            await collection.create_index([("crawl_metadata.task_id", 1)])
            utils.logger.info(f"[DBHandler] Indexes created for {platform}")
        except Exception as e:
            utils.logger.error(f"[DBHandler] Create indexes failed for {platform}: {e}")

    async def get_stats_by_platform(self, platform: str) -> Dict[str, Any]:
        """Get statistics for platform collection"""
        try:
            collection = await self.get_collection(platform)
            total_posts = await collection.count_documents({})
            total_comments = await collection.aggregate([
                {"$group": {"_id": None, "total": {"$sum": "$comment_count"}}}
            ]).to_list(length=1)

            return {
                "platform": platform,
                "total_posts": total_posts,
                "total_comments": total_comments[0]["total"] if total_comments else 0
            }
        except Exception as e:
            utils.logger.error(f"[DBHandler] Get stats failed for {platform}: {e}")
            return {"platform": platform, "total_posts": 0, "total_comments": 0}
