def build_news_prompt(stock_id: str, stock_name: str, news_items: list):
    if not news_items:
        return f"""
請針對以下股票進行新聞面分析：

股票：{stock_name}（{stock_id}）

目前沒有取得近期新聞。

請回覆：
1. 新聞熱度：低
2. 消息面影響：中性
3. 風險提醒
4. 對短中長期策略的影響
"""

    news_text = ""

    for i, item in enumerate(news_items, start=1):
        news_text += f"""
新聞 {i}
日期：{item.get("published", "")}
來源：{item.get("source", "")}
標題：{item.get("title", "")}
"""

    prompt = f"""
你是台股新聞分析引擎，請根據以下新聞標題，分析新聞消息面對股票的影響。

股票：{stock_name}（{stock_id}）

近期新聞：
{news_text}

請用繁體中文，輸出精簡分析。

輸出格式固定如下：

【新聞面分析】
新聞熱度：高 / 中 / 低
消息面方向：偏多 / 中性 / 偏空
主要原因：
- 
- 

短線影響：
中線影響：
長線影響：

風險：
- 

結論：
"""

    return prompt
