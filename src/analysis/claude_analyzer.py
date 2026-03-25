from __future__ import annotations

import json
import logging

import anthropic

from src.storage.models import RawItem
from .models import AnalysisResult, StockOpportunity

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
あなたは米国株・日本株両方に精通した専門アナリストです。最新のニュース記事やSNS投稿を分析し、\
注目すべき株式の投資機会を特定してください。

対象市場:
- **米国株**: ティッカーシンボルで表記（例: AAPL, NVDA, GS）
- **日本株**: 証券コードと企業名で表記（例: 8035 東京エレクトロン, 9984 ソフトバンクG）

注目すべき領域:
- **IPO関連**: 大型IPOによるセクター全体への影響（米国: GS/MS、日本: 野村/大和）
- **政策発表**: 各国政府の投資政策、通商政策、関税、規制変更による追い風（対米投資、経済安保、半導体補助金等）
- **セクターローテーション**: 資金が特定セクターに流入している兆候
- **バスケット買い**: テーマやセクター内の複数銘柄に同時買い圧力がかかる状況
- **決算カタリスト**: 直近のニュース文脈から株価を動かしうる決算イベント
- **日米連動**: 米国の動きが日本株に波及するケース（例: SOX指数上昇→東京エレクトロン、米金利動向→銀行株）

ルール:
1. 複数の情報源が一致する場合のみアラートを出す。単一ソースの場合は信頼度を低めに。
2. 信頼度スコアは保守的に。0.8以上は複数ソースで裏付けがある非常に強いシグナルのみ。
3. 注目すべきものがなければ空のリストを返す。無理にアラートを出さないこと。
4. 因果関係を必ず説明: 何が起きた → 何を意味する → どの銘柄が恩恵を受ける。
5. 同じテーマで恩恵を受ける関連銘柄も含める（日米横断でも可）。
6. 直接的な恩恵だけでなく間接的な恩恵も考慮（例: IPOラッシュ→GS/MS、半導体規制→東京エレクトロン）。
7. すべて日本語で回答すること。
8. 日本株のtickerフィールドには「証券コード 企業名」の形式で記載（例: "8035 東京エレクトロン"）。
"""


class ClaudeAnalyzer:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze(self, items: list[RawItem], watchlist: dict | None = None) -> AnalysisResult:
        if not items:
            return AnalysisResult(opportunities=[], market_summary="No new data to analyze.")

        user_content = self._build_prompt(items, watchlist)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
                tools=[{
                    "name": "report_analysis",
                    "description": "Report the stock analysis results",
                    "input_schema": AnalysisResult.model_json_schema(),
                }],
                tool_choice={"type": "tool", "name": "report_analysis"},
            )

            # Extract tool use result
            for block in response.content:
                if block.type == "tool_use" and block.name == "report_analysis":
                    return AnalysisResult.model_validate(block.input)

            logger.warning("No tool_use block found in Claude response")
            return AnalysisResult(opportunities=[], market_summary="Analysis failed.")

        except Exception:
            logger.exception("Claude API call failed")
            return AnalysisResult(opportunities=[], market_summary="Analysis error.")

    def _build_prompt(self, items: list[RawItem], watchlist: dict | None) -> str:
        lines = ["Here are the latest news items and posts to analyze:\n"]

        for i, item in enumerate(items, 1):
            lines.append(f"--- Item {i} ---")
            lines.append(f"Source: {item.source}")
            lines.append(f"Title: {item.title}")
            if item.content:
                lines.append(f"Content: {item.content[:500]}")
            if item.url:
                lines.append(f"URL: {item.url}")
            if item.published_at:
                lines.append(f"Published: {item.published_at.isoformat()}")
            lines.append("")

        if watchlist:
            lines.append("\n--- ウォッチリスト（以下は特に注目してほしい銘柄・セクターだが、それ以外でも重要な機会があれば必ず報告すること） ---")
            if watchlist.get("jp_tickers"):
                # コメント付きティッカーをそのまま渡す（Claudeが企業名を認識できる）
                jp = watchlist["jp_tickers"]
                lines.append(f"日本株({len(jp)}銘柄): {', '.join(jp)}")
            if watchlist.get("us_tickers"):
                us = watchlist["us_tickers"]
                lines.append(f"米国株({len(us)}銘柄): {', '.join(us)}")
            if watchlist.get("sectors"):
                lines.append(f"注目セクター: {', '.join(watchlist['sectors'])}")

        lines.append(
            "\nAnalyze these items and identify any actionable stock opportunities. "
            "Use the report_analysis tool to provide your results."
        )

        return "\n".join(lines)
