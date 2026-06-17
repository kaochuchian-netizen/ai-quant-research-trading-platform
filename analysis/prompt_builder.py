def build_analysis_prompt(data):

    adr_text = "無 ADR 資料"

    if data.get("adr"):
        adr = data["adr"]

        adr_text = f"""
ADR Symbol：{adr['symbol']}
ADR Close：{adr['close']}
ADR Change：{adr['change_rate']}%
ADR Signal：{adr['signal']}
"""

    prompt = f"""
你是一位專業台股分析師。

請根據以下資料，產生一段「LINE 推播用」的精簡 AI 觀點。

股票代號：{data['stock_id']}
日期：{data['date']}
收盤價：{data['close']}

均線：{data['ma']}
RSI：{data['rsi']}
MACD：{data['macd']}
布林通道：{data['bollinger']}
成交量：{data['volume']}
訊號：{data['signals']}
分數：{data['score']}
整體評等：{data['score']['overall_rating']}

ADR資料：
{adr_text}

輸出規則：
1. 只輸出一段繁體中文
2. 不要標題
3. 不要條列
4. 不要 Markdown
5. 不要免責聲明
6. 不要超過 80 個中文字
7. 必須包含：趨勢、主要風險、操作建議
8. 如果有 ADR 資料，需簡短提到 ADR 對隔日開盤的影響
"""

    return prompt
