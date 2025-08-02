from dotenv import load_dotenv
import os
from openai import AsyncOpenAI
from agents import set_default_openai_client, set_default_openai_api
load_dotenv(override=True)
#检查api
flowus_api_key = os.getenv('FLOWUS_API_KEY')
if not flowus_api_key:
    raise EnvironmentError("未检测到 FLOWUS_API_KEY 环境变量，请设置后重试。")
print(f"FLOWUS API key 存在，开头为 {flowus_api_key[:8]}")

imgbb_api_key = os.getenv('IMGBB_API_KEY')

if not imgbb_api_key:
    raise EnvironmentError("未检测到 IMGBB_API_KEY 环境变量，请设置后重试。")
print(f"IMGBB API key 存在，开头为 {imgbb_api_key[:8]}")

# 初始化client
flowus_client = AsyncOpenAI(
    api_key=flowus_api_key,
    base_url="https://api.xty.app/v1"
)
# 设置默认 client 和默认 API
set_default_openai_client(flowus_client)
set_default_openai_api("chat_completions")