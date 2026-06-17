from analysis.gemini_client import GeminiClient


client = GeminiClient()

prompt = """
請用繁體中文回答。

請分析台積電目前技術面狀況。
"""

result = client.generate(prompt)

print("===== Gemini Response =====")
print(result)
