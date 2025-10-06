#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
キャッシュ管理システム
SQLiteベースのキャッシュでNotion APIコール結果を保存・再利用
"""

import sqlite3
import pickle
import hashlib
import json
import time
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import os
import threading


class CacheManager:
    """SQLiteベースのキャッシュ管理クラス"""
    
    def __init__(self, cache_db_path: str = "cache.db"):
        self.cache_db_path = cache_db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """データベースを初期化"""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            # キャッシュテーブルを作成
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value BLOB,
                    created_at REAL,
                    expires_at REAL,
                    cache_type TEXT
                )
            ''')
            
            # インデックスを作成
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_expires_at ON cache(expires_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cache_type ON cache(cache_type)')
            
            conn.commit()
            conn.close()
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """キャッシュキーを生成"""
        key_data = {
            'prefix': prefix,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュから値を取得"""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT value, expires_at FROM cache 
                WHERE key = ? AND expires_at > ?
            ''', (key, time.time()))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return pickle.loads(result[0])
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600, cache_type: str = "default") -> None:
        """キャッシュに値を保存"""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            expires_at = time.time() + ttl
            value_blob = pickle.dumps(value)
            
            cursor.execute('''
                INSERT OR REPLACE INTO cache (key, value, created_at, expires_at, cache_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (key, value_blob, time.time(), expires_at, cache_type))
            
            conn.commit()
            conn.close()
    
    def delete(self, key: str) -> None:
        """キャッシュから値を削除"""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM cache WHERE key = ?', (key,))
            
            conn.commit()
            conn.close()
    
    def clear_expired(self) -> int:
        """期限切れのキャッシュを削除"""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM cache WHERE expires_at <= ?', (time.time(),))
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return deleted_count
    
    def clear_by_type(self, cache_type: str) -> int:
        """指定タイプのキャッシュを削除"""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM cache WHERE cache_type = ?', (cache_type,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return deleted_count
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            # 総数
            cursor.execute('SELECT COUNT(*) FROM cache')
            total_count = cursor.fetchone()[0]
            
            # 有効なキャッシュ数
            cursor.execute('SELECT COUNT(*) FROM cache WHERE expires_at > ?', (time.time(),))
            valid_count = cursor.fetchone()[0]
            
            # タイプ別統計
            cursor.execute('''
                SELECT cache_type, COUNT(*) 
                FROM cache 
                WHERE expires_at > ? 
                GROUP BY cache_type
            ''', (time.time(),))
            type_stats = dict(cursor.fetchall())
            
            conn.close()
            
            return {
                'total_count': total_count,
                'valid_count': valid_count,
                'expired_count': total_count - valid_count,
                'type_stats': type_stats
            }
    
    def cleanup(self) -> Dict[str, int]:
        """キャッシュクリーンアップを実行"""
        expired_deleted = self.clear_expired()
        
        # 古いキャッシュも削除（7日以上前）
        with self._lock:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            old_threshold = time.time() - (7 * 24 * 3600)  # 7日前
            cursor.execute('DELETE FROM cache WHERE created_at < ?', (old_threshold,))
            old_deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
        
        return {
            'expired_deleted': expired_deleted,
            'old_deleted': old_deleted
        }


# グローバルキャッシュマネージャー
cache_manager = CacheManager()


def cached_result(ttl: int = 3600, cache_type: str = "default"):
    """キャッシュデコレータ"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # キャッシュキーを生成
            key = cache_manager._generate_key(func.__name__, *args, **kwargs)
            
            # キャッシュから取得を試行
            cached_value = cache_manager.get(key)
            if cached_value is not None:
                return cached_value
            
            # キャッシュにない場合は実行
            result = func(*args, **kwargs)
            
            # 結果をキャッシュに保存
            if result is not None:
                cache_manager.set(key, result, ttl, cache_type)
            
            return result
        return wrapper
    return decorator
