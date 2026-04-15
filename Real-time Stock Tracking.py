import os
import time
import json
import requests
import yfinance as yf
from collections import deque
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# 加载环境变量 (从本地 .env 文件读取，保护隐私)
load_dotenv()


class InvestmentAgent:
    def __init__(self):
        # 基础配置
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.feishu_webhook = os.getenv("FEISHU_WEBHOOK_URL")
        self.watch_list = ["NVDA", "TSLA", "700.HK", "601919.SS"]

        # 趋势记忆：每个标的保留最近 6 次扫描记录
        self.memory_window = 6
        self.history = {ticker: deque(maxlen=self.memory_window) for ticker in self.watch_list}

        # 初始化大模型 (千问 Plus)
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen-plus",
            temperature=0.1
        )

    def _get_market_snapshot(self, ticker):
        """抓取市场数据并更新时序记忆"""
        try:
            stock = yf.Ticker(ticker)
            current_price = stock.fast_info['last_price']
            self.history[ticker].append(round(current_price, 2))

            history_list = list(self.history[ticker])
            signal = "Stable"
            if len(history_list) > 1:
                avg = sum(history_list[:-1]) / (len(history_list) - 1)
                diff = (current_price - avg) / avg
                if diff > 0.01:
                    signal = "Bullish Breakout"
                elif diff < -0.01:
                    signal = "Bearish Weakness"

            return {
                "symbol": ticker,
                "price": round(current_price, 2),
                "trend_history": history_list,
                "signal": signal
            }
        except Exception as e:
            return {"symbol": ticker, "error": str(e)}

    def push_to_feishu(self, title, content):
        """企业级飞书富文本推送"""
        if not self.feishu_webhook: return

        payload = {
            "msg_type": "post",
            "content": {"post": {"zh_cn": {
                "title": f"🚨 {title}",
                "content": [[{"tag": "text", "text": content}]]
            }}}
        }
        try:
            requests.post(self.feishu_webhook, json=payload, timeout=10)
        except Exception as e:
            print(f"推送失败: {e}")

    def run_analysis(self):
        """核心监控逻辑"""
        print(f"\n[{time.strftime('%H:%M:%S')}] 正在执行多维趋势分析...")

        snapshots = [str(self._get_market_snapshot(t)) for t in self.watch_list]

        # 职业级 Prompt：结合了你的航运背景逻辑
        prompt = f"""
        Role: Senior Quantitative Strategist
        Context: You are monitoring high-tech stocks and shipping logistics.
        Market Data Snapshot: {snapshots}

        Task:
        1. Analyze trend consistency based on 'trend_history'.
        2. Evaluate the potential impact of 601919.SS (COSCO SHIPPING) fluctuations on tech supply chains (e.g., NVDA).
        3. Issue a warning ONLY if a significant risk or opportunity is detected.

        Response Format:
        - If Alert: Start with 【🚨Investment Alert】 and provide reasoning.
        - If Normal: Reply only "Market Stable".
        """

        try:
            res = self.llm.invoke([HumanMessage(content=prompt)])
            analysis = res.content
            print(f"AI Output: {analysis}")

            if "Alert" in analysis or "预警" in analysis:
                self.push_to_feishu("AI 投资风险预警", analysis)
        except Exception as e:
            print(f"LLM 决策异常: {e}")


if __name__ == "__main__":
    agent = InvestmentAgent()
    print("AI Agent 已启动，结合航运背景与时序记忆监控中...")
    while True:
        agent.run_analysis()
        time.sleep(300)  # 每 5 分钟扫描一次