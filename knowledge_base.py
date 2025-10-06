#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
知識ベース管理機能を提供するモジュール
"""

import os
import glob
import streamlit as st
from functools import lru_cache
from typing import Dict, List, Optional, Any


class KnowledgeBaseManager:
    """知識ベースの管理クラス"""
    
    def __init__(self):
        self.knowledge_base = {}
        self._load_knowledge_base()
    
    # @lru_cache(maxsize=1)  # 一時的に無効化
    def load_knowledge_base(self):
        """JSONファイルとテキストファイルから知識ベースを読み込み（改良版）"""
        knowledge_base = {}
        
        # まずJSONファイルから読み込み
        json_file = "category_definitions.json"
        print(f"🔍 JSONファイル確認: {json_file}")
        if os.path.exists(json_file):
            print(f"✅ JSONファイル存在: {json_file}")
            try:
                import json
                with open(json_file, 'r', encoding='utf-8') as f:
                    category_data = json.load(f)
                print(f"📚 JSONファイル読み込み成功: {len(category_data.get('categories', {}))}件のカテゴリ")
                
                # JSONデータから知識ベースを構築
                for category_name, category_info in category_data.get("categories", {}).items():
                    content_parts = []
                    
                    # カテゴリ情報を追加
                    content_parts.append(f"# {category_name}")
                    content_parts.append(f"アイコン: {category_info.get('icon', '')}")
                    content_parts.append(f"ID: {category_info.get('id', '')}")
                    
                    # キーワード情報を追加
                    keywords = category_info.get("keywords", {})
                    if keywords.get("primary"):
                        content_parts.append(f"主要キーワード: {', '.join(keywords['primary'])}")
                    if keywords.get("secondary"):
                        content_parts.append(f"関連キーワード: {', '.join(keywords['secondary'])}")
                    
                    # 修理費用情報を追加
                    repair_costs = category_info.get("repair_costs", [])
                    if repair_costs:
                        content_parts.append("\n## 修理費用目安")
                        for cost_item in repair_costs:
                            content_parts.append(f"- {cost_item.get('item', '')}: {cost_item.get('price_range', '')}")
                    
                    # フォールバック手順を追加
                    fallback_steps = category_info.get("fallback_steps", [])
                    if fallback_steps:
                        content_parts.append("\n## 基本修理手順")
                        for i, step in enumerate(fallback_steps, 1):
                            content_parts.append(f"{i}. {step}")
                    
                    # テキストファイルの内容も追加（存在する場合）
                    files = category_info.get("files", {})
                    text_file = files.get("text_content")
                    if text_file and os.path.exists(text_file):
                        try:
                            with open(text_file, 'r', encoding='utf-8') as f:
                                text_content = f.read()
                            content_parts.append(f"\n## 詳細情報\n{text_content}")
                        except Exception as e:
                            print(f"Warning: テキストファイル読み込みエラー {text_file}: {e}")
                    
                    knowledge_base[category_name] = '\n'.join(content_parts)
                    print(f"✅ JSONから読み込み: {category_name}")
                    
                    # デバッグ: バッテリーカテゴリの内容を確認
                    if category_name == "バッテリー":
                        print(f"🔋 バッテリーカテゴリの構築された内容:")
                        print(f"  - 文字数: {len(knowledge_base[category_name])}")
                        print(f"  - 最初の200文字: {knowledge_base[category_name][:200]}...")
                        print(f"  - '充電' を含むか: {'充電' in knowledge_base[category_name]}")
                        print(f"  - 'バッテリー' を含むか: {'バッテリー' in knowledge_base[category_name]}")
                    
            except Exception as e:
                print(f"❌ JSONファイル読み込みエラー: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ JSONファイルが見つかりません: {json_file}")
            print(f"🔍 現在のディレクトリ: {os.getcwd()}")
            print(f"📂 ディレクトリ内のファイル:")
            try:
                import glob
                json_files = glob.glob("*.json")
                print(f"  - JSONファイル: {json_files}")
                txt_files = glob.glob("*.txt")
                print(f"  - TXTファイル: {txt_files[:10]}...")  # 最初の10個
            except Exception as e:
                print(f"  - ファイル一覧取得エラー: {e}")
        
        # テキストファイルも追加で読み込み（JSONにない場合）
        priority_files = [
            "バッテリー.txt", "エアコン.txt", "トイレ.txt", "雨漏り.txt",
            "インバーター.txt", "水道ポンプ.txt", "冷蔵庫.txt"
        ]
        
        for file_name in priority_files:
            if os.path.exists(file_name):
                try:
                    with open(file_name, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    category = file_name.replace('.txt', '').replace('　', '・')
                    if category not in knowledge_base:  # JSONにない場合のみ追加
                        knowledge_base[category] = content
                        print(f"✅ テキストファイルから読み込み: {category}")
                    
                except Exception as e:
                    print(f"Warning: ファイル読み込みエラー {file_name}: {e}")
        
        return knowledge_base
    
    def _load_knowledge_base(self):
        """知識ベースを初期化"""
        print("🔄 知識ベースを初期化中...")
        try:
            self.knowledge_base = self.load_knowledge_base()
            print(f"📚 知識ベース読み込み完了: {len(self.knowledge_base)}件のカテゴリ")
        except Exception as e:
            print(f"❌ 知識ベース読み込みエラー: {e}")
            import traceback
            traceback.print_exc()
            self.knowledge_base = {}
        
        if len(self.knowledge_base) == 0:
            print("❌ 警告: 知識ベースが空です！")
            print("🔍 JSONファイルの存在確認...")
            import os
            json_file = "category_definitions.json"
            if os.path.exists(json_file):
                print(f"✅ JSONファイル存在: {json_file}")
                print(f"📄 ファイルサイズ: {os.path.getsize(json_file)} bytes")
            else:
                print(f"❌ JSONファイルが見つかりません: {json_file}")
        else:
            for category in list(self.knowledge_base.keys())[:5]:  # 最初の5つを表示
                print(f"  - {category}")
    
    def extract_relevant_knowledge(self, query: str) -> List[str]:
        """クエリに関連する知識を抽出（改善版）"""
        query_lower = query.lower()
        relevant_content = []
        
        # 拡張されたキーワードマッピング
        keyword_mapping = {
            "インバーター": ["インバーター", "inverter", "dc-ac", "正弦波", "電源変換", "ac", "dc", "電源"],
            "バッテリー": [
                "バッテリー", "battery", "サブバッテリー", "充電", "電圧", "電圧低下", "充電器",
                "充電されない", "充電できない", "走行充電", "充電ライン", "アイソレーター", 
                "dc-dcコンバーター", "切替リレー", "リレー", "ヒューズ切れ", "充電不良",
                "電圧が上がらない", "12.5v", "12.6v", "13.5v", "満充電", "残量", "容量"
            ],
            "トイレ": ["トイレ", "toilet", "カセット", "マリン", "フラッパー", "便器", "水洗"],
            "ルーフベント": ["ルーフベント", "換気扇", "ファン", "マックスファン", "vent", "換気", "排気"],
            "水道": ["水道", "ポンプ", "給水", "水", "water", "pump", "シャワー", "蛇口"],
            "冷蔵庫": [
                "冷蔵庫", "冷凍", "コンプレッサー", "refrigerator", "冷える", "冷却",
                "3way", "3-way", "12v冷蔵庫", "24v冷蔵庫", "dometic", "waeco", "engel",
                "arb", "national luna", "ペルチェ式", "吸収式", "アンモニア臭",
                "ドアパッキン", "温度センサー", "サーミスタ", "エラーコード", "E4",
                "バッテリー消費", "消費電力", "庫内温度", "冷凍室", "野菜室",
                "ドアラッチ", "ヒューズ切れ", "電源切替", "ガスモード", "点火プラグ"
            ],
            "ガス": ["ガス", "gas", "コンロ", "ヒーター", "ff", "プロパン", "lpg"],
            "FFヒーター": [
                # 基本名称
                "FFヒーター", "ffヒーター", "FFヒータ", "ffヒータ", "FF heater", "ff heater",
                "FFヒーダー", "ffヒーダー", "FFヒーダ", "ffヒーダ",
                # 英語表記・略語
                "forced fan heater", "Forced Fan Heater", "FFH", "ffh",
                "車載ヒーター", "車載暖房", "キャンピングカーヒーター", "RVヒーター",
                # メーカー名・製品名
                "ベバスト", "webasto", "Webasto", "ウェバスト", "ウェバスト",
                "ミクニ", "mikuni", "Mikuni", "日本ミクニ",
                "LVYUAN", "lvyuan", "リョクエン", "リョクエン",
                "エバポール", "Eberspacher", "エバスポッチャー",
                "プラネー", "Planar", "プラナー",
                # 症状・トラブル
                "点火しない", "点火不良", "つかない", "点かない", "起動しない", "動かない",
                "白煙", "煙が出る", "煙がでる", "白い煙", "黒い煙", "煙突", "排気",
                "異音", "うるさい", "音が大きい", "ファン音", "燃焼音", "ポンプ音",
                "エラー", "エラーコード", "E13", "エラー表示", "リモコンエラー",
                "燃料", "燃料切れ", "燃料不足", "燃料ポンプ", "燃料フィルター",
                "燃焼", "燃焼不良", "燃焼室", "グロープラグ", "点火プラグ",
                "温度", "温風", "暖房", "暖かくならない", "温度調節",
                "電源", "電圧", "ヒューズ", "配線", "リモコン",
                "換気", "吸気", "排気", "一酸化炭素", "CO", "安全装置",
                "設置", "取り付け", "配管", "煙突設置", "DIY",
                "メンテナンス", "清掃", "分解", "オーバーホール", "点検",
                # 関連用語
                "暖房器", "強制送風", "熱交換器", "ファン", "温度制御",
                "自動停止", "安全装置", "燃料タンク", "配管工事"
            ],
            "電気": ["電気", "led", "照明", "電装", "electrical", "配線", "ヒューズ", "fuse"],
            "排水タンク": [
                "排水タンク", "グレータンク", "汚水", "排水", "drain", "tank", "グレー",
                "thetford", "dometic", "sealand", "valterra", "バルブハンドル", "Oリング",
                "レベルセンサー", "Pトラップ", "封水", "悪臭", "逆流", "凍結", "不凍剤",
                "排水ホース", "カムロック", "通気ベンチ", "バイオフィルム", "排水口キャップ"
            ],
            "電装系": [
                "電装系", "電気", "配線", "ヒューズ", "led", "照明", "electrical", "電源",
                "バッテリー", "インバーター", "victron", "samlex", "renogy", "goal zero",
                "bluetti", "調光器", "PWM", "100Vコンセント", "サブバッテリー", "残量計",
                "シャント抵抗", "DCシガーソケット", "USBポート", "5Vレギュレーター",
                "電子レンジ", "突入電流", "電圧降下", "配線太径", "外部電源", "AC入力"
            ],
            "雨漏り": ["雨漏り", "rain", "leak", "防水", "シール", "水漏れ", "水滴"],
            "異音": ["異音", "音", "騒音", "振動", "noise", "うるさい", "ガタガタ"],
            "ドア": ["ドア", "door", "窓", "window", "開閉", "開かない", "閉まらない"],
            "タイヤ": [
                "タイヤ", "tire", "パンク", "空気圧", "摩耗", "交換", "cp規格", "lt規格",
                "ミシュラン", "ブリヂストン", "ダンロップ", "ヨコハマ", "バースト", "偏摩耗",
                "亀裂", "ひび割れ", "バランス", "ローテーション", "過積載", "経年劣化",
                "ホイール", "損傷", "変形", "psi", "kpa", "kgf/cm2", "パンク保証"
            ],
            "エアコン": ["エアコン", "aircon", "冷房", "暖房", "温度", "設定"],
            "家具": [
                "家具", "テーブル", "椅子", "収納", "棚", "furniture", "ベッド", "ソファ",
                "キャビネット", "引き出し", "ダイネット", "ラッチ", "ヒンジ", "化粧板",
                "床下収納", "フロアハッチ", "スライドクローゼット", "マグネットキャッチ",
                "耐振動ラッチ", "金属ダンパー", "樹脂ブッシュ", "木工パテ", "消臭処理"
            ],
            "外装": ["外装", "塗装", "傷", "へこみ", "錆", "corrosion"],
            "排水": ["排水", "タンク", "汚水", "waste", "tank", "空にする"],
            "ソーラー": [
                "ソーラー", "solar", "パネル", "発電", "太陽光", "チャージコントローラー", "pwm", "mppt",
                "ソーラーパネル", "太陽光発電", "トイファクトリー", "京セラ", "長州産業", "kyocera", "choshu",
                "発電量", "変換効率", "バッテリー充電", "影の影響", "表面汚れ", "ひび割れ", "配線断線",
                "雷故障", "老朽化", "角度調整", "設置工事", "メンテナンス", "清掃", "診断"
            ],
            "外部電源": ["外部電源", "ac", "コンセント", "電源", "接続"],
            "室内LED": ["led", "照明", "電球", "暗い", "点かない", "light"],
            "水道ポンプ": [
                "水道ポンプ", "給水システム", "ポンプユニット", "給水設備", "配管・水回り",
                "ポンプ", "給水", "吐水", "吸水", "水圧", "流量", "故障", "モーター", "漏水",
                "water pump", "water system", "pump unit", "water supply", "plumbing",
                "water pressure", "flow rate", "motor failure", "leak", "water leak",
                "ポンプ故障", "給水不良", "水が出ない", "水圧不足", "ポンプ音", "異音",
                "モーター焼け", "コイル断線", "軸受け", "シール", "インペラー", "ケーシング",
                "圧力スイッチ", "フロートスイッチ", "配管", "ホース", "継手", "バルブ",
                "フィルター", "逆止弁", "減圧弁", "水漏れ", "凍結", "不凍剤", "防錆剤"
            ]
        }
        
        # キーワードマッチングで関連カテゴリを特定
        matched_categories = []
        for category, keywords in keyword_mapping.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    matched_categories.append(category)
                    break
        
        # マッチしたカテゴリのコンテンツを取得
        for category in matched_categories:
            if category in self.knowledge_base:
                content = self.knowledge_base[category]
                # 関連性の高い部分を抽出（簡易版）
                lines = content.split('\n')
                relevant_lines = []
                for line in lines:
                    if any(keyword.lower() in line.lower() for keyword in keyword_mapping.get(category, [])):
                        relevant_lines.append(line)
                
                if relevant_lines:
                    relevant_content.append(f"【{category}】\n" + '\n'.join(relevant_lines[:10]))  # 最大10行
        
        # マッチしなかった場合は全カテゴリから検索
        if not relevant_content:
            for category, content in self.knowledge_base.items():
                if any(keyword.lower() in query_lower for keyword in keyword_mapping.get(category, [])):
                    relevant_content.append(f"【{category}】\n{content[:500]}...")  # 最大500文字
        
        return relevant_content
    
    def get_category_specific_info(self, category: str, query: str) -> Optional[str]:
        """特定カテゴリの情報を取得"""
        if category not in self.knowledge_base:
            return None
        
        content = self.knowledge_base[category]
        query_lower = query.lower()
        
        # クエリに関連する部分を抽出
        lines = content.split('\n')
        relevant_lines = []
        
        for line in lines:
            if query_lower in line.lower():
                relevant_lines.append(line)
        
        if relevant_lines:
            return '\n'.join(relevant_lines[:20])  # 最大20行
        
        return content[:1000]  # 関連部分が見つからない場合は最初の1000文字
    
    def get_all_categories(self) -> List[str]:
        """利用可能な全カテゴリを取得"""
        return list(self.knowledge_base.keys())
    
    def get_category_content(self, category: str) -> Optional[str]:
        """指定カテゴリの全コンテンツを取得"""
        return self.knowledge_base.get(category)
    
    def search_in_content(self, query: str) -> Dict[str, str]:
        """全コンテンツからクエリを検索"""
        print(f"\n" + "="*50)
        print(f"🔍 search_in_content関数が呼び出されました")
        print(f"🔍 検索クエリ: '{query}'")
        print(f"📚 知識ベースの状態: {len(self.knowledge_base)}件のカテゴリ")
        print(f"="*50)
        
        if len(self.knowledge_base) == 0:
            print("❌ 警告: 知識ベースが空です！検索をスキップします。")
            return {}
        
        results = {}
        query_lower = query.lower()
        
        print(f"🔍 検索クエリ: '{query}' (小文字: '{query_lower}')")
        print(f"📚 検索対象カテゴリ数: {len(self.knowledge_base)}")
        
        # デバッグ: 最初のカテゴリの内容を確認
        if self.knowledge_base:
            first_category = list(self.knowledge_base.keys())[0]
            first_content = self.knowledge_base[first_category]
            print(f"🔍 サンプルカテゴリ: {first_category}")
            print(f"📄 サンプル内容（最初の200文字）: {first_content[:200]}...")
        
        for category, content in self.knowledge_base.items():
            # 完全一致検索
            if query_lower in content.lower():
                print(f"✅ 完全一致したカテゴリ: {category}")
                # 関連部分を抽出
                lines = content.split('\n')
                relevant_lines = []
                
                for line in lines:
                    if query_lower in line.lower():
                        relevant_lines.append(line)
                
                if relevant_lines:
                    results[category] = '\n'.join(relevant_lines[:10])  # 最大10行
                    print(f"  📄 関連行数: {len(relevant_lines)}")
            else:
                # 部分一致検索（単語レベル）
                query_words = query_lower.split()
                matched_words = []
                for word in query_words:
                    if word in content.lower():
                        matched_words.append(word)
                
                if matched_words:
                    print(f"🔍 部分一致したカテゴリ: {category} (マッチした単語: {matched_words})")
                    # 部分一致でも結果に含める
                    lines = content.split('\n')
                    relevant_lines = []
                    
                    for line in lines:
                        if any(word in line.lower() for word in matched_words):
                            relevant_lines.append(line)
                    
                    if relevant_lines:
                        results[category] = '\n'.join(relevant_lines[:10])
                        print(f"  📄 関連行数: {len(relevant_lines)}")
                else:
                    # カテゴリ名でのマッチング
                    if any(word in category.lower() for word in query_words):
                        print(f"🏷️ カテゴリ名でマッチしたカテゴリ: {category}")
                        # カテゴリ名がマッチした場合は全内容を返す
                        results[category] = content[:500]  # 最初の500文字
                        print(f"  📄 カテゴリ名マッチ: 全内容の最初の500文字")
                    else:
                        # デバッグ: マッチしなかった理由を確認
                        if "バッテリー" in category.lower() and "バッテリー" in query_lower:
                            print(f"🔍 バッテリーカテゴリの内容確認: {content[:100]}...")
        
        print(f"🎯 検索結果: {len(results)}件")
        return results
    
    def get_water_pump_info(self, query: str) -> Optional[str]:
        """水道ポンプ専用テキストデータから情報を取得"""
        try:
            with open("水道ポンプ.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 既存のextract_relevant_knowledge関数を活用
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"水道ポンプ情報取得エラー: {e}")
            return None
    
    def get_body_damage_info(self, query: str) -> Optional[str]:
        """車体破損専用テキストデータから情報を取得"""
        try:
            with open("車体外装の破損.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"車体破損情報取得エラー: {e}")
            return None
    
    def get_indoor_led_info(self, query: str) -> Optional[str]:
        """室内LED専用テキストデータから情報を取得"""
        try:
            with open("室内LED.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"室内LED情報取得エラー: {e}")
            return None
    
    def get_external_power_info(self, query: str) -> Optional[str]:
        """外部電源専用テキストデータから情報を取得"""
        try:
            with open("外部電源.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"外部電源情報取得エラー: {e}")
            return None
    
    def get_noise_info(self, query: str) -> Optional[str]:
        """異音専用テキストデータから情報を取得"""
        try:
            with open("異音.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"異音情報取得エラー: {e}")
            return None
    
    def get_tire_info(self, query: str) -> Optional[str]:
        """タイヤ専用テキストデータから情報を取得"""
        try:
            with open("タイヤ.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"タイヤ情報取得エラー: {e}")
            return None
    
    def get_solar_panel_info(self, query: str) -> Optional[str]:
        """ソーラーパネル専用テキストデータから情報を取得"""
        try:
            with open("ソーラーパネル.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"ソーラーパネル情報取得エラー: {e}")
            return None
    
    def get_sub_battery_info(self, query: str) -> Optional[str]:
        """サブバッテリー専用テキストデータから情報を取得"""
        try:
            with open("サブバッテリー.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"サブバッテリー情報取得エラー: {e}")
            return None
    
    def get_air_conditioner_info(self, query: str) -> Optional[str]:
        """エアコン専用テキストデータから情報を取得"""
        try:
            with open("エアコン.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"エアコン情報取得エラー: {e}")
            return None
    
    def get_inverter_info(self, query: str) -> Optional[str]:
        """インバーター専用テキストデータから情報を取得"""
        try:
            with open("インバーター.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"インバーター情報取得エラー: {e}")
            return None
    
    def get_window_info(self, query: str) -> Optional[str]:
        """ウインドウ専用テキストデータから情報を取得"""
        try:
            with open("ウインドウ.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"ウインドウ情報取得エラー: {e}")
            return None
    
    def get_rain_leak_info(self, query: str) -> Optional[str]:
        """雨漏り専用テキストデータから情報を取得"""
        try:
            with open("雨漏り.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"雨漏り情報取得エラー: {e}")
            return None
    
    def get_toilet_info(self, query: str) -> Optional[str]:
        """トイレ専用テキストデータから情報を取得"""
        try:
            with open("トイレ.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"トイレ情報取得エラー: {e}")
            return None
    
    def get_battery_info(self, query: str) -> Optional[str]:
        """バッテリー専用テキストデータから情報を取得"""
        try:
            with open("バッテリー.txt", 'r', encoding='utf-8') as f:
                content = f.read()
            
            relevant_info = self.extract_relevant_knowledge(query)
            if relevant_info:
                return '\n'.join(relevant_info)
            
            return content
            
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"バッテリー情報取得エラー: {e}")
            return None


# グローバルインスタンス
knowledge_base_manager = KnowledgeBaseManager()
