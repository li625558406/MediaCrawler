# -*- coding: utf-8 -*-
"""Test script for MediaCrawler API Server"""

import requests
import time
import json


BASE_URL = "http://localhost:8000"


def test_start_crawl():
    """Test starting a crawl task"""
    print("\n=== Testing POST /start_crawl ===")

    request_data = {
        "platforms": ["xhs"],
        "keyword_groups": [
            ["编程副业"]
        ],
        "config": {
            "login_type": "cookie",
            "crawler_type": "search",
            "headless": False,
            "enable_cdp_mode": True,
            "max_notes_count": 5,
            "max_comments_per_note": 5
        }
    }

    response = requests.post(f"{BASE_URL}/start_crawl", json=request_data)

    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result.get("task_id")
    else:
        print(f"Error: {response.text}")
        return None


def test_task_status(task_id):
    """Test getting task status"""
    print(f"\n=== Testing GET /task_status/{task_id} ===")

    response = requests.get(f"{BASE_URL}/task_status/{task_id}")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")


def test_is_running():
    """Test checking if task is running"""
    print("\n=== Testing GET /is_running ===")

    response = requests.get(f"{BASE_URL}/is_running")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")


def test_platforms():
    """Test getting supported platforms"""
    print("\n=== Testing GET /platforms ===")

    response = requests.get(f"{BASE_URL}/platforms")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")


def test_get_data(platform="xhs"):
    """Test getting platform data"""
    print(f"\n=== Testing GET /data/{platform} ===")

    response = requests.get(f"{BASE_URL}/data/{platform}", params={"limit": 5})

    print(f"Status Code: {response.status_code}")
    result = response.json()
    print(f"Count: {result.get('count')}")
    print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)}")


def test_stats(platform="xhs"):
    """Test getting platform stats"""
    print(f"\n=== Testing GET /stats/{platform} ===")

    response = requests.get(f"{BASE_URL}/stats/{platform}")

    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")


def main():
    """Run all tests"""
    print("=" * 60)
    print("MediaCrawler API Server Test")
    print("=" * 60)

    # Test platforms endpoint
    test_platforms()

    # Test is_running before starting
    test_is_running()

    # Start a crawl task
    task_id = test_start_crawl()

    if task_id:
        # Monitor task status
        print("\n--- Monitoring task status (press Ctrl+C to stop) ---")
        try:
            for i in range(10):
                time.sleep(5)
                test_task_status(task_id)
                test_is_running()

        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user")

    # Test data endpoints
    test_get_data()
    test_stats()

    print("\n" + "=" * 60)
    print("Tests completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
