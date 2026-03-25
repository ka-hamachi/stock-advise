from __future__ import annotations

import logging

import anthropic

from src.storage.models import RawItem
from .models import AnalysisResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_US = """\
あなたは米国株市場の専門アナリストです。最新のニュース記事を分析し、\
注目すべき米国株の投資機会を5〜10件特定してください。

注目すべき領域:
- **IPO関連**: 大型IPOによるセクター全体への影響（GS/MSの引受手数料増など）
- **政策発表**: 政府の投資政策、通商政策、関税、規制変更による追い風
- **セクターローテーション**: 資金が特定セクターに流入している兆候
- **バスケット買い**: テーマやセクター内の複数銘柄に同時買い圧力がかかる状況
- **決算カタリスト**: 直近のニュース文脈から株価を動かしうる決算イベント

ルール:
1. 複数の情報源が一致する場合のみアラートを出す。単一ソースの場合は信頼度を低めに。
2. 信頼度スコアは保守的に。0.8以上は複数ソースで裏付けがある非常に強いシグナルのみ。
3. 因果関係を必ず説明: 何が起きた → 何を意味する → どの銘柄が恩恵を受ける。
4. 同じテーマで恩恵を受ける関連銘柄も含める。
5. 直接的な恩恵だけでなく間接的な恩恵も考慮。
6. すべて日本語で回答すること。ティッカーシンボルは米国市場のものを使用。
7. **必ず5〜10件の機会を報告すること。**
"""

SYSTEM_PROMPT_JP = """\
あなたは日本株市場の専門アナリストです。最新のニュース記事を分析し、\
注目すべき日本株の投資機会を5〜10件特定してください。

注目すべき領域:
- **IPO関連**: 大型IPOによるセクター全体への影響（野村/大和の引受など）
- **政策発表**: 政府の経済政策、経済安保、半導体補助金、対米投資政策などによる追い風
- **セクターローテーション**: 資金が特定セクターに流入している兆候
- **バスケット買い**: テーマやセクター内の複数銘柄に同時買い圧力がかかる状況
- **決算カタリスト**: 直近のニュース文脈から株価を動かしうる決算イベント
- **海外連動**: 米国・中国の動きが日本株に波及するケース（例: SOX指数→東京エレクトロン、米金利→銀行株、中国景気→商社）

ルール:
1. 複数の情報源が一致する場合のみアラートを出す。単一ソースの場合は信頼度を低めに。
2. 信頼度スコアは保守的に。0.8以上は複数ソースで裏付けがある非常に強いシグナルのみ。
3. 因果関係を必ず説明: 何が起きた → 何を意味する → どの銘柄が恩恵を受ける。
4. 同じテーマで恩恵を受ける関連銘柄も含める。
5. 直接的な恩恵だけでなく間接的な恩恵も考慮。
6. すべて日本語で回答すること。
7. tickerフィールドには「証券コード 企業名」の形式で記載（例: "8035 東京エレクトロン"）。
8. **必ず5〜10件の機会を報告すること。** 米国ニュースしかない場合でも、その影響を受ける日本株を分析すること。
"""

# Japanese news source prefixes
JP_SOURCES = {"Yahoo Finance Japan", "日経新聞", "ロイター Japan", "株探ニュース"}


def is_jp_source(source: str) -> bool:
    return any(jp in source for jp in JP_SOURCES)


class ClaudeAnalyzer:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def analyze(self, items: list[RawItem], watchlist: dict | None = None) -> AnalysisResult:
        if not items:
            return AnalysisResult(opportunities=[], market_summary="分析対象のデータがありません。")

        # Split items by market
        jp_items = [i for i in items if is_jp_source(i.source)]
        us_items = [i for i in items if not is_jp_source(i.source)]

        logger.info("Analyzing %d US items and %d JP items separately", len(us_items), len(jp_items))

        # Run US analysis
        us_result = self._call_claude(
            SYSTEM_PROMPT_US,
            us_items + jp_items,  # JP news can also affect US stocks
            watchlist,
            "米国株",
        )

        # Run JP analysis (all news - US news affects JP stocks too)
        jp_result = self._call_claude(
            SYSTEM_PROMPT_JP,
            jp_items + us_items,  # US news can also affect JP stocks
            watchlist,
            "日本株",
        )

        # Merge results
        all_opps = us_result.opportunities + jp_result.opportunities
        summary = f"【米国】{us_result.market_summary}\n【日本】{jp_result.market_summary}"

        return AnalysisResult(opportunities=all_opps, market_summary=summary)

    def _call_claude(
        self,
        system_prompt: str,
        items: list[RawItem],
        watchlist: dict | None,
        market_label: str,
    ) -> AnalysisResult:
        user_content = self._build_prompt(items, watchlist)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
                tools=[{
                    "name": "report_analysis",
                    "description": "Report the stock analysis results",
                    "input_schema": AnalysisResult.model_json_schema(),
                }],
                tool_choice={"type": "tool", "name": "report_analysis"},
            )

            for block in response.content:
                if block.type == "tool_use" and block.name == "report_analysis":
                    result = AnalysisResult.model_validate(block.input)
                    logger.info("%s analysis: %d opportunities", market_label, len(result.opportunities))
                    return result

            logger.warning("No tool_use block in %s response", market_label)
            return AnalysisResult(opportunities=[], market_summary=f"{market_label}の分析に失敗しました。")

        except Exception:
            logger.exception("%s Claude API call failed", market_label)
            return AnalysisResult(opportunities=[], market_summary=f"{market_label}の分析エラー。")

    def _build_prompt(self, items: list[RawItem], watchlist: dict | None) -> str:
        lines = ["以下の最新ニュースを分析してください:\n"]

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
            lines.append("\n--- ウォッチリスト（特に注目してほしいが、それ以外も重要なら報告すること） ---")
            if watchlist.get("jp_tickers"):
                jp = watchlist["jp_tickers"]
                lines.append(f"日本株({len(jp)}銘柄): {', '.join(jp)}")
            if watchlist.get("us_tickers"):
                us = watchlist["us_tickers"]
                lines.append(f"米国株({len(us)}銘柄): {', '.join(us)}")
            if watchlist.get("sectors"):
                lines.append(f"注目セクター: {', '.join(watchlist['sectors'])}")

        lines.append(
            "\n上記のニュースを分析し、投資機会を特定してください。"
            "report_analysisツールで結果を報告してください。"
        )

        return "\n".join(lines)
