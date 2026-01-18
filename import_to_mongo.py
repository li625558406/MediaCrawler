# -*- coding: utf-8 -*-
"""
完全隔离的MongoDB导入工具
将data目录下的comments和contents JSON文件组合后存入MongoDB
每个平台对应一个独立的collection
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any
from pymongo import MongoClient, ASCENDING
from datetime import datetime


class MongoDataImporter:
    """MongoDB数据导入器 - 完全隔离的实现"""

    # 平台名称到MongoDB collection名称的映射
    PLATFORM_COLLECTION_MAP = {
        "xhs": "xhs_mongo_data",
        "douyin": "douyin_mongo_data",
        "bili": "bili_mongo_data",
        "weibo": "weibo_mongo_data"
    }

    def __init__(self, host: str = "localhost", port: int = 27018,
                 db_name: str = "lee_ai", username: str = "", password: str = ""):
        """
        初始化MongoDB连接

        Args:
            host: MongoDB主机地址
            port: MongoDB端口
            db_name: 数据库名称
            username: 用户名
            password: 密码
        """
        self.host = host
        self.port = port
        self.db_name = db_name
        self.username = username
        self.password = password
        self.client = None
        self.db = None

    def connect(self):
        """建立MongoDB连接"""
        try:
            if self.username and self.password:
                mongo_uri = f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/"
            else:
                mongo_uri = f"mongodb://{self.host}:{self.port}/"

            self.client = MongoClient(mongo_uri)
            self.db = self.client[self.db_name]
            print(f"成功连接到MongoDB: {self.host}:{self.port}/{self.db_name}")
            return True
        except Exception as e:
            print(f"连接MongoDB失败: {e}")
            return False

    def close(self):
        """关闭MongoDB连接"""
        if self.client:
            self.client.close()
            print("MongoDB连接已关闭")

    def load_json_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        加载JSON文件

        Args:
            file_path: JSON文件路径

        Returns:
            JSON数据列表
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"成功加载文件: {file_path}, 共 {len(data)} 条记录")
                return data if isinstance(data, list) else [data]
        except FileNotFoundError:
            print(f"文件不存在: {file_path}")
            return []
        except json.JSONDecodeError as e:
            print(f"JSON解析错误 {file_path}: {e}")
            return []
        except Exception as e:
            print(f"加载文件失败 {file_path}: {e}")
            return []

    def combine_data(self, contents: List[Dict], comments: List[Dict]) -> List[Dict]:
        """
        组合contents和comments数据

        Args:
            contents: 内容数据列表
            comments: 评论数据列表

        Returns:
            组合后的数据列表
        """
        # 创建note_id到content的映射
        content_map = {item.get("note_id") or item.get("aweme_id") or item.get("id"): item
                       for item in contents if item.get("note_id") or item.get("aweme_id") or item.get("id")}

        # 创建note_id到comments列表的映射
        comments_map: Dict[str, List[Dict]] = {}
        for comment in comments:
            note_id = comment.get("note_id") or comment.get("aweme_id") or comment.get("oid")
            if note_id:
                if note_id not in comments_map:
                    comments_map[note_id] = []
                comments_map[note_id].append(comment)

        # 组合数据
        combined_data = []
        for note_id, content in content_map.items():
            combined_item = {
                "content": content,
                "comments": comments_map.get(note_id, []),
                "comment_count": len(comments_map.get(note_id, [])),
                "imported_at": datetime.now().isoformat()
            }
            combined_data.append(combined_item)

        # 添加只有comments没有content的数据（如果有）
        for note_id, comment_list in comments_map.items():
            if note_id not in content_map:
                combined_item = {
                    "content": None,
                    "comments": comment_list,
                    "comment_count": len(comment_list),
                    "imported_at": datetime.now().isoformat()
                }
                combined_data.append(combined_item)

        return combined_data

    def find_json_files(self, data_dir: str) -> Dict[str, Dict[str, str]]:
        """
        查找data目录下所有平台的JSON文件

        Args:
            data_dir: data目录路径

        Returns:
            字典结构: {platform: {type: file_path}}
        """
        result = {}
        data_path = Path(data_dir)

        if not data_path.exists():
            print(f"数据目录不存在: {data_dir}")
            return result

        # 遍历平台目录
        for platform_dir in data_path.iterdir():
            if not platform_dir.is_dir():
                continue

            platform_name = platform_dir.name
            if platform_name not in self.PLATFORM_COLLECTION_MAP:
                print(f"跳过未知平台: {platform_name}")
                continue

            json_dir = platform_dir / "json"
            if not json_dir.exists():
                print(f"平台 {platform_name} 没有json目录，跳过")
                continue

            # 查找comments和contents文件
            platform_files = {}
            for json_file in json_dir.glob("*.json"):
                file_name = json_file.name

                # 识别文件类型
                if "comments" in file_name:
                    platform_files["comments"] = str(json_file)
                elif "contents" in file_name:
                    platform_files["contents"] = str(json_file)

            if platform_files:
                result[platform_name] = platform_files

        return result

    def import_to_mongodb(self, data_dir: str = "./data", delete_existing: bool = False):
        """
        导入数据到MongoDB

        Args:
            data_dir: data目录路径
            delete_existing: 是否删除已存在的collection
        """
        # 查找所有JSON文件
        platform_files = self.find_json_files(data_dir)

        if not platform_files:
            print("未找到任何JSON文件")
            return

        print(f"\n找到 {len(platform_files)} 个平台的数据:")
        for platform, files in platform_files.items():
            print(f"  - {platform}: {list(files.keys())}")

        # 处理每个平台
        for platform_name, files in platform_files.items():
            print(f"\n{'='*60}")
            print(f"开始处理平台: {platform_name}")
            print(f"{'='*60}")

            # 加载数据
            comments_data = []
            contents_data = []

            if "comments" in files:
                comments_data = self.load_json_file(files["comments"])

            if "contents" in files:
                contents_data = self.load_json_file(files["contents"])

            if not comments_data and not contents_data:
                print(f"平台 {platform_name} 没有有效数据，跳过")
                continue

            # 组合数据
            combined_data = self.combine_data(contents_data, comments_data)
            print(f"组合后的数据: {len(combined_data)} 条")

            # 导入到MongoDB
            collection_name = self.PLATFORM_COLLECTION_MAP[platform_name]
            collection = self.db[collection_name]

            # 删除已存在的数据（可选）
            if delete_existing:
                result = collection.delete_many({})
                print(f"删除已存在数据: {result.deleted_count} 条")

            # 批量插入数据
            if combined_data:
                try:
                    result = collection.insert_many(combined_data)
                    print(f"成功插入 {len(result.inserted_ids)} 条数据到 collection: {collection_name}")

                    # 创建索引
                    collection.create_index([("content.note_id", ASCENDING)], sparse=True)
                    collection.create_index([("content.aweme_id", ASCENDING)], sparse=True)
                    collection.create_index([("imported_at", ASCENDING)])
                    print("索引创建完成")

                except Exception as e:
                    print(f"插入数据失败: {e}")

    def print_statistics(self, data_dir: str = "./data"):
        """
        打印统计信息

        Args:
            data_dir: data目录路径
        """
        platform_files = self.find_json_files(data_dir)

        print("\n" + "="*60)
        print("数据统计")
        print("="*60)

        for platform_name, files in platform_files.items():
            print(f"\n平台: {platform_name}")
            print(f"  Collection名称: {self.PLATFORM_COLLECTION_MAP[platform_name]}")

            comments_count = 0
            contents_count = 0

            if "comments" in files:
                comments_data = self.load_json_file(files["comments"])
                comments_count = len(comments_data)
                print(f"  Comments文件: {comments_count} 条")

            if "contents" in files:
                contents_data = self.load_json_file(files["contents"])
                contents_count = len(contents_data)
                print(f"  Contents文件: {contents_count} 条")

            # 检查MongoDB中的数据
            collection_name = self.PLATFORM_COLLECTION_MAP[platform_name]
            collection = self.db[collection_name]
            mongo_count = collection.count_documents({})
            print(f"  MongoDB中已有: {mongo_count} 条")


def main():
    """主函数"""
    # MongoDB配置（可以根据环境变量或直接指定）
    MONGODB_HOST = "localhost"
    MONGODB_PORT = 27018
    MONGODB_DB_NAME = "lee_ai"
    MONGODB_USER = ""
    MONGODB_PWD = ""

    # 数据目录
    DATA_DIR = "./data"

    print("MongoDB数据导入工具")
    print("="*60)

    # 创建导入器
    importer = MongoDataImporter(
        host=MONGODB_HOST,
        port=MONGODB_PORT,
        db_name=MONGODB_DB_NAME,
        username=MONGODB_USER,
        password=MONGODB_PWD
    )

    # 连接MongoDB
    if not importer.connect():
        print("无法连接到MongoDB，程序退出")
        return

    try:
        # 打印统计信息
        importer.print_statistics(DATA_DIR)

        # 询问是否删除已存在的数据
        print("\n" + "="*60)
        delete_existing = input("是否删除已存在的collection数据？(y/n): ").lower() == 'y'

        # 执行导入
        print("\n开始导入数据...")
        importer.import_to_mongodb(DATA_DIR, delete_existing=delete_existing)

        # 导入完成后的统计
        print("\n导入完成！最终统计:")
        importer.print_statistics(DATA_DIR)

    except KeyboardInterrupt:
        print("\n\n用户中断操作")
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 关闭连接
        importer.close()


if __name__ == "__main__":
    main()
