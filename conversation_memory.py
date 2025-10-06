# conversation_memory.py - 自然な会話機能の実装
import streamlit as st
from langchain.memory import ConversationBufferWindowMemory, ConversationSummaryMemory
from langchain.memory.chat_message_histories import StreamlitChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
import os
import re
from datetime import datetime
from typing import List, Dict, Any

class NaturalConversationManager:
    """自然な会話を管理するクラス"""
    
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            st.error("OpenAI APIキーが設定されていません")
            return
        
        # 会話メモリの初期化
        if "conversation_memory" not in st.session_state:
            st.session_state.conversation_memory = ConversationBufferWindowMemory(
                k=10,  # 最近の10メッセージを保持
                return_messages=True
            )
        
        # 会話履歴の初期化
        if "conversation_history" not in st.session_state:
            st.session_state.conversation_history = []
        
        # LLMの初期化
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0.8,
            openai_api_key=self.openai_api_key
        )
    
    def analyze_conversation_context(self) -> str:
        """会話の文脈を分析"""
        if not st.session_state.conversation_history:
            return "初回の会話です"
        
        # 最近の会話のトピックを分析
        recent_topics = []
        for message in st.session_state.conversation_history[-5:]:  # 最近の5つのメッセージ
            content = message.get("content", "")
            # トピックの抽出
            if any(word in content for word in ['バッテリー', '電池']):
                recent_topics.append('バッテリー関連')
            elif any(word in content for word in ['雨漏り', '水漏れ']):
                recent_topics.append('雨漏り関連')
            elif any(word in content for word in ['エアコン', '冷房', '暖房']):
                recent_topics.append('エアコン関連')
            elif any(word in content for word in ['ガス', 'コンロ', 'ヒーター']):
                recent_topics.append('ガス関連')
            elif any(word in content for word in ['トイレ', '水洗']):
                recent_topics.append('トイレ関連')
        
        return f"最近の話題: {', '.join(set(recent_topics)) if recent_topics else 'なし'}"
    
    def analyze_user_intent(self, user_message: str) -> List[str]:
        """ユーザーの意図を分析"""
        intent_patterns = {
            '相談': ['相談', '困って', '問題', '故障', '壊れた', '動かない'],
            '来店予約': ['行きたい', '来店', '予約', '時間', 'いつ', '金曜日', '土曜日'],
            '電話相談': ['電話', 'かけたい', '連絡', '問い合わせ'],
            '価格確認': ['いくら', '費用', '価格', '料金', 'コスト'],
            '緊急': ['急いで', '緊急', 'すぐに', '今すぐ', '至急'],
            '診断': ['診断', '原因', 'なぜ', 'どうして'],
            '修理手順': ['やり方', '方法', '手順', 'どうやって']
        }
        
        detected_intents = []
        for intent, patterns in intent_patterns.items():
            if any(pattern in user_message for pattern in patterns):
                detected_intents.append(intent)
        
        return detected_intents if detected_intents else ['一般的な質問']
    
    def handle_specific_queries(self, user_message: str) -> str:
        """特定の質問パターンに対する自然な応答"""
        
        # 来店予約の質問
        if any(word in user_message for word in ['行きたい', '来店', '予約', '金曜日', '土曜日', '時間']):
            return """
申し訳ございませんが、AIアシスタントでは来店予約の詳細な調整はできません。

📞 **お電話でのご相談をお勧めします**
- 営業時間: 平日 9:00-18:00、土曜 9:00-17:00
- 電話番号: 03-XXXX-XXXX
- スタッフが直接お時間の調整をさせていただきます

💡 **事前にご準備いただくとスムーズです**
- お車の年式・型式
- 具体的な症状やご相談内容
- ご希望の日時（第1希望、第2希望など）

お電話の際は「AI相談で事前に症状をお聞きしました」とお伝えいただければ、スムーズにご案内できます。
"""
        
        # 緊急の質問
        elif any(word in user_message for word in ['緊急', '急いで', 'すぐに', '今すぐ', '至急']):
            return """
🚨 **緊急のご相談ですね**

まずは落ち着いて、以下の点をご確認ください：

1. **安全確認**
   - お怪我はありませんか？
   - 車両の安全な場所への移動は可能ですか？

2. **緊急連絡先**
   - 24時間対応: 03-XXXX-XXXX（緊急時専用）
   - 通常営業: 03-XXXX-XXXX

3. **応急処置**
   - 可能な範囲での応急処置方法をお教えします
   - 安全を最優先に行動してください

お電話いただければ、緊急度に応じて最適な対応をご案内いたします。
"""
        
        # 電話相談の希望
        elif any(word in user_message for word in ['電話', 'かけたい', '連絡', '問い合わせ']):
            return """
📞 **お電話でのご相談について**

お電話でのご相談を承っております：

**営業時間**
- 平日: 9:00-18:00
- 土曜: 9:00-17:00
- 日曜・祝日: 休業

**お電話番号**
- 03-XXXX-XXXX

**お電話の際のご準備**
- お車の年式・型式
- 症状の詳細
- いつから症状が出ているか
- これまでの対処法

AI相談でお聞きした内容もお伝えいただければ、よりスムーズにご案内できます。
"""
        
        return None  # 特定のパターンに該当しない場合は通常の処理
    
    def create_natural_response_prompt(self, user_message: str, context_info: str = "") -> str:
        """自然な会話のためのプロンプトを生成"""
        
        # 会話の文脈を分析
        conversation_context = self.analyze_conversation_context()
        
        # ユーザーの意図を分析
        user_intent = self.analyze_user_intent(user_message)
        
        # 自然な応答のためのプロンプト
        natural_prompt = f"""
あなたはキャンピングカー修理の専門スタッフです。以下の指示に従って自然で親しみやすい回答をしてください：

【会話の文脈】
{conversation_context}

【ユーザーの意図】
{', '.join(user_intent)}

【回答のガイドライン】
1. 親しみやすく、丁寧な口調で回答してください
2. ユーザーの質問に直接答えるだけでなく、関連する情報も提供してください
3. 必要に応じて、電話での相談や来店を案内してください
4. 専門用語は分かりやすく説明してください
5. 費用目安があれば必ず含めてください
6. 安全を最優先にしたアドバイスを心がけてください
7. 自然な会話の流れを保ってください

【ユーザーの質問】
{user_message}

【関連情報】
{context_info}

【回答例の参考】
- 「はい、その症状についてお答えしますね」
- 「お困りのようですね、一緒に解決していきましょう」
- 「まずは安全確認から始めましょう」
- 「費用の目安は○○円程度です」
- 「詳しくはお電話でご相談ください」
"""
        return natural_prompt
    
    def generate_natural_response(self, user_message: str, context_info: str = "") -> str:
        """自然な応答を生成"""
        
        # 特定の質問パターンのチェック
        specific_response = self.handle_specific_queries(user_message)
        if specific_response:
            return specific_response
        
        # 自然な応答のプロンプトを生成
        prompt = self.create_natural_response_prompt(user_message, context_info)
        
        # 会話履歴をメッセージ形式に変換
        messages = []
        
        # システムメッセージを追加
        messages.append(HumanMessage(content=prompt))
        
        # 応答生成
        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            st.error(f"自然な応答生成エラー: {e}")
            return "申し訳ございません。現在システムに問題が発生しています。お電話でご相談ください。"
    
    def add_message_to_history(self, role: str, content: str):
        """会話履歴にメッセージを追加"""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        st.session_state.conversation_history.append(message)
        
        # 会話メモリにも追加
        if role == "user":
            st.session_state.conversation_memory.chat_memory.add_user_message(content)
        elif role == "assistant":
            st.session_state.conversation_memory.chat_memory.add_ai_message(content)
    
    def get_conversation_summary(self) -> str:
        """会話の要約を取得"""
        if not st.session_state.conversation_history:
            return "まだ会話がありません"
        
        # 最近の会話を要約
        recent_messages = st.session_state.conversation_history[-5:]
        topics = []
        for msg in recent_messages:
            content = msg.get("content", "")
            if any(word in content for word in ['バッテリー', '電池']):
                topics.append('バッテリー関連')
            elif any(word in content for word in ['雨漏り', '水漏れ']):
                topics.append('雨漏り関連')
            # 他のトピックも追加可能
        
        return f"最近の話題: {', '.join(set(topics)) if topics else '一般的な相談'}"
    
    def clear_conversation(self):
        """会話履歴をクリア"""
        st.session_state.conversation_history = []
        st.session_state.conversation_memory.clear()
        st.session_state.messages = []
