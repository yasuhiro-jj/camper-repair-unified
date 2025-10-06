# streamlit_app.py - Streamlit Cloud用メインファイル
import streamlit as st
import os
import uuid
import re
import json
from data_access.notion_client import NotionClient
import time
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

# 環境変数の手動設定（.envファイルが存在しない場合）
def setup_environment_variables():
    """環境変数を手動で設定"""
    if not os.getenv("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = "sk-proj-DD...4QgA"
    if not os.getenv("NOTION_API_KEY"):
        os.environ["NOTION_API_KEY"] = "ntn_627215...Z9a8"
    if not os.getenv("NOTION_TOKEN"):
        os.environ["NOTION_TOKEN"] = "ntn_627215...Z9a8"
    if not os.getenv("NODE_DB_ID"):
        os.environ["NODE_DB_ID"] = "254e9a7e-e5b7-807e-a703-e18117fa597e"
    if not os.getenv("CASE_DB_ID"):
        os.environ["CASE_DB_ID"] = "256e9a7e-e5b7-8021-924c-d65854d8880f"
    if not os.getenv("ITEM_DB_ID"):
        os.environ["ITEM_DB_ID"] = "254e9a7e-e5b7-80af-bf24-e441079169d5"

# 環境変数を設定
setup_environment_variables()

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage, AIMessage
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_chroma import Chroma

import glob
import config

# 自然な会話機能をインポート
from conversation_memory import NaturalConversationManager

# === RAG機能付きAI相談機能 ===
def initialize_database():
    """データベースを初期化"""
    try:
        main_path = os.path.dirname(os.path.abspath(__file__))
        documents = []
        
        # PDFファイルの読み込み
        pdf_path = os.path.join(main_path, "キャンピングカー修理マニュアル.pdf")
        if os.path.exists(pdf_path):
            loader = PyPDFLoader(pdf_path)
            documents.extend(loader.load())
        
        # テキストファイルの読み込み
        txt_files = glob.glob(os.path.join(main_path, "*.txt"))
        for txt_file in txt_files:
            try:
                loader = TextLoader(txt_file, encoding='utf-8')
                documents.extend(loader.load())
            except Exception as e:
                st.warning(f"テキストファイル {txt_file} の読み込みに失敗: {e}")
        
        if not documents:
            st.warning("ドキュメントが見つかりません")
            return None
        
        # OpenAIの埋め込みモデルを設定
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            st.error("OpenAI APIキーが設定されていません")
        return None

        embeddings_model = OpenAIEmbeddings(openai_api_key=openai_api_key)
        
        # ドキュメントの前処理
        for doc in documents:
            if not isinstance(doc.page_content, str):
                doc.page_content = str(doc.page_content)
        
        # Chromaデータベースを作成
        db = Chroma.from_documents(documents=documents, embedding=embeddings_model)
        
        return db
        
    except Exception as e:
        st.error(f"データベース初期化エラー: {e}")
        return None

def search_relevant_documents(db, query, k=3):
    """関連ドキュメントを検索"""
    try:
        if not db:
            return []
        
        # 類似度検索
        results = db.similarity_search(query, k=k)
        return results
        
    except Exception as e:
        st.error(f"ドキュメント検索エラー: {e}")
        return []

def generate_ai_response_with_rag(prompt):
    """RAG機能付きAIの回答を生成（自然な会話機能統合版）"""
    try:
        # 自然な会話マネージャーの初期化
        conversation_manager = NaturalConversationManager()
        
        # データベースから関連ドキュメントを検索
        db = initialize_database()
        relevant_docs = search_relevant_documents(db, prompt)
        
        # 関連ドキュメントの内容を抽出
        context = ""
        if relevant_docs:
            context = "\n\n".join([doc.page_content for doc in relevant_docs])
        
        # 自然な応答を生成
        with st.spinner("AIが回答を生成中..."):
            response_content = conversation_manager.generate_natural_response(prompt, context)
            
        # 回答をセッションに追加
        st.session_state.messages.append({"role": "assistant", "content": response_content})
        
        # 会話履歴に追加
        conversation_manager.add_message_to_history("user", prompt)
        conversation_manager.add_message_to_history("assistant", response_content)
        
        # 関連ドキュメントの情報を表示
        if relevant_docs:
            st.session_state.last_relevant_docs = relevant_docs
        
    except Exception as e:
        st.error(f"AI回答生成エラー: {e}")
        # エラー時は基本的な応答を提供
        error_response = "申し訳ございません。現在システムに問題が発生しています。お電話でご相談ください。"
        st.session_state.messages.append({"role": "assistant", "content": error_response})

def show_relevant_documents():
    """関連ドキュメントを表示"""
    if "last_relevant_docs" in st.session_state and st.session_state.last_relevant_docs:
        st.markdown("###    参考ドキュメント")
        for i, doc in enumerate(st.session_state.last_relevant_docs, 1):
            source = doc.metadata.get('source', 'unknown')
            filename = os.path.basename(source)
            with st.expander(f"📄 {filename}"):
                st.markdown(doc.page_content[:500] + "..." if len(doc.page_content) > 500 else doc.page_content)

# === Notion連携機能 ===
def initialize_notion_client():
    """Notionクライアントを初期化"""
    try:
        api_key = os.getenv("NOTION_API_KEY")
        if not api_key:
            st.warning("⚠️ NOTION_API_KEYが設定されていません")
            return None
        
        client = NotionClient()
        return client
    except Exception as e:
        st.error(f"❌ Notionクライアントの初期化に失敗: {e}")
        return None

def load_notion_diagnostic_data():
    """Notionから診断データを読み込み"""
    try:
        client = initialize_notion_client()
        if not client:
            st.error("❌ Notionクライアントの初期化に失敗しました")
            return None
        
        node_db_id = os.getenv("NODE_DB_ID")
        if not node_db_id:
            st.error("❌ NODE_DB_IDが設定されていません")
            return None
        
        # Notionから診断ノードを取得
        response = client.databases.query(database_id=node_db_id)
        nodes = response.get("results", [])
        
        if not nodes:
            st.warning("⚠️ 診断ノードが見つかりませんでした")
            return None
        
        # データを変換
        diagnostic_nodes = {}
        start_nodes = {}
        
        for node in nodes:
            properties = node.get("properties", {})
            
            # ノードIDを取得
            node_id_prop = properties.get("ノードID", {})
            node_id = ""
            if node_id_prop.get("type") == "title":
                title_content = node_id_prop.get("title", [])
                if title_content:
                    node_id = title_content[0].get("plain_text", "")
            
            if not node_id:
                continue
            
            # 各プロパティを取得
            question_prop = properties.get("質問内容", {})
            question = ""
            if question_prop.get("type") == "rich_text":
                rich_text_content = question_prop.get("rich_text", [])
                if rich_text_content:
                    question = rich_text_content[0].get("plain_text", "")
            
            result_prop = properties.get("診断結果", {})
            result = ""
            if result_prop.get("type") == "rich_text":
                rich_text_content = result_prop.get("rich_text", [])
                if rich_text_content:
                    result = rich_text_content[0].get("plain_text", "")
            
            category_prop = properties.get("カテゴリ", {})
            category = ""
            if category_prop.get("type") == "rich_text":
                rich_text_content = category_prop.get("rich_text", [])
                if rich_text_content:
                    category = rich_text_content[0].get("plain_text", "")
            
            is_start = properties.get("開始フラグ", {}).get("checkbox", False)
            is_end = properties.get("終端フラグ", {}).get("checkbox", False)
            
            next_nodes_prop = properties.get("次のノード", {})
            next_nodes = []
            if next_nodes_prop.get("type") == "rich_text":
                rich_text_content = next_nodes_prop.get("rich_text", [])
                if rich_text_content:
                    next_nodes_text = rich_text_content[0].get("plain_text", "")
                    next_nodes = [node.strip() for node in next_nodes_text.split(",") if node.strip()]
            
            # ノードデータを作成
            node_data = {
                "question": question,
                "category": category,
                "is_start": is_start,
                "is_end": is_end,
                "next_nodes": next_nodes,
                "result": result
            }
            
            diagnostic_nodes[node_id] = node_data
            
            # 開始ノードを記録
            if is_start:
                start_nodes[category] = node_id
        
        return {
            "diagnostic_nodes": diagnostic_nodes,
            "start_nodes": start_nodes
        }
        
    except Exception as e:
        st.error(f"❌ Notionからの診断データ読み込みに失敗: {e}")
        return None
    
def load_notion_repair_cases():
    """Notionから修理ケースデータを読み込み"""
    client = initialize_notion_client()
    if not client:
        return []
    
    try:
        case_db_id = os.getenv("CASE_DB_ID")
        if not case_db_id:
            st.error("❌ CASE_DB_IDが設定されていません")
            return []
        
        # Notionから修理ケースを取得
        response = client.databases.query(database_id=case_db_id)
        cases = response.get("results", [])
        
        if not cases:
            st.warning("⚠️ 修理ケースが見つかりませんでした")
            return []
        
        repair_cases = []
        
        for case in cases:
            properties = case.get("properties", {})
            
            # ケースIDを取得
            case_id_prop = properties.get("ケースID", {})
            case_id = ""
            if case_id_prop.get("type") == "title":
                title_content = case_id_prop.get("title", [])
                if title_content:
                    case_id = title_content[0].get("plain_text", "")
            
            if not case_id:
                continue
            
            # 各プロパティを取得
            symptoms_prop = properties.get("症状", {})
            symptoms = ""
            if symptoms_prop.get("type") == "rich_text":
                rich_text_content = symptoms_prop.get("rich_text", [])
                if rich_text_content:
                    symptoms = rich_text_content[0].get("plain_text", "")
            
            repair_steps_prop = properties.get("修理手順", {})
            repair_steps = ""
            if repair_steps_prop.get("type") == "rich_text":
                rich_text_content = repair_steps_prop.get("rich_text", [])
                if rich_text_content:
                    repair_steps = rich_text_content[0].get("plain_text", "")
            
            parts_prop = properties.get("必要な部品", {})
            parts = ""
            if parts_prop.get("type") == "rich_text":
                rich_text_content = parts_prop.get("rich_text", [])
                if rich_text_content:
                    parts = rich_text_content[0].get("plain_text", "")
            
            tools_prop = properties.get("必要な工具", {})
            tools = ""
            if tools_prop.get("type") == "rich_text":
                rich_text_content = tools_prop.get("rich_text", [])
                if rich_text_content:
                    tools = rich_text_content[0].get("plain_text", "")
            
            difficulty_prop = properties.get("難易度", {})
            difficulty = ""
            if difficulty_prop.get("type") == "rich_text":
                rich_text_content = difficulty_prop.get("rich_text", [])
                if rich_text_content:
                    difficulty = rich_text_content[0].get("plain_text", "")
            
            # ケースデータを作成
            case_data = {
                "case_id": case_id,
                "symptoms": symptoms,
                "repair_steps": repair_steps,
                "parts": parts,
                "tools": tools,
                "difficulty": difficulty
            }
            
            repair_cases.append(case_data)
        
        return repair_cases
        
    except Exception as e:
        st.error(f"❌ Notionからの修理ケース読み込みに失敗: {e}")
        return []

def run_diagnostic_flow(diagnostic_data, current_node_id=None):
    """症状診断フローを実行"""
    if not diagnostic_data:
        st.error("診断データが読み込めませんでした。")
        return

    diagnostic_nodes = diagnostic_data["diagnostic_nodes"]
    start_nodes = diagnostic_data["start_nodes"]

    # セッション状態の初期化
    if "diagnostic_current_node" not in st.session_state:
        st.session_state.diagnostic_current_node = None
        st.session_state.diagnostic_history = []

    # 開始ノードの選択
    if st.session_state.diagnostic_current_node is None:
        st.markdown("###    症状診断システム")
        st.markdown("**症状のカテゴリを選択してください：**")
        
        # 利用可能なカテゴリを表示
        available_categories = list(start_nodes.keys())
        
        if not available_categories:
            st.warning("⚠️ 利用可能な診断カテゴリがありません")
            return
        
        selected_category = st.selectbox(
            "カテゴリを選択",
            available_categories,
            key="category_select"
        )
        
        if st.button("診断開始", key="start_diagnosis"):
            start_node_id = start_nodes[selected_category]
            st.session_state.diagnostic_current_node = start_node_id
            st.session_state.diagnostic_history = [start_node_id]
            st.rerun()
        
        return

    # 現在のノードを取得
    current_node = diagnostic_nodes.get(st.session_state.diagnostic_current_node)
    if not current_node:
        st.error("診断ノードが見つかりませんでした。")
        return

    # 質問の表示
    question = current_node.get("question", "")
    if question:
        st.markdown(f"### ❓ {question}")
    
    # 終端ノードの場合
    if current_node.get("is_end", False):
        result = current_node.get("result", "")
        if result:
            # 診断結果の表示を強化
            st.markdown("## 🔍 診断結果")
            
            # 診断名の抽出（結果から最初の行を診断名として扱う）
            diagnosis_lines = result.split('\n')
            diagnosis_name = diagnosis_lines[0] if diagnosis_lines else "症状診断"
            
            # 診断結果の詳細表示
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("診断名", diagnosis_name)
            with col2:
                # 確信度の推定（診断結果の長さに基づく簡易的な推定）
                confidence = min(95, max(60, len(result) // 10 + 60))
                st.metric("確信度", f"{confidence}%")
            with col3:
                # 緊急度の判定（キーワードベース）
                urgency_keywords = ["緊急", "危険", "即座", "停止", "故障"]
                urgency = "緊急" if any(keyword in result for keyword in urgency_keywords) else "要注意"
                st.metric("緊急度", urgency)
            
            # 診断結果の詳細
            st.markdown("### 📋 診断詳細")
            st.markdown(result)
            
            # 費用目安の表示
            st.markdown("### 💰 費用目安")
            cost_info = current_node.get("cost_estimation", "")
            if cost_info:
                st.markdown(cost_info)
            else:
                # デフォルトの費用目安（カテゴリに基づく）
                category = current_node.get("category", "")
                default_costs = {
                    "バッテリー": "部品代: 15,000-25,000円\n工賃: 5,000-10,000円\n合計: 20,000-35,000円",
                    "エアコン": "部品代: 30,000-80,000円\n工賃: 15,000-30,000円\n合計: 45,000-110,000円",
                    "電装系": "部品代: 5,000-20,000円\n工賃: 3,000-8,000円\n合計: 8,000-28,000円",
                    "タイヤ": "部品代: 20,000-40,000円\n工賃: 2,000-5,000円\n合計: 22,000-45,000円"
                }
                default_cost = default_costs.get(category, "部品代: 10,000-30,000円\n工賃: 5,000-15,000円\n合計: 15,000-45,000円")
                st.markdown(default_cost)
        
        # 関連する修理ケースを表示
        st.markdown("### 📋 関連する修理ケース")
        repair_cases = load_notion_repair_cases()
        
        if repair_cases:
            # 症状に基づいて関連ケースをフィルタリング
            category = current_node.get("category", "")
            related_cases = [case for case in repair_cases if category.lower() in case.get("symptoms", "").lower()]
            
            if related_cases:
                for case in related_cases[:3]:  # 上位3件を表示
                    with st.expander(f"🔧 {case['case_id']}: {case['symptoms'][:50]}..."):
                        st.markdown(f"**症状:** {case['symptoms']}")
                        st.markdown(f"**修理手順:** {case['repair_steps']}")
                        st.markdown(f"**必要な部品:** {case['parts']}")
                        st.markdown(f"**必要な工具:** {case['tools']}")
                        st.markdown(f"**難易度:** {case['difficulty']}")
                        
                        # 費用情報がある場合
                        if 'cost' in case and case['cost']:
                            st.markdown(f"**費用目安:** {case['cost']}")
            else:
                st.info("関連する修理ケースが見つかりませんでした。")
        else:
            st.info("修理ケースデータを読み込めませんでした。")
        
        # 診断をリセット
        if st.button("新しい診断を開始", key="reset_diagnosis"):
            st.session_state.diagnostic_current_node = None
            st.session_state.diagnostic_history = []
            st.rerun()
        
        return

    # 次のノードへの選択肢
    next_nodes = current_node.get("next_nodes", [])
    if len(next_nodes) >= 2:
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("はい", key=f"yes_{current_node_id}"):
                next_node_id = next_nodes[0]
                st.session_state.diagnostic_current_node = next_node_id
                st.session_state.diagnostic_history.append(next_node_id)
                st.rerun()
        
        with col2:
            if st.button("いいえ", key=f"no_{current_node_id}"):
                next_node_id = next_nodes[1] if len(next_nodes) > 1 else next_nodes[0]
                st.session_state.diagnostic_current_node = next_node_id
                st.session_state.diagnostic_history.append(next_node_id)
                st.rerun()
    elif len(next_nodes) == 1:
        if st.button("次へ", key=f"next_{current_node_id}"):
            next_node_id = next_nodes[0]
            st.session_state.diagnostic_current_node = next_node_id
            st.session_state.diagnostic_history.append(next_node_id)
            st.rerun()

    # 診断履歴の表示
    if st.session_state.diagnostic_history:
        st.markdown("---")
        st.markdown("**📝 診断履歴**")
        for i, node_id in enumerate(st.session_state.diagnostic_history):
            node = diagnostic_nodes.get(node_id, {})
            question = node.get("question", "")
            if question:
                st.markdown(f"{i+1}. {question}")

# === メインアプリケーション ===
def main():
    st.set_page_config(
        page_title="キャンピングカー修理専門 AIチャット",
        page_icon="  ",
        layout="wide"
    )

    # カスタムCSS
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 15px;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .feature-banner {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin: 20px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .feature-list {
        background: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 20px 0;
    }
    
    .quick-question {
        background: white;
        border: 2px solid #e9ecef;
        border-radius: 8px;
        padding: 10px 15px;
        margin: 5px;
        cursor: pointer;
        transition: all 0.3s ease;
        display: inline-block;
    }
    
    .quick-question:hover {
        border-color: #667eea;
        background: #f8f9fa;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: white;
        border-radius: 8px;
        color: #666;
        font-weight: 500;
        padding: 12px 24px;
        border: 2px solid transparent;
        transition: all 0.3s ease;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #667eea;
        color: white;
        border-color: #667eea;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .stTabs [aria-selected="false"]:hover {
        background-color: #e8f4fd;
        border-color: #667eea;
        color: #667eea;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # ヘッダー
    st.markdown("""
    <div class="main-header">
        <h1>🔧 キャンピングカー修理専門 AIチャット</h1>
        <p>経験豊富なAIがキャンピングカーの修理について詳しくお答えします</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 修理アドバイスセンターへのリンク
    st.markdown("""
    <div style="text-align: center; margin: 20px 0;">
        <button onclick="window.open('templates/templates/repair_advice_center.html', '_blank')" 
                style="display: inline-block; background: linear-gradient(45deg, #dc3545, #ff6b6b); 
                       color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; 
                       font-weight: bold; box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3); 
                       border: none; cursor: pointer; font-size: 16px;">
            🔧 修理専門アドバイスセンター
        </button>
        <p style="margin-top: 10px; color: #666; font-size: 14px;">
            具体的な修理費相場、代替品、詳細な修理手順をご提供
        </p>
    </div>
    """, unsafe_allow_html=True)

    # サイドバーに修理アドバイスセンターへのリンクを追加
    with st.sidebar:
        st.markdown("### 🔧 修理専門ツール")
        st.markdown("""
        <button onclick="window.open('templates/templates/repair_advice_center.html', '_blank')" 
                style="display: block; background: linear-gradient(45deg, #dc3545, #ff6b6b); 
                       color: white; padding: 12px 20px; text-decoration: none; border-radius: 20px; 
                       font-weight: bold; text-align: center; box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3); 
                       border: none; cursor: pointer; width: 100%; font-size: 14px; margin: 10px 0;">
            🔧 修理専門アドバイスセンター
        </button>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📋 機能説明")
        st.info("""
        **AIチャット相談**: 一般的な修理相談
        
        **対話式症状診断**: 症状から原因を特定
        
        **修理アドバイスセンター**: 詳細な修理手順・費用相場
        """)

    # 3つのタブを作成
    tab1, tab2, tab3 = st.tabs(["   AIチャット相談", "🔍 対話式症状診断", "🔧 修理アドバイスセンター"])
    
    with tab1:
        # AIチャット相談の説明バナー
        st.markdown("""
        <div class="feature-banner">
            <h3>💬 AIチャット相談</h3>
            <p>経験豊富なAIがキャンピングカーの修理について詳しくお答えします。自由に質問してください。</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 機能説明
        st.markdown("""
        <div class="feature-list">
            <h4>🎯 この機能でできること</h4>
            <ul>
                <li>🔧 修理方法の詳細な説明</li>
                <li>🛠️ 工具や部品の選び方</li>
                <li>⚠️ 安全な作業手順の案内</li>
                <li>   定期メンテナンスのアドバイス</li>
                <li>🔍 トラブルシューティングのヒント</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # 修理アドバイスセンターへの案内
        st.markdown("""
        <div style="background: #fff3cd; border: 1px solid #ffeaa7; border-radius: 10px; padding: 15px; margin: 20px 0;">
            <h4 style="color: #856404; margin-top: 0;">💡 より詳細な情報が必要ですか？</h4>
            <p style="color: #856404; margin-bottom: 10px;">
                具体的な修理費用相場、代替品情報、詳細な修理手順をお探しの場合は、
                <strong>修理専門アドバイスセンター</strong>をご利用ください。
            </p>
            <button onclick="window.open('templates/repair_advice_center.html', '_blank')" 
               style="display: inline-block; background: linear-gradient(45deg, #dc3545, #ff6b6b); 
                       color: white; padding: 10px 20px; text-decoration: none; border-radius: 20px; 
                       font-weight: bold; box-shadow: 0 2px 10px rgba(220, 53, 69, 0.3); 
                       border: none; cursor: pointer; font-size: 14px;">
                🔧 修理専門アドバイスセンターへ
            </button>
        </div>
        """, unsafe_allow_html=True)
        
        # よくある質問ボタン
        st.markdown("### 💡 よくある質問 (クリックで質問)")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔋 バッテリー上がり", key="battery_question"):
                question = "バッテリーが上がってしまいました。どうすればいいですか？"
                st.session_state.messages.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant", avatar="https://camper-repair.net/blog/wp-content/uploads/2025/05/dummy_staff_01-150x138-1.png"):
                    with st.spinner("   修理アドバイスを生成中..."):
                        generate_ai_response_with_rag(question)
                st.rerun()
        
            if st.button("   水道ポンプ", key="water_pump_question"):
                question = "水道ポンプが動きません。原因と対処法を教えてください。"
                st.session_state.messages.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant", avatar="https://camper-repair.net/blog/wp-content/uploads/2025/05/dummy_staff_01-150x138-1.png"):
                    with st.spinner("   修理アドバイスを生成中..."):
                        generate_ai_response_with_rag(question)
                st.rerun()
        
        with col2:
            if st.button("🔥 ガスコンロ", key="gas_stove_question"):
                question = "ガスコンロの火がつきません。どうすればいいですか？"
                st.session_state.messages.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant", avatar="https://camper-repair.net/blog/wp-content/uploads/2025/05/dummy_staff_01-150x138-1.png"):
                    with st.spinner("   修理アドバイスを生成中..."):
                        generate_ai_response_with_rag(question)
                st.rerun()
    
            if st.button("❄️ 冷蔵庫", key="refrigerator_question"):
                question = "冷蔵庫が冷えません。原因と対処法を教えてください。"
                st.session_state.messages.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant", avatar="https://camper-repair.net/blog/wp-content/uploads/2025/05/dummy_staff_01-150x138-1.png"):
                    with st.spinner("   修理アドバイスを生成中..."):
                        generate_ai_response_with_rag(question)
                st.rerun()
        
        with col3:
            if st.button("📋 定期点検", key="maintenance_question"):
                question = "キャンピングカーの定期点検について教えてください。"
                st.session_state.messages.append({"role": "user", "content": question})
                with st.chat_message("user"):
                    st.markdown(question)
                with st.chat_message("assistant", avatar="https://camper-repair.net/blog/wp-content/uploads/2025/05/dummy_staff_01-150x138-1.png"):
                    with st.spinner("   修理アドバイスを生成中..."):
                        generate_ai_response_with_rag(question)
                st.rerun()
        
            if st.button("🆕 新しい会話", key="new_conversation"):
                # 自然な会話マネージャーで会話をクリア
                conversation_manager = NaturalConversationManager()
                conversation_manager.clear_conversation()
                st.rerun()
        
        # セッション状態の初期化
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # 会話履歴の表示
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # 会話の要約表示（会話がある場合のみ）
        if st.session_state.messages:
            with st.expander("💬 会話の要約", expanded=False):
                conversation_manager = NaturalConversationManager()
                summary = conversation_manager.get_conversation_summary()
                st.info(f"📝 {summary}")
                
                # 会話の統計情報
                user_messages = [msg for msg in st.session_state.messages if msg["role"] == "user"]
                assistant_messages = [msg for msg in st.session_state.messages if msg["role"] == "assistant"]
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("ユーザーメッセージ数", len(user_messages))
                with col2:
                    st.metric("AI応答数", len(assistant_messages))
                with col3:
                    st.metric("総メッセージ数", len(st.session_state.messages))
        
        # ユーザー入力
        if prompt := st.chat_input("キャンピングカーの修理について質問してください..."):
            # ユーザーメッセージを追加
            st.session_state.messages.append({"role": "user", "content": prompt})
        
            with st.chat_message("user"):
                st.markdown(prompt)
        
            # AIの回答を生成（RAG機能付き）
            with st.chat_message("assistant", avatar="https://camper-repair.net/blog/wp-content/uploads/2025/05/dummy_staff_01-150x138-1.png"):
                with st.spinner("   修理アドバイスを生成中..."):
                    generate_ai_response_with_rag(prompt)

        # 関連ドキュメントの表示
        show_relevant_documents()
    
    with tab2:
        # 症状診断の説明
        st.markdown("""
        <div class="feature-banner">
            <h3>🔍 対話式症状診断</h3>
            <p>症状を選択して、段階的に診断を行い、最適な対処法をご案内します。</p>
        </div>
        """, unsafe_allow_html=True)
        
        # 修理アドバイスセンターへの案内
        st.markdown("""
        <div style="background: #d1ecf1; border: 1px solid #bee5eb; border-radius: 10px; padding: 15px; margin: 20px 0;">
            <h4 style="color: #0c5460; margin-top: 0;">🔧 診断後の詳細情報</h4>
            <p style="color: #0c5460; margin-bottom: 10px;">
                診断結果に基づいて、具体的な修理手順、必要な部品、費用相場などの詳細情報を
                <strong>修理専門アドバイスセンター</strong>でご確認いただけます。
            </p>
            <button onclick="window.open('templates/repair_advice_center.html', '_blank')" 
               style="display: inline-block; background: linear-gradient(45deg, #dc3545, #ff6b6b); 
                       color: white; padding: 10px 20px; text-decoration: none; border-radius: 20px; 
                       font-weight: bold; box-shadow: 0 2px 10px rgba(220, 53, 69, 0.3); 
                       border: none; cursor: pointer; font-size: 14px;">
                🔧 修理専門アドバイスセンターへ
            </button>
        </div>
        """, unsafe_allow_html=True)
        
        # 症状診断システム
        st.markdown("---")
        st.markdown("### 🔍 デバッグ情報（常時表示）")
        
        # Notion関連の環境変数をチェック
        notion_api_key = os.getenv("NOTION_API_KEY")
        notion_token = os.getenv("NOTION_TOKEN")
        node_db_id = os.getenv("NODE_DB_ID")
        case_db_id = os.getenv("CASE_DB_ID")
        
        st.markdown("**環境変数チェック:**")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"NOTION_API_KEY: {'✅ 設定済み' if notion_api_key else '❌ 未設定'}")
            st.write(f"NODE_DB_ID: {'✅ 設定済み' if node_db_id else '❌ 未設定'}")
        with col2:
            st.write(f"NOTION_TOKEN: {'✅ 設定済み' if notion_token else '❌ 未設定'}")
            st.write(f"CASE_DB_ID: {'✅ 設定済み' if case_db_id else '❌ 未設定'}")
        
        st.markdown("**詳細情報:**")
        # 使用可能なAPIキーを表示
        api_key = notion_api_key or notion_token
        if api_key:
            st.write(f"✅ 使用可能なAPIキー: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")
        else:
            st.write("❌ Notion APIキーが設定されていません")
            st.info("NOTION_API_KEYまたはNOTION_TOKENを設定してください")
        
        # データベースIDの表示
        if node_db_id:
            st.write(f"✅ 診断フローDB ID: {node_db_id}")
        else:
            st.write("❌ NODE_DB_IDが設定されていません")
            st.info("診断フローデータベースのIDを設定してください")
        
        if case_db_id:
            st.write(f"✅ 修理ケースDB ID: {case_db_id}")
        else:
            st.write("❌ CASE_DB_IDが設定されていません")
            st.info("修理ケースデータベースのIDを設定してください")
        
        # .envファイルの存在確認
        env_exists = os.path.exists('.env')
        st.markdown("**ファイル確認:**")
        st.write(f".envファイル: {'✅ 存在' if env_exists else '❌ 存在しない'}")
        if not env_exists:
            st.info("env_example.txtを.envにリネームして設定してください")
        
        st.markdown("---")
        st.markdown("### 🔧 診断システム")
        
        with st.spinner("診断データを読み込み中..."):
            notion_data = load_notion_diagnostic_data()
        
        if notion_data:
            st.success("✅ 診断データの読み込みが完了しました")
            run_diagnostic_flow(notion_data)
        else:
            st.error("❌ 診断データの読み込みに失敗しました。")
            st.info("上記のデバッグ情報を確認して環境変数を設定してください。")
            
            # デバッグ情報を表示
            st.markdown("### 🔍 デバッグ情報")
            api_key = os.getenv("NOTION_API_KEY") or os.getenv("NOTION_TOKEN")
            node_db_id = os.getenv("NODE_DB_ID")
            
            st.write(f"APIキー: {'✅ 設定済み' if api_key else '❌ 未設定'}")
            st.write(f"NODE_DB_ID: {'✅ 設定済み' if node_db_id else '❌ 未設定'}")
            
            if api_key and node_db_id:
                st.info("環境変数は設定されています。Notionクライアントの接続を確認してください。")
    
    with tab3:
        # 修理アドバイスセンターの説明バナー
        st.markdown("""
        <div class="feature-banner">
            <h3>🔧 修理専門アドバイスセンター</h3>
            <p>具体的な修理費用相場、代替品情報、詳細な修理手順をご提供します。</p>
        </div>
        """, unsafe_allow_html=True)
        
        # フル機能版への遷移ボタン
        st.markdown("""
        <div style="text-align: center; margin: 20px 0;">
            <button onclick="window.open('templates/repair_advice_center.html', '_blank')" 
                    style="display: inline-block; background: linear-gradient(45deg, #dc3545, #ff6b6b); 
                           color: white; padding: 15px 30px; text-decoration: none; border-radius: 25px; 
                           font-weight: bold; box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3); 
                           border: none; cursor: pointer; font-size: 16px;">
                🚀 フル機能版を開く
            </button>
            <p style="margin-top: 10px; color: #666; font-size: 14px;">
                より詳細な機能とインタラクティブな検索システムをご利用いただけます
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # 修理アドバイスセンターの機能説明
        st.markdown("""
        <div class="feature-list">
            <h4>🎯 この機能でできること</h4>
            <ul>
                <li>💰 修理費用の相場情報</li>
                <li>🛠️ 必要な工具と部品の詳細</li>
                <li>📋 ステップバイステップの修理手順</li>
                <li>⚠️ 安全な作業方法の案内</li>
                <li>🔍 トラブルシューティングのヒント</li>
                <li>📞 専門業者への相談方法</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # 検索機能
        st.markdown("### 🔍 修理内容を検索")
        
        # 検索入力
        repair_query = st.text_input(
            "修理したい内容や症状を入力してください",
            placeholder="例：バッテリーが上がらない、エアコンが効かない、雨漏りがする"
        )
        
        if st.button("🔍 修理情報を検索", type="primary"):
            if repair_query:
                st.success(f"「{repair_query}」の修理情報を検索中...")
                
                # 検索結果の表示（サンプル）
                st.markdown("### 📋 検索結果")
                
                # カテゴリ別の修理情報を表示
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 💰 修理費用相場")
                    st.info("""
                    **軽微な修理**: 5,000円～15,000円
                    **中程度の修理**: 15,000円～50,000円
                    **大規模な修理**: 50,000円以上
                    """)
                
                with col2:
                    st.markdown("#### ⏰ 作業時間目安")
                    st.info("""
                    **簡単な修理**: 30分～2時間
                    **標準的な修理**: 2時間～半日
                    **複雑な修理**: 半日～数日
                    """)
                
                # 必要な工具と部品
                st.markdown("#### 🛠️ 必要な工具・部品")
                st.markdown("""
                **基本工具セット**:
                - ドライバーセット
                - レンチセット
                - テスター
                - マルチメーター
                
                **専門工具**:
                - キャンピングカー専用工具
                - 配線用工具
                - 配管用工具
                """)
                
                # 修理手順
                st.markdown("#### 📋 修理手順")
                st.markdown("""
                1. **安全確認**: 電源を切り、安全な環境を確保
                2. **症状確認**: 問題の詳細を特定
                3. **部品確認**: 必要な部品と工具を準備
                4. **修理実行**: 手順に従って修理
                5. **動作確認**: 修理後の動作テスト
                6. **最終確認**: 安全面の最終チェック
                """)
                
                # 注意事項
                st.markdown("#### ⚠️ 注意事項")
                st.warning("""
                - 電気関連の修理は専門知識が必要です
                - ガス関連の作業は資格が必要な場合があります
                - 不安な場合は専門業者にご相談ください
                """)
                
            else:
                st.warning("検索キーワードを入力してください")
        
        # よくある修理カテゴリ
        st.markdown("### 📂 よくある修理カテゴリ")
        
        categories = {
            "🔋 バッテリー": "バッテリー上がり、充電不良、寿命",
            "❄️ 冷蔵庫": "冷えない、異音、電源問題",
            "🌡️ エアコン": "冷えない、温まらない、異音",
            "💧 給水・排水": "水が出ない、排水不良、ポンプ故障",
            "⚡ 電気系統": "ヒューズ切れ、配線不良、LED故障",
            "🚪 ドア・窓": "開閉不良、ガラス破損、シール劣化",
            "🚗 車体": "雨漏り、錆、外装破損",
            "🛏️ 家具": "固定不良、破損、調整不良"
        }
        
        cols = st.columns(4)
        for i, (category, description) in enumerate(categories.items()):
            with cols[i % 4]:
                if st.button(category, key=f"category_{i}"):
                    st.info(f"**{category}**\n{description}")
        
        # 専門業者への相談案内
        st.markdown("### 📞 専門業者への相談")
        st.markdown("""
        <div style="background: #e8f4fd; border: 1px solid #667eea; border-radius: 10px; padding: 20px; margin: 20px 0;">
            <h4 style="color: #667eea; margin-top: 0;">🔧 修理が困難な場合</h4>
            <p style="color: #333; margin-bottom: 15px;">
                複雑な修理や専門知識が必要な作業については、
                キャンピングカー専門の修理業者にご相談することをお勧めします。
            </p>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                <span style="background: #667eea; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">
                    🏢 キャンピングカー専門店
                </span>
                <span style="background: #667eea; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">
                    🔧 自動車整備工場
                </span>
                <span style="background: #667eea; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">
                    ⚡ 電気工事店
                </span>
                <span style="background: #667eea; color: white; padding: 5px 10px; border-radius: 15px; font-size: 12px;">
                    💧 配管工事店
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 
