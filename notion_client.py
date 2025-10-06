#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Notion API関連の機能を管理するモジュール（非同期対応・キャッシュ対応）
"""

import os
import asyncio
import aiohttp
import json
from functools import lru_cache
from typing import Dict, List, Optional, Any
try:
    from .cache_manager import cache_manager, cached_result
except ImportError:
    # キャッシュ機能を無効化
    cache_manager = None
    def cached_result(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# Streamlitのインポート（条件付き）
try:
    import streamlit as st
except ImportError:
    # Streamlitが利用できない環境ではstをNoneに設定
    st = None


class NotionClient:
    """Notion APIクライアントの管理クラス（非同期対応・キャッシュ対応）"""
    
    def __init__(self):
        self.client = None
        self.api_key = None
        self.session = None
        self._initialize_api_key()
    
    def _initialize_api_key(self):
        """APIキーの初期化（遅延インポート対応）"""
        try:
            import streamlit as st
            self.api_key = (
                st.secrets.get("NOTION_API_KEY") or 
                st.secrets.get("NOTION_TOKEN") or 
                os.getenv("NOTION_API_KEY") or 
                os.getenv("NOTION_TOKEN")
            )
        except ImportError:
            # Streamlitが利用できない環境での初期化
            self.api_key = (
                os.getenv("NOTION_API_KEY") or 
                os.getenv("NOTION_TOKEN")
            )
        
        # デバッグ情報
        if self.api_key:
            print(f"🔑 Notion APIキー取得成功: {self.api_key[:10]}...")
        else:
            print("❌ Notion APIキーが取得できませんでした")
    
    async def _get_session(self):
        """非同期HTTPセッションを取得"""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                }
            )
        return self.session
    
    async def _close_session(self):
        """HTTPセッションを閉じる"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _make_request(self, method: str, url: str, data: Optional[Dict] = None) -> Dict:
        """非同期HTTPリクエストを実行（HTTPステータス検査付き）"""
        session = await self._get_session()
        
        try:
            if method.upper() == "GET":
                async with session.get(url) as resp:
                    txt = await resp.text()
            elif method.upper() == "POST":
                async with session.post(url, json=data) as resp:
                    txt = await resp.text()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # HTTPステータス検査
            if resp.status >= 400:
                raise Exception(f"HTTP {resp.status}: {txt[:300]}")
            
            return json.loads(txt)
        except Exception as e:
            raise Exception(f"Notion API request failed: {str(e)}")
    
    @cached_result(ttl=1800, cache_type="notion_diagnostic")  # 30分キャッシュ
    async def load_diagnostic_data_async(self):
        """非同期で診断データを読み込み（キャッシュ対応）"""
        if not self.api_key:
            return None
        
        try:
            node_db_id = self._get_database_id("NODE_DB_ID", "NOTION_DIAGNOSTIC_DB_ID")
            if not node_db_id:
                return None
            
            # 非同期でデータベースクエリを実行
            url = f"https://api.notion.com/v1/databases/{node_db_id}/query"
            print(url)
            assert url.startswith("https://api.notion.com/"), f"URL malformed: {url}"
            response = await self._make_request("POST", url, {"page_size": 100})
            
            nodes = response.get("results", [])
            if not nodes:
                return None
            
            diagnostic_data = {
                "nodes": [],
                "start_nodes": []
            }
            
            # 並列でノード詳細を取得
            tasks = []
            for node in nodes:
                task = self._process_node_async(node)
                tasks.append(task)
            
            processed_nodes = await asyncio.gather(*tasks, return_exceptions=True)
            
            for node_info in processed_nodes:
                if isinstance(node_info, Exception):
                    continue
                diagnostic_data["nodes"].append(node_info)
                if node_info.get("category") == "開始":
                    diagnostic_data["start_nodes"].append(node_info)
            
            return diagnostic_data
            
        except Exception as e:
            print(f"Error loading diagnostic data: {e}")
            return None
    
    async def _process_node_async(self, node: Dict) -> Dict:
        """ノードを非同期で処理"""
        properties = node.get("properties", {})
        
        node_info = {
            "id": node.get("id"),
            "title": "",
            "category": "",
            "symptoms": [],
            "next_nodes": [],
            "related_cases": [],
            "related_items": []
        }
        
        # タイトルの抽出（診断フローDB: ノードID）
        title_prop = properties.get("ノードID", {})
        if title_prop.get("type") == "title" and title_prop.get("title"):
            node_info["title"] = title_prop["title"][0].get("plain_text", "")
        
        # カテゴリの抽出（text型対応）
        category_prop = properties.get("カテゴリ", {})
        if category_prop.get("type") in ("rich_text","text"):
            texts = category_prop.get("rich_text", [])
            node_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
        elif category_prop.get("type") == "select" and category_prop.get("select"):
            node_info["category"] = category_prop["select"].get("name", "")
        
        # 症状の抽出（text型対応）
        symptoms_prop = properties.get("症状", {})
        if symptoms_prop.get("type") == "multi_select":
            node_info["symptoms"] = [item.get("name", "") for item in symptoms_prop.get("multi_select", [])]
        elif symptoms_prop.get("type") in ("rich_text","text"):
            texts = symptoms_prop.get("rich_text", [])
            node_info["symptoms"] = ["".join(t.get("plain_text","") for t in texts)] if texts else []
        
        # 質問内容の抽出
        question_prop = properties.get("質問内容", {})
        if question_prop.get("type") in ("rich_text","text"):
            texts = question_prop.get("rich_text", [])
            node_info["question"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
        
        # 診断結果の抽出
        result_prop = properties.get("診断結果", {})
        if result_prop.get("type") in ("rich_text","text"):
            texts = result_prop.get("rich_text", [])
            node_info["diagnosis_result"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
        
        # 修理手順の抽出
        steps_prop = properties.get("修理手順", {})
        if steps_prop.get("type") in ("rich_text","text"):
            texts = steps_prop.get("rich_text", [])
            node_info["repair_steps"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
        
        # 注意事項の抽出
        warnings_prop = properties.get("注意事項", {})
        if warnings_prop.get("type") in ("rich_text","text"):
            texts = warnings_prop.get("rich_text", [])
            node_info["warnings"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
        
        # 開始フラグの抽出
        start_flag_prop = properties.get("開始フラグ", {})
        if start_flag_prop.get("type") == "checkbox":
            node_info["is_start"] = start_flag_prop.get("checkbox", False)
        
        # 終端フラグの抽出
        end_flag_prop = properties.get("終端フラグ", {})
        if end_flag_prop.get("type") == "checkbox":
            node_info["is_end"] = end_flag_prop.get("checkbox", False)
        
        # 次のノードの抽出
        next_nodes_prop = properties.get("次のノード", {})
        if next_nodes_prop.get("type") in ("rich_text","text"):
            texts = next_nodes_prop.get("rich_text", [])
            next_nodes_text = "".join(t.get("plain_text","") for t in texts) if texts else ""
            node_info["next_nodes"] = [node.strip() for node in next_nodes_text.split(",") if node.strip()]
        
        # routing_configの抽出
        routing_config_prop = properties.get("routing_config", {})
        if routing_config_prop.get("type") in ("rich_text","text"):
            texts = routing_config_prop.get("rich_text", [])
            routing_config_text = "".join(t.get("plain_text","") for t in texts) if texts else ""
            try:
                import json
                node_info["routing_config"] = json.loads(routing_config_text) if routing_config_text else {}
            except json.JSONDecodeError:
                print(f"⚠️ routing_configのJSON解析に失敗: {routing_config_text}")
                node_info["routing_config"] = {}
        
        # メモの抽出
        memo_prop = properties.get("メモ", {})
        if memo_prop.get("type") in ("rich_text","text"):
            texts = memo_prop.get("rich_text", [])
            node_info["memo"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
        
        # 関連データの並列取得
        related_tasks = []
        
        # 関連修理ケース
        cases_prop = properties.get("関連修理ケース", {})
        if cases_prop.get("type") == "relation":
            for relation in cases_prop.get("relation", []):
                task = self._get_related_case_async(relation["id"])
                related_tasks.append(task)
        
        # 関連部品・工具
        items_prop = properties.get("関連部品・工具", {})
        if items_prop.get("type") == "relation":
            for relation in items_prop.get("relation", []):
                task = self._get_related_item_async(relation["id"])
                related_tasks.append(task)
        
        # 並列実行
        if related_tasks:
            related_results = await asyncio.gather(*related_tasks, return_exceptions=True)
            for result in related_results:
                if isinstance(result, Exception):
                    continue
                if result.get("type") == "case":
                    node_info["related_cases"].append(result)
                elif result.get("type") == "item":
                    node_info["related_items"].append(result)
        
        return node_info
    
    async def _get_related_case_async(self, case_id: str) -> Dict:
        """関連修理ケースを非同期で取得"""
        try:
            url = f"https://api.notion.com/v1/pages/{case_id}"
            print(url)
            assert url.startswith("https://api.notion.com/"), f"URL malformed: {url}"
            response = await self._make_request("GET", url)
            properties = response.get("properties", {})
            
            case_info = {
                "id": case_id,
                "title": "",
                "category": "",
                "solution": "",
                "type": "case"
            }
            
            # タイトル抽出（修理ケースDB: ケースID）
            title_prop = properties.get("ケースID", {})
            if title_prop.get("type") == "title" and title_prop.get("title"):
                case_info["title"] = title_prop["title"][0].get("plain_text", "")
            
            # カテゴリ抽出（text型対応）
            cat_prop = properties.get("カテゴリ", {})
            if cat_prop.get("type") in ("rich_text","text"):
                texts = cat_prop.get("rich_text", [])
                case_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
            elif cat_prop.get("type") == "select" and cat_prop.get("select"):
                case_info["category"] = cat_prop["select"].get("name", "")
            
            # 解決方法抽出
            solution_prop = properties.get("解決方法", {})
            if solution_prop.get("type") == "rich_text" and solution_prop.get("rich_text"):
                case_info["solution"] = solution_prop["rich_text"][0].get("plain_text", "")
            
            return case_info
        except Exception:
            return {"type": "case", "error": True}
    
    async def _get_related_item_async(self, item_id: str) -> Dict:
        """関連部品・工具を非同期で取得"""
        try:
            url = f"https://api.notion.com/v1/pages/{item_id}"
            print(url)
            assert url.startswith("https://api.notion.com/"), f"URL malformed: {url}"
            response = await self._make_request("GET", url)
            properties = response.get("properties", {})
            
            item_info = {
                "id": item_id,
                "name": "",
                "category": "",
                "price": "",
                "supplier": "",
                "type": "item"
            }
            
            # 名前抽出（部品・工具DB: 部品名）
            name_prop = properties.get("部品名", {})
            if name_prop.get("type") == "title" and name_prop.get("title"):
                item_info["name"] = name_prop["title"][0].get("plain_text", "")
            
            # カテゴリ抽出（text型対応）
            cat_prop = properties.get("カテゴリ", {})
            if cat_prop.get("type") in ("rich_text","text"):
                texts = cat_prop.get("rich_text", [])
                item_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
            elif cat_prop.get("type") == "select" and cat_prop.get("select"):
                item_info["category"] = cat_prop["select"].get("name", "")
            
            # 価格抽出（text型対応）
            price_prop = properties.get("価格", {})
            if price_prop.get("type") in ("rich_text","text"):
                texts = price_prop.get("rich_text", [])
                item_info["price"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
            elif price_prop.get("type") == "number":
                item_info["price"] = str(price_prop.get("number", ""))
            
            # サプライヤー抽出
            supplier_prop = properties.get("サプライヤー", {})
            if supplier_prop.get("type") == "rich_text" and supplier_prop.get("rich_text"):
                item_info["supplier"] = supplier_prop["rich_text"][0].get("plain_text", "")
            
            return item_info
        except Exception:
            return {"type": "item", "error": True}
    
    def initialize_client(self):
        """Notionクライアントを初期化（改善版）"""
        # Streamlitのインポートを先に試行
        try:
            import streamlit as st
            st_available = True
        except ImportError:
            st = None
            st_available = False
        
        try:
            print("🔄 Notionクライアント初期化を開始...")
            
            # APIキーの確認
            if not self.api_key:
                print("❌ Notion APIキーが設定されていません")
                if st_available:
                    st.error("❌ Notion APIキーが設定されていません")
                    st.info("💡 解決方法:")
                    st.info("1. .streamlit/secrets.tomlにNOTION_API_KEYを設定")
                    st.info("2. 環境変数NOTION_API_KEYを設定")
                    st.info("3. Notion統合でAPIキーを生成")
                else:
                    print("💡 環境変数NOTION_API_KEYを設定してください")
                return None
            
            # APIキーの形式確認
            if not self.api_key.startswith("secret_") and not self.api_key.startswith("ntn_"):
                if st_available:
                    st.warning("⚠️ Notion APIキーの形式が正しくない可能性があります")
                    st.info("💡 正しい形式: secret_... または ntn_...")
                else:
                    print("⚠️ Notion APIキーの形式が正しくない可能性があります")
            
            from notion_client import Client
            print(f"🔧 Notionクライアント作成中... (APIキー: {self.api_key[:10]}...)")
            self.client = Client(auth=self.api_key)
            
            # 接続テスト
            try:
                print("🔍 Notion API接続テスト中...")
                # ユーザー情報を取得して接続をテスト
                user = self.client.users.me()
                user_name = user.get('name', 'Unknown User')
                print(f"✅ Notion接続成功: {user_name}")
                
                # データベースIDの確認
                print("🔍 データベースID確認中...")
                node_db_id = self._get_database_id("NODE_DB_ID", "NOTION_DIAGNOSTIC_DB_ID")
                case_db_id = self._get_database_id("CASE_DB_ID", "NOTION_REPAIR_CASE_DB_ID")
                item_db_id = self._get_database_id("ITEM_DB_ID")
                
                print(f"📊 データベースID確認結果:")
                print(f"  - 診断フローDB: {node_db_id[:20]}..." if node_db_id else "  - 診断フローDB: ❌ 未設定")
                print(f"  - 修理ケースDB: {case_db_id[:20]}..." if case_db_id else "  - 修理ケースDB: ❌ 未設定")
                print(f"  - 部品・工具DB: {item_db_id[:20]}..." if item_db_id else "  - 部品・工具DB: ❌ 未設定")
                
                # データベースアクセス権限のテスト
                test_results = []
                
                if node_db_id:
                    try:
                        response = self.client.databases.query(database_id=node_db_id)
                        nodes_count = len(response.get("results", []))
                        test_results.append(f"✅ 診断フローDB: {nodes_count}件のノード")
                    except Exception as e:
                        test_results.append(f"❌ 診断フローDB: アクセス失敗 - {str(e)[:100]}")
                
                if case_db_id:
                    try:
                        response = self.client.databases.query(database_id=case_db_id)
                        cases_count = len(response.get("results", []))
                        test_results.append(f"✅ 修理ケースDB: {cases_count}件のケース")
                    except Exception as e:
                        test_results.append(f"❌ 修理ケースDB: アクセス失敗 - {str(e)[:100]}")
                
                if item_db_id:
                    try:
                        response = self.client.databases.query(database_id=item_db_id)
                        items_count = len(response.get("results", []))
                        test_results.append(f"✅ 部品・工具DB: {items_count}件のアイテム")
                    except Exception as e:
                        test_results.append(f"❌ 部品・工具DB: アクセス失敗 - {str(e)[:100]}")
                
                # テスト結果の簡易ログ（st が無い場合）
                if not st_available:
                    print("=== Notionデータベース接続テスト結果 ===")
                    for line in test_results:
                        print(line)
                    print("=====================================")
                
                return self.client
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Notion接続テスト失敗: {error_msg}")
                
                if st_available:
                    st.error(f"❌ Notion接続テスト失敗: {error_msg}")
                
                # エラーの種類に応じた解決方法を提示
                if "unauthorized" in error_msg.lower() or "401" in error_msg:
                    print("💡 解決方法: APIキーが無効です。新しいAPIキーを生成してください")
                    if st_available:
                        st.info("💡 解決方法: APIキーが無効です。新しいAPIキーを生成してください")
                elif "not_found" in error_msg.lower() or "404" in error_msg:
                    print("💡 解決方法: データベースIDが間違っているか、アクセス権限がありません")
                    if st_available:
                        st.info("💡 解決方法: データベースIDが間違っているか、アクセス権限がありません")
                elif "rate_limited" in error_msg.lower() or "429" in error_msg:
                    print("💡 解決方法: API制限に達しました。しばらく待ってから再試行してください")
                    if st_available:
                        st.info("💡 解決方法: API制限に達しました。しばらく待ってから再試行してください")
                else:
                    print("💡 解決方法: ネットワーク接続とAPIキーの権限を確認してください")
                    if st_available:
                        st.info("💡 解決方法: ネットワーク接続とAPIキーの権限を確認してください")
                
                return None
                
        except ImportError as e:
            print(f"❌ notion-clientライブラリがインストールされていません: {e}")
            print("💡 解決方法: pip install notion-client==2.2.1")
            if st_available:
                st.error(f"❌ notion-clientライブラリがインストールされていません: {e}")
                st.info("💡 解決方法: pip install notion-client==2.2.1")
            return None
        except Exception as e:
            print(f"❌ Notionクライアントの初期化に失敗: {e}")
            if st_available:
                st.error(f"❌ Notionクライアントの初期化に失敗: {e}")
            return None
    
    def _get_database_id(self, primary_key: str, secondary_key: str = None) -> Optional[str]:
        """データベースIDを取得"""
        try:
            import streamlit as st
            return (
                st.secrets.get(primary_key) or 
                (st.secrets.get(secondary_key) if secondary_key else None) or 
                os.getenv(primary_key) or 
                (os.getenv(secondary_key) if secondary_key else None)
            )
        except ImportError:
            # Streamlitコンテキスト外では環境変数のみ使用
            return (
                os.getenv(primary_key) or 
                (os.getenv(secondary_key) if secondary_key else None)
            )
    
    def load_diagnostic_data(self):
        """Notionから診断データを読み込み（ルーティング対応版）"""
        if not self.client:
            self.client = self.initialize_client()
        
        if not self.client:
            return None
        
        try:
            # データベースIDの取得（複数の設定方法に対応）
            node_db_id = self._get_database_id("NODE_DB_ID", "NOTION_DIAGNOSTIC_DB_ID")
            case_db_id = self._get_database_id("CASE_DB_ID", "NOTION_REPAIR_CASE_DB_ID")
            item_db_id = self._get_database_id("ITEM_DB_ID")
            
            if not node_db_id:
                print("❌ 診断フローDBのIDが設定されていません")
                try:
                    import streamlit as st
                    st.error("❌ 診断フローDBのIDが設定されていません")
                    st.info("💡 解決方法:")
                    st.info("1. .streamlit/secrets.tomlにNODE_DB_IDを設定")
                    st.info("2. 環境変数NODE_DB_IDを設定")
                    st.info("3. NotionデータベースのIDを確認")
                except ImportError:
                    pass
                return None
            
            # Notionから診断フローデータを取得（ルーティング対応）
            try:
                response = self.client.databases.query(database_id=node_db_id)
                nodes = response.get("results", [])
                
                if not nodes:
                    print("⚠️ 診断フローDBにデータがありません")
                    try:
                        import streamlit as st
                        st.warning("⚠️ 診断フローDBにデータがありません")
                        st.info("💡 Notionデータベースに診断ノードを追加してください")
                    except ImportError:
                        pass
                    return None
                    
            except Exception as e:
                error_msg = str(e)
                print(f"❌ 診断フローDBのクエリに失敗: {error_msg}")
                
                try:
                    import streamlit as st
                    st.error(f"❌ 診断フローDBのクエリに失敗: {error_msg}")
                except ImportError:
                    pass
                
                # エラーの種類に応じた解決方法を提示
                if "not_found" in error_msg.lower() or "404" in error_msg:
                    print("💡 解決方法: データベースIDが間違っています")
                    try:
                        import streamlit as st
                        st.info("💡 解決方法: データベースIDが間違っています")
                        st.info(f"   現在のID: {node_db_id}")
                        st.info("   NotionでデータベースのIDを確認してください")
                    except ImportError:
                        pass
                elif "unauthorized" in error_msg.lower() or "401" in error_msg:
                    print("💡 解決方法: APIキーにデータベースへのアクセス権限がありません")
                    try:
                        import streamlit as st
                        st.info("💡 解決方法: APIキーにデータベースへのアクセス権限がありません")
                        st.info("   Notion統合の設定でデータベースへのアクセスを許可してください")
                    except ImportError:
                        pass
                elif "rate_limited" in error_msg.lower() or "429" in error_msg:
                    print("💡 解決方法: API制限に達しました。しばらく待ってから再試行してください")
                    try:
                        import streamlit as st
                        st.info("💡 解決方法: API制限に達しました。しばらく待ってから再試行してください")
                    except ImportError:
                        pass
                else:
                    print("💡 解決方法: ネットワーク接続とAPIキーの権限を確認してください")
                    try:
                        import streamlit as st
                        st.info("💡 解決方法: ネットワーク接続とAPIキーの権限を確認してください")
                    except ImportError:
                        pass
                
                return None
            
            diagnostic_data = {
                "nodes": [],
                "start_nodes": []
            }
            
            for node in nodes:
                properties = node.get("properties", {})
                
                # ノードの基本情報を抽出（ルーティング対応）
                node_info = {
                    "id": node.get("id"),
                    "node_id": "",  # ノードID（title）
                    "title": "",
                    "category": "",
                    "symptoms": [],
                    "next_nodes": [],
                    "related_cases": [],  # 関連する修理ケース
                    "related_items": [],   # 関連する部品・工具
                    # ルーティング用フィールド
                    "start": False,        # 開始フラグ
                    "terminal": False,     # 終端フラグ
                    "next_raw": "",       # 次のノード（カンマ区切り）
                    "question": "",       # 質問内容
                    "result": "",         # 診断結果
                    "steps": "",          # 修理手順
                    "cautions": "",       # 注意事項
                    "routing": None       # メモ内JSONのrouting_config
                }
                
                # ノードIDの抽出（診断フローDB: ノードID）
                title_prop = properties.get("ノードID", {})
                if title_prop.get("type") == "title" and title_prop.get("title"):
                    node_info["node_id"] = title_prop["title"][0].get("plain_text", "")
                    node_info["title"] = node_info["node_id"]  # 互換性のため
                
                # 開始フラグの抽出
                start_prop = properties.get("開始フラグ", {})
                if start_prop.get("type") in ("rich_text", "text"):
                    texts = start_prop.get("rich_text", [])
                    start_value = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                    node_info["start"] = start_value == "**YES**"
                elif start_prop.get("type") == "select" and start_prop.get("select"):
                    node_info["start"] = start_prop["select"].get("name", "") == "**YES**"
                
                # 終端フラグの抽出
                terminal_prop = properties.get("終端フラグ", {})
                if terminal_prop.get("type") in ("rich_text", "text"):
                    texts = terminal_prop.get("rich_text", [])
                    terminal_value = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                    node_info["terminal"] = terminal_value == "**YES**"
                elif terminal_prop.get("type") == "select" and terminal_prop.get("select"):
                    node_info["terminal"] = terminal_prop["select"].get("name", "") == "**YES**"
                
                # 次のノードの抽出
                next_prop = properties.get("次のノード", {})
                if next_prop.get("type") in ("rich_text", "text"):
                    texts = next_prop.get("rich_text", [])
                    node_info["next_raw"] = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                
                # 質問内容の抽出
                question_prop = properties.get("質問内容", {})
                if question_prop.get("type") in ("rich_text", "text"):
                    texts = question_prop.get("rich_text", [])
                    node_info["question"] = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                
                # 診断結果の抽出
                result_prop = properties.get("診断結果", {})
                if result_prop.get("type") in ("rich_text", "text"):
                    texts = result_prop.get("rich_text", [])
                    node_info["result"] = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                
                # 修理手順の抽出
                steps_prop = properties.get("修理手順", {})
                if steps_prop.get("type") in ("rich_text", "text"):
                    texts = steps_prop.get("rich_text", [])
                    node_info["steps"] = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                
                # 注意事項の抽出
                cautions_prop = properties.get("注意事項", {})
                if cautions_prop.get("type") in ("rich_text", "text"):
                    texts = cautions_prop.get("rich_text", [])
                    node_info["cautions"] = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                
                # メモ（routing_config）の抽出
                memo_prop = properties.get("メモ", {})
                if memo_prop.get("type") in ("rich_text", "text"):
                    texts = memo_prop.get("rich_text", [])
                    memo_content = "".join(t.get("plain_text", "") for t in texts) if texts else ""
                    node_info["routing"] = self._parse_routing_config(memo_content)
                
                # カテゴリの抽出（text型対応）
                category_prop = properties.get("カテゴリ", {})
                if category_prop.get("type") in ("rich_text","text"):
                    texts = category_prop.get("rich_text", [])
                    node_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                elif category_prop.get("type") == "select" and category_prop.get("select"):
                    node_info["category"] = category_prop["select"].get("name", "")
                
                # 症状の抽出（text型対応）
                symptoms_prop = properties.get("症状", {})
                if symptoms_prop.get("type") == "multi_select":
                    node_info["symptoms"] = [item.get("name", "") for item in symptoms_prop.get("multi_select", [])]
                elif symptoms_prop.get("type") in ("rich_text","text"):
                    texts = symptoms_prop.get("rich_text", [])
                    node_info["symptoms"] = ["".join(t.get("plain_text","") for t in texts)] if texts else []
                
                # 関連修理ケースの抽出（リレーション対応）
                cases_prop = properties.get("関連修理ケース", {})
                if cases_prop.get("type") == "relation":
                    for relation in cases_prop.get("relation", []):
                        try:
                            case_response = self.client.pages.retrieve(page_id=relation["id"])
                            case_properties = case_response.get("properties", {})
                            
                            case_info = {
                                "id": relation["id"],
                                "title": "",
                                "category": "",
                                "solution": ""
                            }
                            
                            # ケースタイトルの抽出（修理ケースDB: ケースID）
                            title_prop = case_properties.get("ケースID", {})
                            if title_prop.get("type") == "title" and title_prop.get("title"):
                                case_info["title"] = title_prop["title"][0].get("plain_text", "")
                            
                            # カテゴリの抽出（text型対応）
                            cat_prop = case_properties.get("カテゴリ", {})
                            if cat_prop.get("type") in ("rich_text","text"):
                                texts = cat_prop.get("rich_text", [])
                                case_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                            elif cat_prop.get("type") == "select" and cat_prop.get("select"):
                                case_info["category"] = cat_prop["select"].get("name", "")
                            
                            # 解決方法の抽出
                            solution_prop = case_properties.get("解決方法", {})
                            if solution_prop.get("type") == "rich_text" and solution_prop.get("rich_text"):
                                case_info["solution"] = solution_prop["rich_text"][0].get("plain_text", "")
                            
                            node_info["related_cases"].append(case_info)
                        except Exception as e:
                            print(f"修理ケース情報の取得に失敗: {e}")
                            try:
                                import streamlit as st
                                st.warning(f"修理ケース情報の取得に失敗: {e}")
                            except ImportError:
                                pass
                
                # 関連部品・工具の抽出（リレーション対応）
                items_prop = properties.get("関連部品・工具", {})
                if items_prop.get("type") == "relation":
                    for relation in items_prop.get("relation", []):
                        try:
                            item_response = self.client.pages.retrieve(page_id=relation["id"])
                            item_properties = item_response.get("properties", {})
                            
                            item_info = {
                                "id": relation["id"],
                                "name": "",
                                "category": "",
                                "price": "",
                                "supplier": ""
                            }
                            
                            # アイテム名の抽出（部品・工具DB: 部品名）
                            name_prop = item_properties.get("部品名", {})
                            if name_prop.get("type") == "title" and name_prop.get("title"):
                                item_info["name"] = name_prop["title"][0].get("plain_text", "")
                            
                            # カテゴリの抽出（text型対応）
                            cat_prop = item_properties.get("カテゴリ", {})
                            if cat_prop.get("type") in ("rich_text","text"):
                                texts = cat_prop.get("rich_text", [])
                                item_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                            elif cat_prop.get("type") == "select" and cat_prop.get("select"):
                                item_info["category"] = cat_prop["select"].get("name", "")
                            
                            # 価格の抽出（text型対応）
                            price_prop = item_properties.get("価格", {})
                            if price_prop.get("type") in ("rich_text","text"):
                                texts = price_prop.get("rich_text", [])
                                item_info["price"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                            elif price_prop.get("type") == "number":
                                item_info["price"] = str(price_prop.get("number", ""))
                            
                            # サプライヤーの抽出
                            supplier_prop = item_properties.get("サプライヤー", {})
                            if supplier_prop.get("type") == "rich_text" and supplier_prop.get("rich_text"):
                                item_info["supplier"] = supplier_prop["rich_text"][0].get("plain_text", "")
                            
                            node_info["related_items"].append(item_info)
                        except Exception as e:
                            print(f"部品・工具情報の取得に失敗: {e}")
                            try:
                                import streamlit as st
                                st.warning(f"部品・工具情報の取得に失敗: {e}")
                            except ImportError:
                                pass
                
                diagnostic_data["nodes"].append(node_info)
                
                # 開始ノードの判定
                if node_info["category"] == "開始":
                    diagnostic_data["start_nodes"].append(node_info)
            
            return diagnostic_data
            
        except Exception as e:
            print(f"❌ Notionからの診断データ読み込みに失敗: {e}")
            try:
                import streamlit as st
                st.error(f"❌ Notionからの診断データ読み込みに失敗: {e}")
            except ImportError:
                pass
                return None
    
    def _parse_routing_config(self, memo_content):
        """メモ内のrouting_configをパース"""
        if not memo_content:
            return None
        
        try:
            import json
            # JSON形式のrouting_configを抽出
            if "routing_config" in memo_content:
                # 簡易的なJSON抽出（実際の実装ではより堅牢なパーサーを使用）
                start_idx = memo_content.find("{")
                end_idx = memo_content.rfind("}") + 1
                if start_idx != -1 and end_idx > start_idx:
                    json_str = memo_content[start_idx:end_idx]
                    config = json.loads(json_str)
                    return config.get("routing_config")
        except Exception as e:
            print(f"⚠️ routing_config解析エラー: {e}")
        
        return None
    
    def run_diagnostic_routing(self, user_input, diagnostic_data):
        """診断フローのルーティング実行"""
        if not diagnostic_data or not diagnostic_data.get("nodes"):
            print("❌ 診断データがありません")
            return {"text": "フォールバック診断（暫定）:\n" + user_input, "end": True}
        
        nodes = diagnostic_data["nodes"]
        
        # ノードインデックス作成
        node_index = {node["node_id"]: node for node in nodes if node.get("node_id")}
        
        # 開始ノードを検索
        start_nodes = [node for node in nodes if node.get("start", False)]
        
        print(f"📊 開始ノード数: {len(start_nodes)}")
        
        if not start_nodes:
            print("❌ 開始ノードが見つかりません")
            return {"text": "フォールバック診断（暫定）:\n" + user_input, "end": True}
        
        # 最初の開始ノードを選択（カテゴリ指定などは後で実装）
        current_node = start_nodes[0]
        print(f"🎯 選定ノード: {current_node.get('node_id', 'unknown')}")
        
        # 遷移ループ（最大20回のホップで無限ループを防止）
        seen_nodes = set()
        for hop in range(20):
            node_id = current_node.get("node_id")
            
            if not node_id:
                break
                
            if node_id in seen_nodes:
                print(f"⚠️ 循環検出: {node_id}")
                break
            seen_nodes.add(node_id)
            
            # 終端ノードかチェック
            if current_node.get("terminal", False):
                print(f"🏁 終端判定: {node_id}")
                # 出力整形
                output_parts = []
                
                if current_node.get("result"):
                    output_parts.append(f"診断結果:\n{current_node['result']}")
                if current_node.get("steps"):
                    output_parts.append(f"修理手順:\n{current_node['steps']}")
                if current_node.get("cautions"):
                    output_parts.append(f"注意事項:\n{current_node['cautions']}")
                
                result_text = "\n\n".join(output_parts) if output_parts else "診断完了"
                print(f"📤 診断完了出力")
                return {"text": result_text, "end": True}
            
            # 次のノードを選択
            next_node = self._choose_next_node(user_input, current_node, node_index)
            
            if not next_node:
                print(f"❌ 次のノードが見つかりません: {node_id}")
                break
                
            print(f"➡️ 遷移: {node_id} → {next_node.get('node_id', 'unknown')}")
            current_node = next_node
        
        # 遷移が完了しない場合はフォールバック
        print("🔄 フォールバック採否: はい")
        return {"text": "フォールバック診断（暫定）:\n" + user_input, "end": True}
    
    def _choose_next_node(self, user_input, current_node, node_index):
        """次のノードを選択"""
        node_id = current_node.get("node_id")
        
        # 1. routing_config を最優先
        routing_config = current_node.get("routing")
        if routing_config and routing_config.get("next_nodes_map"):
            next_node = self._choose_by_routing(user_input, current_node, node_index)
            if next_node:
                return next_node
        
        # 2. next_raw を使用（フォールバック）
        next_raw = current_node.get("next_raw", "")
        if next_raw:
            next_ids = [id.strip() for id in next_raw.split(",")]
            for next_id in next_ids:
                if next_id in node_index:
                    return node_index[next_id]
        
        return None
    
    def _choose_by_routing(self, user_input, current_node, node_index):
        """routing_config によるノード選択"""
        routing_config = current_node.get("routing")
        if not routing_config:
            return None
        
        next_nodes_map = routing_config.get("next_nodes_map", [])
        threshold = routing_config.get("threshold", 0)
        
        best_candidate = None
        best_score = -1
        best_keyword_count = 0
        
        for candidate in next_nodes_map:
            candidate_id = candidate.get("id")
            if not candidate_id or candidate_id not in node_index:
                continue
            
            # キーワードマッチングスコア計算
            keywords = candidate.get("keywords", [])
            weight = candidate.get("weight", 1)
            
            hits = sum(1 for kw in keywords if kw in user_input)
            score = hits * weight
            keyword_count = len(keywords)
            
            print(f"🔍 keywordマッチ: {candidate_id} - ヒット数:{hits}, スコア:{score}, キーワード数:{keyword_count}")
            
            if score >= threshold:
                # スコアが最大、または同点の場合はキーワード数が多い方を選択
                if (score > best_score or 
                    (score == best_score and 
                     routing_config.get("tie_breaker_rule") == "specific_over_generic" and
                     keyword_count > best_keyword_count)):
                    best_candidate = candidate
                    best_score = score
                    best_keyword_count = keyword_count
        
        if best_candidate:
            return node_index[best_candidate["id"]]
        
        # フォールバック候補を確認
        for candidate in next_nodes_map:
            if candidate.get("fallback", False):
                candidate_id = candidate.get("id")
                if candidate_id in node_index:
                    return node_index[candidate_id]
        
        return None
    
    def load_repair_cases(self):
        """Notionから修理ケースデータを読み込み（キャッシュ最適化版）"""
        if not self.client:
            self.client = self.initialize_client()
        
        if not self.client:
            return None
        
        try:
            # データベースIDの取得
            case_db_id = self._get_database_id("CASE_DB_ID", "NOTION_REPAIR_CASE_DB_ID")
            
            if not case_db_id:
                if st:
                    st.error("❌ 修理ケースDBのIDが設定されていません")
                    st.info("💡 解決方法:")
                    st.info("1. .streamlit/secrets.tomlにCASE_DB_IDを設定")
                    st.info("2. 環境変数CASE_DB_IDを設定")
                    st.info("3. NotionデータベースのIDを確認")
                else:
                    print("❌ 修理ケースDBのIDが設定されていません")
                return None
            
            # Notionから修理ケースデータを取得
            try:
                response = self.client.databases.query(database_id=case_db_id)
                cases = response.get("results", [])
                
                if not cases:
                    if st:
                        st.warning("⚠️ 修理ケースDBにデータがありません")
                        st.info("💡 Notionデータベースに修理ケースを追加してください")
                    else:
                        print("⚠️ 修理ケースDBにデータがありません")
                    return None
                    
            except Exception as e:
                error_msg = str(e)
                if st:
                    st.error(f"❌ 修理ケースDBのクエリに失敗: {error_msg}")
                else:
                    print(f"❌ 修理ケースDBのクエリに失敗: {error_msg}")
                
                if "not_found" in error_msg.lower() or "404" in error_msg:
                    if st:
                        st.info("💡 解決方法: データベースIDが間違っています")
                        st.info(f"   現在のID: {case_db_id}")
                    else:
                        print("💡 解決方法: データベースIDが間違っています")
                elif "unauthorized" in error_msg.lower() or "401" in error_msg:
                    if st:
                        st.info("💡 解決方法: APIキーにデータベースへのアクセス権限がありません")
                    else:
                        print("💡 解決方法: APIキーにデータベースへのアクセス権限がありません")
                elif "rate_limited" in error_msg.lower() or "429" in error_msg:
                    if st:
                        st.info("💡 解決方法: API制限に達しました。しばらく待ってから再試行してください")
                    else:
                        print("💡 解決方法: API制限に達しました。しばらく待ってから再試行してください")
                else:
                    if st:
                        st.info("💡 解決方法: ネットワーク接続とAPIキーの権限を確認してください")
                    else:
                        print("💡 解決方法: ネットワーク接続とAPIキーの権限を確認してください")
                
                return None
            
            repair_cases = []
            
            for case in cases:
                properties = case.get("properties", {})
                
                # ケースの基本情報を抽出
                case_info = {
                    "id": case.get("id"),
                    "title": "",
                    "category": "",
                    "symptoms": [],
                    "solution": "",
                    "cost_estimate": "",
                    "difficulty": "",
                    "tools_required": [],
                    "parts_required": []
                }
                
                # タイトルの抽出（修理ケースDB: ケースID）
                title_prop = properties.get("ケースID", {})
                if title_prop.get("type") == "title" and title_prop.get("title"):
                    case_info["title"] = title_prop["title"][0].get("plain_text", "")
                
                # カテゴリの抽出（text型対応）
                category_prop = properties.get("カテゴリ", {})
                if category_prop.get("type") in ("rich_text","text"):
                    texts = category_prop.get("rich_text", [])
                    case_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                elif category_prop.get("type") == "select" and category_prop.get("select"):
                    case_info["category"] = category_prop["select"].get("name", "")
                
                # 症状の抽出（text型対応）
                symptoms_prop = properties.get("症状", {})
                if symptoms_prop.get("type") == "multi_select":
                    case_info["symptoms"] = [item.get("name", "") for item in symptoms_prop.get("multi_select", [])]
                elif symptoms_prop.get("type") in ("rich_text","text"):
                    texts = symptoms_prop.get("rich_text", [])
                    case_info["symptoms"] = ["".join(t.get("plain_text","") for t in texts)] if texts else []
                
                # 解決方法の抽出
                solution_prop = properties.get("解決方法", {})
                if solution_prop.get("type") == "rich_text" and solution_prop.get("rich_text"):
                    case_info["solution"] = solution_prop["rich_text"][0].get("plain_text", "")
                
                # 費用見積もりの抽出
                cost_prop = properties.get("費用見積もり", {})
                if cost_prop.get("type") == "rich_text" and cost_prop.get("rich_text"):
                    case_info["cost_estimate"] = cost_prop["rich_text"][0].get("plain_text", "")
                
                # 難易度の抽出（text型対応）
                difficulty_prop = properties.get("難易度", {})
                if difficulty_prop.get("type") in ("rich_text","text"):
                    texts = difficulty_prop.get("rich_text", [])
                    case_info["difficulty"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                elif difficulty_prop.get("type") == "select" and difficulty_prop.get("select"):
                    case_info["difficulty"] = difficulty_prop["select"].get("name", "")
                
                # 必要な工具の抽出（text型対応）
                tools_prop = properties.get("必要な工具", {})
                if tools_prop.get("type") == "multi_select":
                    case_info["tools_required"] = [item.get("name", "") for item in tools_prop.get("multi_select", [])]
                elif tools_prop.get("type") in ("rich_text","text"):
                    texts = tools_prop.get("rich_text", [])
                    case_info["tools_required"] = ["".join(t.get("plain_text","") for t in texts)] if texts else []
                
                # 必要な部品の抽出（text型対応）
                parts_prop = properties.get("必要な部品", {})
                if parts_prop.get("type") == "multi_select":
                    case_info["parts_required"] = [item.get("name", "") for item in parts_prop.get("multi_select", [])]
                elif parts_prop.get("type") in ("rich_text","text"):
                    texts = parts_prop.get("rich_text", [])
                    case_info["parts_required"] = ["".join(t.get("plain_text","") for t in texts)] if texts else []
                
                repair_cases.append(case_info)
            
            return repair_cases
            
        except Exception as e:
            if st:
                st.error(f"❌ Notionからの修理ケースデータ読み込みに失敗: {e}")
            else:
                print(f"❌ Notionからの修理ケースデータ読み込みに失敗: {e}")
            return None
    
    def test_connection(self):
        """NotionDB接続をテスト"""
        try:
            if not self.client:
                self.client = self.initialize_client()
            
            if not self.client:
                return False, "Notionクライアントの初期化に失敗"
            
            # ユーザー情報を取得して接続をテスト
            user = self.client.users.me()
            user_name = user.get('name', 'Unknown User')
            
            return True, f"Notion接続成功: {user_name}"
            
        except Exception as e:
            return False, f"Notion接続テスト失敗: {str(e)}"
    
    def get_repair_cases_by_category(self, category: str):
        """カテゴリ別に修理ケースを取得（キャッシュ付き）"""
        repair_cases = self.load_repair_cases()
        if not repair_cases:
            return []
        
        return [case for case in repair_cases if case.get("category", "").lower() == category.lower()]
    
    def get_items_by_category(self, category: str):
        """カテゴリ別に部品・工具を取得（text型フィールド対応）"""
        if not self.client:
            self.client = self.initialize_client()
        
        if not self.client:
            return []
        
        try:
            item_db_id = self._get_database_id("ITEM_DB_ID")
            if not item_db_id:
                return []
            
            # text型フィールドに対応した検索フィルター
            response = self.client.databases.query(
                database_id=item_db_id,
                filter={
                    "property": "カテゴリ",
                    "rich_text": {
                        "contains": category
                    }
                }
            )
            
            items = response.get("results", [])
            item_list = []
            
            for item in items:
                properties = item.get("properties", {})
                
                item_info = {
                    "id": item.get("id"),
                    "name": "",
                    "category": "",
                    "price": "",
                    "supplier": ""
                }
                
                # アイテム名の抽出（部品・工具DB: 部品名）
                name_prop = properties.get("部品名", {})
                if name_prop.get("type") == "title" and name_prop.get("title"):
                    item_info["name"] = name_prop["title"][0].get("plain_text", "")
                
                # カテゴリの抽出（text型対応）
                cat_prop = properties.get("カテゴリ", {})
                if cat_prop.get("type") in ("rich_text","text"):
                    texts = cat_prop.get("rich_text", [])
                    item_info["category"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                elif cat_prop.get("type") == "select" and cat_prop.get("select"):
                    item_info["category"] = cat_prop["select"].get("name", "")
                
                # 価格の抽出（text型対応）
                price_prop = properties.get("価格", {})
                if price_prop.get("type") in ("rich_text","text"):
                    texts = price_prop.get("rich_text", [])
                    item_info["price"] = "".join(t.get("plain_text","") for t in texts) if texts else ""
                elif price_prop.get("type") == "number":
                    item_info["price"] = str(price_prop.get("number", ""))
                
                # サプライヤーの抽出
                supplier_prop = properties.get("サプライヤー", {})
                if supplier_prop.get("type") == "rich_text" and supplier_prop.get("rich_text"):
                    item_info["supplier"] = supplier_prop["rich_text"][0].get("plain_text", "")
                
                item_list.append(item_info)
            
            return item_list
            
        except Exception as e:
            if st:
                st.error(f"❌ 部品・工具データの取得に失敗: {e}")
            else:
                print(f"❌ 部品・工具データの取得に失敗: {e}")
            return []
    
    def search_database(self, query: str):
        """Notionデータベースから関連情報を検索（text型フィールド対応）"""
        try:
            if not self.client:
                self.client = self.initialize_client()
            
            if not self.client:
                return []
            
            # 各データベースから検索
            results = []
            
            # 診断フローDBから検索
            node_db_id = self._get_database_id("NODE_DB_ID", "NOTION_DIAGNOSTIC_DB_ID")
            if node_db_id:
                try:
                    # text型フィールドに対応した検索フィルター
                    response = self.client.databases.query(
                        database_id=node_db_id,
                        filter={
                            "or": [
                                {
                                    "property": "ノードID",
                                    "title": {
                                        "contains": query
                                    }
                                },
                                {
                                    "property": "カテゴリ",
                                    "rich_text": {
                                        "contains": query
                                    }
                                },
                                {
                                    "property": "症状",
                                    "rich_text": {
                                        "contains": query
                                    }
                                }
                            ]
                        }
                    )
                    
                    for node in response.get("results", []):
                        properties = node.get("properties", {})
                        title_prop = properties.get("ノードID", {})
                        if title_prop.get("type") == "title" and title_prop.get("title"):
                            title = title_prop["title"][0].get("plain_text", "")
                            results.append({
                                "type": "診断ノード",
                                "title": title,
                                "id": node.get("id")
                            })
                except Exception as e:
                    if st:
                        st.warning(f"診断フローDBの検索に失敗: {e}")
                    else:
                        print(f"診断フローDBの検索に失敗: {e}")
            
            # 修理ケースDBから検索
            case_db_id = self._get_database_id("CASE_DB_ID", "NOTION_REPAIR_CASE_DB_ID")
            if case_db_id:
                try:
                    # text型フィールドに対応した検索フィルター
                    response = self.client.databases.query(
                        database_id=case_db_id,
                        filter={
                            "or": [
                                {
                                    "property": "ケースID",
                                    "title": {
                                        "contains": query
                                    }
                                },
                                {
                                    "property": "カテゴリ",
                                    "rich_text": {
                                        "contains": query
                                    }
                                },
                                {
                                    "property": "症状",
                                    "rich_text": {
                                        "contains": query
                                    }
                                },
                                {
                                    "property": "解決方法",
                                    "rich_text": {
                                        "contains": query
                                    }
                                }
                            ]
                        }
                    )
                    
                    for case in response.get("results", []):
                        properties = case.get("properties", {})
                        title_prop = properties.get("ケースID", {})
                        if title_prop.get("type") == "title" and title_prop.get("title"):
                            title = title_prop["title"][0].get("plain_text", "")
                            results.append({
                                "type": "修理ケース",
                                "title": title,
                                "id": case.get("id")
                            })
                except Exception as e:
                    if st:
                        st.warning(f"修理ケースDBの検索に失敗: {e}")
                    else:
                        print(f"修理ケースDBの検索に失敗: {e}")
            
            # 部品・工具DBから検索
            item_db_id = self._get_database_id("ITEM_DB_ID")
            if item_db_id:
                try:
                    # text型フィールドに対応した検索フィルター
                    response = self.client.databases.query(
                        database_id=item_db_id,
                        filter={
                            "or": [
                                {
                                    "property": "部品名",
                                    "title": {
                                        "contains": query
                                    }
                                },
                                {
                                    "property": "カテゴリ",
                                    "rich_text": {
                                        "contains": query
                                    }
                                },
                                {
                                    "property": "サプライヤー",
                                    "rich_text": {
                                        "contains": query
                                    }
                                }
                            ]
                        }
                    )
                    
                    for item in response.get("results", []):
                        properties = item.get("properties", {})
                        name_prop = properties.get("部品名", {})
                        if name_prop.get("type") == "title" and name_prop.get("title"):
                            name = name_prop["title"][0].get("plain_text", "")
                            results.append({
                                "type": "部品・工具",
                                "title": name,
                                "id": item.get("id")
                            })
                except Exception as e:
                    if st:
                        st.warning(f"部品・工具DBの検索に失敗: {e}")
                    else:
                        print(f"部品・工具DBの検索に失敗: {e}")
            
            return results
            
        except Exception as e:
            if st:
                st.error(f"❌ Notionデータベース検索に失敗: {e}")
            else:
                print(f"❌ Notionデータベース検索に失敗: {e}")
            return []


# グローバルインスタンス
notion_client = NotionClient()
