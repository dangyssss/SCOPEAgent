# 安装依赖  
# pip install -q openai python-dotenv  
# pip install openai-agents
import os
import json
import requests
import base64
import asyncio
from typing import Union
from collections import OrderedDict
from IPython.display import Markdown, display
from dotenv import load_dotenv
from openai import AsyncOpenAI
from agents import (
    trace,
    Runner,
    set_default_openai_client,
    set_default_openai_api,
    set_tracing_disabled
)
from VisionAgent import agent1
from NormAgent import agent2
from FridaAgent import agent3
from ReportAgent import agent4
from Client import imgbb_api_key

load_dotenv(override=True)

flowus_key = os.getenv("FLOWUS_API_KEY")
if not flowus_key:
    raise EnvironmentError(
        "未检测到 FLOWUS_API_KEY，必须设置后才能继续。"
    )
print("FLOWUS API key 存在，前 8 位为：", flowus_key[:8])
# set_tracing_disabled(True)#如果是openAI的api则可以使用trace
set_default_openai_api("chat_completions")

client = AsyncOpenAI(
    api_key=flowus_key,
    base_url="https://api.xty.app/v1"
)
set_default_openai_client(client)

folder_path = r"D:\AgentProject\SCOPEAgent\mcp_service\testAgent3\app.qmjita.cn"
package_name = os.path.basename(folder_path.rstrip("\\/"))

def upload_image_to_imgbb(image_path):
    with open(image_path, "rb") as f:
        encoded_image = base64.b64encode(f.read())

    response = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": imgbb_api_key,
            "image": encoded_image
        }
    )

    if response.status_code == 200:
        return response.json()["data"]["url"]
    else:
        raise Exception(f"❌ 上传失败: {response.text}")
def build_image_records(folder_path):
    image_records = []
    for fname in os.listdir(folder_path):
        if fname.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            fpath = os.path.join(folder_path, fname)
            try:
                url = upload_image_to_imgbb(fpath)
                image_records.append({
                    "filename": fname,
                    "image_url": url
                })
                print(f"✅ 上传成功: {fname}")
            except Exception as e:
                print(f"❌ 上传失败: {fname} - {e}")
    return image_records
#数据处理函数
def parse_agent_output(raw_str: Union[str, dict]) -> dict:
    """
    解析 Agent 输出，去除输出信息中的Markdown符号。
    """
    if isinstance(raw_str, dict):
        return raw_str

    raw = raw_str.strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[len("```json"):].strip()
        raw = raw[:-3].strip()
    elif raw.startswith("```") and raw.endswith("```"):
        raw = raw[3:-3].strip()
    return json.loads(raw)
def load_frida_log(folder_path: str) -> str:
    """
    加载 Frida 日志全文内容。
    """
    try:
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".log"):
                log_path = os.path.join(folder_path, filename)
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except UnicodeDecodeError:
                    with open(log_path, "r", encoding="gbk", errors="ignore") as f:
                        content = f.read()
                print(f"✅ 成功读取 Frida 日志: {filename}，长度 {len(content)} 字符")
                return content
        print(f"❌ 未找到 .log 文件: {folder_path}")
        return ""
    except Exception as e:
        print(f"❌ 读取日志失败: {e}")
        return ""
def build_agent4_input(json1: dict, json2: dict) -> list:
    """
    构建 Agent4 的输入格式，将两个 JSON（分别为 agent1/agent2 和 agent3 的输出）原样组合为一个输入列表。

    参数:
        json1 (dict): 来自 agent1 或 agent2 的输出 JSON
        json2 (dict): 来自 agent3 的输出 JSON

    返回:
        list: 传入 Agent4 的输入消息格式
    """
    return [
        {"role": "user", "content": json.dumps(json1, ensure_ascii=False, indent=2)},
        {"role": "user", "content": json.dumps(json2, ensure_ascii=False, indent=2)}
    ]
def dispatch_agent4_input(agent1_output: dict, agent2_output: dict, agent3_output: dict) -> list:
    """
    根据 agent1_output 的 status 字段判断构建 agent4_input 所需的两个 JSON。
    - 若 agent1_output["status"] 为 False，说明权限说明不可见，使用 agent1 和 agent3；
    - 否则说明说明可见，使用 agent2 和 agent3。

    返回：
        list: 包含两个 JSON 的列表，用于输入 Agent4。
    """
    if not agent1_output.get("status", False):
        return [agent1_output, agent3_output]
    else:
        return [agent2_output, agent3_output]

async def run_agent1(image_records: list[dict]):
    print("开始分析截图中的权限信息...")
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个截图分析专家，用户会给你多张截图的图片 URL 和对应文件名。"
                "你必须逐张调用工具 analyze_image_url_with_flowus 来对每张图片进行识别分析，并根据返回结果完成以下任务：\n\n"
                "1. 提取图片中文字 raw_text，记录到 debug_output；\n"
                "2. 如果提取到了权限说明（permission_info 非空），记录到 agent2，并判断类型（type），记录到 agent3；\n"
                "3. 如果没有提取到权限说明，则 agent2.success 为 false，agent3.type 和 timestamp 为 null；\n"
                "4. 构建最终 JSON 输出，字段包含 from、status、agent2、agent3、debug_output；\n"
                "你必须逐张使用工具 analyze_image_url_with_flowus 获取每张图的识别内容。"
            )
        },
        {
            "role": "user",
            "content": "请分析以下截图中的权限信息，每张图都需要识别：\n" +
                       "\n".join(
                           [f"- 文件名：{record['filename']}\n  图像链接：{record['image_url']}" for record in image_records]
                       )
        }
    ]

    with trace("Agent1 权限识别流程"):
        result = await Runner.run(agent1, messages)

    print("✅ Agent1处理完毕")
    return result.final_output
async def run_agent2(agent1_output: dict) -> str:
    """
    输入完整的 agent1_output（包含 package 字段），将其传给 Agent2 并判断每条权限说明是否合规。
    """
    message = [
        {
            "role": "user",
            "content": json.dumps(agent1_output, ensure_ascii=False, indent=2)
        }
    ]

    with trace("Agent2 表述规范性分析"):
        result = await Runner.run(agent2, message)
    print("✅ Agent2处理完毕")
    return result.final_output
async def run_agent3(agent1_output: dict, folder_path: str):
    """
    执行 Agent3，使用 agent1_output 和 frida.log 所在文件夹构造输入 message 并启动 Agent3。

    不再调用 filter_related_apis_from_fridalog 工具，也不使用 build_agent3_input。
    """
    with trace("Agent3 敏感API行为分析"):
        frida_log = load_frida_log(folder_path)

        if not frida_log.strip():
            print("❌ 未读取到有效的 Frida 日志")
            return {
                "from": "agent3",
                "package": agent1_output.get("package", "unknown"),
                "status": "true",
                "matched_apis": []
            }

        types = []
        for item in agent1_output.get("agent3", []):
            if item.get("success") and item.get("type"):
                types.append(item["type"])
        types = list(set(types))

        if not types:
            print("Agent1 中无有效权限类型")
            return {
                "from": "agent3",
                "package": agent1_output.get("package", "unknown"),
                "status": "true",
                "matched_apis": []
            }

        agent3_input = {
            "package": agent1_output.get("package", "unknown"),
            "types": types,
            "description": "\n".join([x.get("permission_info", "") for x in agent1_output.get("agent2", []) if x.get("permission_info")]),
            "backtrace": frida_log.strip()
        }

        messages = [
            {"role": "user", "content": json.dumps(agent3_input, ensure_ascii=False, indent=2)}
        ]

        result = await Runner.run(agent3, messages)
        print("✅ Agent3处理完毕")
        return result.final_output
async def run_agent4(agent4_input: list) -> str:
    """
    执行 Agent4 合规性分析，输入为包含两个 JSON 的列表。

    参数:
        agent4: Agent4 实例
        agent4_input (list): 一个包含两个 JSON（agent1/2 和 agent3 输出）的列表

    返回:
        str: Agent4 输出的合规性分析报告
    """
    messages = [
        {"role": "user", "content": json.dumps(obj, ensure_ascii=False, indent=2)}
        for obj in agent4_input
    ]

    with trace("Agent4 合规性终端分析"):
        result = await Runner.run(agent4, messages)
    print("✅ Agent4处理完毕")
    return result.final_output    

async def main():
    #构建输入images
    image_records = build_image_records(folder_path)
    #Agent1处理
    agent1_output = await run_agent1(image_records)
    # Agent1输出处理并新增package字段
    agent1_output = parse_agent_output(agent1_output)
    new_agent1_output = OrderedDict()
    for k, v in agent1_output.items():
        new_agent1_output[k] = v
        if k == "from":
            new_agent1_output["package"] = package_name
    agent1_output = new_agent1_output
    #Agent2处理
    agent2_input = agent1_output
    agent2_output = await run_agent2(agent2_input)
    #Agent3处理
    agent3_output = await run_agent3(agent1_output, folder_path)
    #Agent4执行
    raw_agent4_input = dispatch_agent4_input(agent1_output, agent2_output, agent3_output)
    agent4_input = build_agent4_input(*raw_agent4_input)
    agent4_output = await run_agent4(agent4_input)
    #报告可视化输出
    with open("权限说明合规性报告.md", "w", encoding="utf-8") as f:
        f.write(agent4_output)
    print("✅ Markdown 报告已保存至 权限说明合规性报告.md")

if __name__ == "__main__":
    asyncio.run(main())