#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
診断データ管理機能を提供するモジュール
"""

import streamlit as st
from typing import Dict, List, Optional, Any, Tuple
from .notion_client import notion_client
from .knowledge_base import knowledge_base_manager


class DiagnosticDataManager:
    """診断データの管理クラス"""
    
    def __init__(self):
        self.diagnostic_data = None
        self.repair_cases = []
        self._load_data()
    
    def _load_data(self):
        """診断データと修理ケースを読み込み"""
        try:
            # NotionClientのインスタンスを新規作成して使用
            from .notion_client import NotionClient
            client = NotionClient()
            
            self.diagnostic_data = client.load_diagnostic_data()
            self.repair_cases = client.load_repair_cases() or []
        except Exception as e:
            print(f"診断データの読み込みに失敗: {e}")
            import traceback
            traceback.print_exc()
            self.diagnostic_data = None
            self.repair_cases = []
    
    def get_diagnostic_data(self) -> Optional[Dict]:
        """診断データを取得"""
        return self.diagnostic_data
    
    def get_repair_cases(self) -> List[Dict]:
        """修理ケースを取得"""
        return self.repair_cases
    
    def get_start_nodes(self) -> List[Dict]:
        """開始ノードを取得"""
        if not self.diagnostic_data:
            return []
        return self.diagnostic_data.get("start_nodes", [])
    
    def get_nodes_by_category(self, category: str) -> List[Dict]:
        """カテゴリ別にノードを取得"""
        if not self.diagnostic_data:
            return []
        
        nodes = self.diagnostic_data.get("nodes", [])
        return [node for node in nodes if node.get("category", "").lower() == category.lower()]
    
    def get_nodes_by_symptoms(self, symptoms: List[str]) -> List[Dict]:
        """症状別にノードを取得"""
        if not self.diagnostic_data:
            return []
        
        nodes = self.diagnostic_data.get("nodes", [])
        matching_nodes = []
        
        for node in nodes:
            node_symptoms = node.get("symptoms", [])
            if any(symptom.lower() in [s.lower() for s in node_symptoms] for symptom in symptoms):
                matching_nodes.append(node)
        
        return matching_nodes
    
    def get_repair_cases_by_category(self, category: str) -> List[Dict]:
        """カテゴリ別に修理ケースを取得"""
        return [case for case in self.repair_cases if case.get("category", "").lower() == category.lower()]
    
    def get_repair_cases_by_symptoms(self, symptoms: List[str]) -> List[Dict]:
        """症状別に修理ケースを取得"""
        matching_cases = []
        
        for case in self.repair_cases:
            case_symptoms = case.get("symptoms", [])
            if any(symptom.lower() in [s.lower() for s in case_symptoms] for symptom in symptoms):
                matching_cases.append(case)
        
        return matching_cases
    
    def create_relation_context(self, symptoms_input: str) -> str:
        """リレーションデータを活用したコンテキストを作成"""
        context = ""
        
        if not self.diagnostic_data and not self.repair_cases:
            return "診断データが利用できません。"
        
        # 診断ノードの関連情報
        if self.diagnostic_data:
            context += "## 診断フローノード情報\n"
            nodes = self.diagnostic_data.get("nodes", [])
            
            for node in nodes[:5]:  # 最大5ノード
                context += f"**{node.get('title', 'N/A')}**\n"
                context += f"- カテゴリ: {node.get('category', 'N/A')}\n"
                context += f"- 症状: {', '.join(node.get('symptoms', []))}\n"
                
                # 関連修理ケース
                related_cases = node.get("related_cases", [])
                if related_cases:
                    context += "- 関連修理ケース:\n"
                    for case in related_cases[:3]:  # 最大3ケース
                        context += f"  - {case.get('title', 'N/A')}: {case.get('solution', 'N/A')[:100]}...\n"
                
                # 関連部品・工具
                related_items = node.get("related_items", [])
                if related_items:
                    context += "- 関連部品・工具:\n"
                    for item in related_items[:3]:  # 最大3アイテム
                        context += f"  - {item.get('name', 'N/A')}: {item.get('price', 'N/A')}円 ({item.get('supplier', 'N/A')})\n"
                
                context += "\n"
        
        # 修理ケースの関連情報
        if self.repair_cases:
            context += "## 修理ケース情報\n"
            for case in self.repair_cases[:5]:  # 最大5ケース
                context += f"**{case.get('title', 'N/A')}**\n"
                context += f"- カテゴリ: {case.get('category', 'N/A')}\n"
                context += f"- 症状: {', '.join(case.get('symptoms', []))}\n"
                context += f"- 解決方法: {case.get('solution', 'N/A')[:200]}...\n"
                context += f"- 費用見積もり: {case.get('cost_estimate', 'N/A')}\n"
                context += f"- 難易度: {case.get('difficulty', 'N/A')}\n"
                context += f"- 必要な工具: {', '.join(case.get('tools_required', []))}\n"
                context += f"- 必要な部品: {', '.join(case.get('parts_required', []))}\n"
                context += "\n"
        
        return context
    
    def show_relation_details(self, symptoms_input: str):
        """リレーションデータの詳細を表示"""
        st.markdown("## 🔗 リレーションデータ詳細")
        
        if not self.diagnostic_data and not self.repair_cases:
            st.warning("診断データが利用できません。")
            return
        
        # 診断ノードの詳細
        if self.diagnostic_data:
            st.markdown("### 📊 診断フローノード")
            nodes = self.diagnostic_data.get("nodes", [])
            
            for i, node in enumerate(nodes[:3], 1):  # 最大3ノード表示
                with st.expander(f"ノード {i}: {node.get('title', 'N/A')}"):
                    st.write(f"**カテゴリ**: {node.get('category', 'N/A')}")
                    st.write(f"**症状**: {', '.join(node.get('symptoms', []))}")
                    
                    # 関連修理ケース
                    related_cases = node.get("related_cases", [])
                    if related_cases:
                        st.write("**関連修理ケース**:")
                        for case in related_cases:
                            st.write(f"- {case.get('title', 'N/A')}: {case.get('solution', 'N/A')}")
                    
                    # 関連部品・工具
                    related_items = node.get("related_items", [])
                    if related_items:
                        st.write("**関連部品・工具**:")
                        for item in related_items:
                            st.write(f"- {item.get('name', 'N/A')}: {item.get('price', 'N/A')}円 ({item.get('supplier', 'N/A')})")
        
        # 修理ケースの詳細
        if self.repair_cases:
            st.markdown("### 🔧 修理ケース")
            for i, case in enumerate(self.repair_cases[:3], 1):  # 最大3ケース表示
                with st.expander(f"ケース {i}: {case.get('title', 'N/A')}"):
                    st.write(f"**カテゴリ**: {case.get('category', 'N/A')}")
                    st.write(f"**症状**: {', '.join(case.get('symptoms', []))}")
                    st.write(f"**解決方法**: {case.get('solution', 'N/A')}")
                    st.write(f"**費用見積もり**: {case.get('cost_estimate', 'N/A')}")
                    st.write(f"**難易度**: {case.get('difficulty', 'N/A')}")
                    st.write(f"**必要な工具**: {', '.join(case.get('tools_required', []))}")
                    st.write(f"**必要な部品**: {', '.join(case.get('parts_required', []))}")
    
    def run_ai_diagnostic(self, symptoms_input: str) -> str:
        """AI診断モード（リレーション活用版）"""
        if not symptoms_input.strip():
            return "症状を入力してください。"
        
        # 知識ベースを読み込み
        knowledge_base = knowledge_base_manager.knowledge_base
        
        # リレーションデータを活用した高度なコンテキスト作成
        context = self.create_relation_context(symptoms_input)
        
        # 診断プロンプトを作成
        diagnosis_prompt = f"""症状: {symptoms_input}

{context}

上記の症状について、3つのデータベースのリレーション情報を活用して、以下の形式で詳細な診断と解決策を提供してください：

1. **診断結果**
2. **関連する修理ケース**
3. **必要な部品・工具（価格・サプライヤー情報付き）**
4. **修理手順**
5. **費用見積もり**
6. **注意事項**

各項目について、具体的で実用的な情報を提供してください。"""

        # AI応答を生成
        try:
            from langchain_openai import ChatOpenAI
            import os
            
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                return "OpenAI APIキーが設定されていません。"
            
            model = ChatOpenAI(api_key=openai_api_key, model_name="gpt-4o-mini")
            response = model.invoke(diagnosis_prompt)
            
            return response.content
            
        except Exception as e:
            return f"AI診断の実行中にエラーが発生しました: {str(e)}"
    
    def run_interactive_diagnostic(self, symptoms_input: str) -> Dict[str, Any]:
        """対話式診断モード（NotionDB活用版）"""
        if not symptoms_input.strip():
            return {"error": "症状を入力してください。"}
        
        # 症状に基づいて関連ノードを検索
        symptoms = symptoms_input.lower().split()
        matching_nodes = self.get_nodes_by_symptoms(symptoms)
        
        if not matching_nodes:
            return {"error": "該当する診断ノードが見つかりませんでした。"}
        
        # 関連修理ケースを検索
        matching_cases = self.get_repair_cases_by_symptoms(symptoms)
        
        # 結果を整理
        result = {
            "nodes": matching_nodes[:3],  # 最大3ノード
            "cases": matching_cases[:3],  # 最大3ケース
            "total_nodes": len(matching_nodes),
            "total_cases": len(matching_cases)
        }
        
        return result
    
    def run_detailed_diagnostic(self, symptoms_input: str) -> Dict[str, Any]:
        """詳細診断モード（リレーション活用版）"""
        if not symptoms_input.strip():
            return {"error": "症状を入力してください。"}
        
        # 症状に基づいて詳細検索
        symptoms = symptoms_input.lower().split()
        
        # 診断ノードの詳細検索
        all_nodes = self.diagnostic_data.get("nodes", []) if self.diagnostic_data else []
        detailed_nodes = []
        
        for node in all_nodes:
            node_symptoms = [s.lower() for s in node.get("symptoms", [])]
            node_title = node.get("title", "").lower()
            node_category = node.get("category", "").lower()
            
            # 症状、タイトル、カテゴリでマッチング
            if (any(symptom in node_symptoms for symptom in symptoms) or
                any(symptom in node_title for symptom in symptoms) or
                any(symptom in node_category for symptom in symptoms)):
                detailed_nodes.append(node)
        
        # 修理ケースの詳細検索
        detailed_cases = []
        for case in self.repair_cases:
            case_symptoms = [s.lower() for s in case.get("symptoms", [])]
            case_title = case.get("title", "").lower()
            case_category = case.get("category", "").lower()
            
            if (any(symptom in case_symptoms for symptom in symptoms) or
                any(symptom in case_title for symptom in symptoms) or
                any(symptom in case_category for symptom in symptoms)):
                detailed_cases.append(case)
        
        # 結果を整理
        result = {
            "nodes": detailed_nodes[:5],  # 最大5ノード
            "cases": detailed_cases[:5],  # 最大5ケース
            "total_nodes": len(detailed_nodes),
            "total_cases": len(detailed_cases),
            "search_terms": symptoms
        }
        
        return result
    
    def get_diagnostic_summary(self) -> Dict[str, Any]:
        """診断データの概要を取得"""
        summary = {
            "diagnostic_nodes": 0,
            "start_nodes": 0,
            "repair_cases": 0,
            "categories": set(),
            "symptoms": set()
        }
        
        if self.diagnostic_data:
            nodes = self.diagnostic_data.get("nodes", [])
            summary["diagnostic_nodes"] = len(nodes)
            summary["start_nodes"] = len(self.diagnostic_data.get("start_nodes", []))
            
            for node in nodes:
                category = node.get("category", "")
                if category:
                    summary["categories"].add(category)
                
                symptoms = node.get("symptoms", [])
                summary["symptoms"].update(symptoms)
        
        summary["repair_cases"] = len(self.repair_cases)
        
        for case in self.repair_cases:
            category = case.get("category", "")
            if category:
                summary["categories"].add(category)
        
        summary["categories"] = list(summary["categories"])
        summary["symptoms"] = list(summary["symptoms"])
        
        return summary


# グローバルインスタンス
diagnostic_data_manager = DiagnosticDataManager()
