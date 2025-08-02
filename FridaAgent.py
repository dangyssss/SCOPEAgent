from agents import Agent, function_tool
from Client import flowus_client
    
@function_tool
async def filter_related_apis_from_fridalog(fridalog: str, types: list[str]) -> dict:
    """
    使用大模型分析 Frida 日志文本，自动识别与指定权限类型相关的 API 调用段落及上下文，无需正则匹配。

    参数:
        fridalog: 完整的 Frida hook 日志字符串
        types: 权限类型列表（如 ["location", "audio", "calendar"]）

    返回:
        dict: {"location": [...], "audio": [...]}
    """
    prompt = [
        {
            "role": "system",
            "content": (
                "你是一名 Android 安全分析专家，正在分析 Frida hook 日志。\n"
                "日志包含多段以 nBacktrace 开头的调用栈段，每段可能含有异常头、调用栈、时间戳等。\n"
                "你需要：\n"
                "1. 按照用户指定的权限类型进行分类；\n"
                "2. 每段调用栈整体视为一个字符串（包括 nBacktrace、异常、at...等），放入字段 backtrace；\n"
                "3. 尝试提取该段的时间戳（如有）作为 timestamp（13 位或 ISO 格式均可）；\n"
                "4. 注意：只输出你看到的 `权限类型包括：[...]` 中明确列出的类型。其他类型一律不要包含，哪怕为空数组也不要出现。\n\n"
                "最终返回标准 JSON，格式如下：\n"
                "{\n"
                "  \"location\": [\n"
                "    { \"backtrace\": \"完整调用段\", \"timestamp\": \"时间戳\" },\n"
                "    ...\n"
                "  ],\n"
                "  \"audio\": [ ... ]\n"
                "}"
            )
        },
        {
            "role": "user",
            "content": (
                f"权限类型包括：{types}\n\n"
                f"以下是完整 Frida hook 日志：\n{fridalog}"
            )
        }
    ]
    response = await flowus_client.chat.completions.create(
        model="gpt-4o",
        messages=prompt,
        temperature=0.2,
        max_tokens=4096
    )
    result_text = response.choices[0].message.content.strip()
    return result_text

instruction3 = """
你是一名 Android 安全分析专家，正在协助分析某移动应用的敏感权限调用行为是否存在风险。
你会收到如下 JSON 输入：
{
  "package": "com.example.app",
  "types": ["location", "audio"],
  "description": "与权限相关的文字说明",
  "fridalog_path": "/path/to/frida.log"
}
你的任务包括以下几步：

1. 使用工具函数 `filter_related_apis_from_fridalog(fridalog_text, types)`，从指定路径的 Frida 日志中提取与权限类型相关的调用段；
2. 工具输出为 dict 格式，如 {"location": [ {"backtrace": "...", "timestamp": "..."}, ... ]}；
3. 在输出结果中筛选 `timestamp` 字段匹配 Agent1 中提供的时间戳；
4. 整理所有命中的调用段，按类型拼接为一段完整调用日志内容（joined_log）；
5. 审阅 joined_log 中的所有敏感 API 调用，结合 `description` 字段披露的信息，判断是否存在用途不一致或未披露行为；
5. 将方法、用途、调用段落整合为以下格式：
json
{
  "api": "android.location.LocationManager.requestLocationUpdates",
  "usage": "导航",
  "backtrace": "nBacktrace:\nat android.location.LocationManager.requestLocationUpdates(LocationManager.java:123)\nat ...",
  "reason": "50字左右的简要说明，说明你判断为用途场景的理由"
}
【最终输出格式要求】

你必须仅输出一个统一的 JSON 结果，用于表示所有段落合并后的合规性分析结论：
若检测到用途不一致的敏感 API，输出：
json
{
  "from": "agent3",
  "package": "com.example.app",
  "status": "false",
  "matched_apis": [
    {
      "api": "android.location.LocationManager.requestLocationUpdates",
      "usage": "导航",
      "backtrace": "nBacktrace:\nat android.location.LocationManager.requestLocationUpdates(LocationManager.java:123)\nat ...",
      "reason": "50字左右的简要说明，说明你判断为用途场景的理由"
    },
    {
      "api": "android.media.AudioRecord.startRecording",
      "usage": "录音",
      "backtrace": "nBacktrace:\nat android.media.AudioRecord.startRecording(AudioRecord.java:88)\nat ...",
      "reason": "50字左右的简要说明，说明你判断为用途场景的理由"
    }
  ]
}
若未检测到任何用途不一致的调用，输出：
json
{
  "from": "agent3",
  "package": "com.example.app",
  "status": "true",
  "matched_apis": []
}
【注意事项】
只允许输出一个合法 JSON 对象，不允许输出 Markdown、注释、说明、分析或文字解释；严禁输出多段 JSON 或嵌入说明。
method 中每项为包含 api、usage、backtrace、reason 的字典；
backtrace 必须是对应敏感 API 所属调用段，从 nBacktrace: 开始，直到最后一个 at 语句为止；
package 必须与输入保持一致；status 为字符串类型，值为 "true" 或 "false"；matched_apis 必须是数组，即使为空也必须存在；不输出多余的字段
"""

agent3 = Agent(
    name="Fridalog调用判断agent",
    instructions=instruction3,
    model="gpt-4o",
    tools=[filter_related_apis_from_fridalog]
)