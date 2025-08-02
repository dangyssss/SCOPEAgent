from agents import Agent, function_tool
import re
from Client import flowus_client

@function_tool
async def analyze_image_url_with_flowus(filename: str, image_url: str) -> dict:
    print(f"正在识别图片: {filename}")
    messages = [
        {
            "role": "system",
            "content": "你是一个 OCR 图像识别专家，请识别图片中的所有文字，并判断其中是否包含权限说明。"
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"请识别图像文件 {filename} 中的所有可见文字内容，并完成以下任务：\n\n"
                        "1. 提取所有文字，原样输出为 raw_text。\n"
                        "2. 判断是否存在权限说明，如有，请提取该段并输出为 permission_info。\n"
                        "注意以下判断标准：\n"
                        "- 属于权限说明的关键词：获取权限、申请权限、收集信息、获取位置信息、访问相册、使用该权限、实现功能、为您推荐、验证 IMEI 等。\n"
                        "- 不属于权限说明的内容包括：允许/拒绝、Allow/Deny、系统弹窗提示、是否允许 XXX 访问某权限。\n"
                        "只提取文字，不做解释，不输出格式说明。\n"
                        "直接返回两个字段：raw_text 和 permission_info。"
                    )
                },
                {"type": "image_url", "image_url": {"url": image_url}}
            ]
        }
    ]
    try:
        response = await flowus_client.chat.completions.create(
            model="gemini-2.5-flash",
            messages=messages,
            max_tokens=2048
        )
        content = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"\n❌ 模型调用失败 for {filename}：{e}\n")
        return {
            "filename": filename,
            "timestamp": "error",
            "raw_text": "",
            "permission_info": None
        }

    match = re.search(r'(\d{13})', filename)
    timestamp = match.group(1) if match else "null"
    raw_text = ""
    permission_info = None
    raw_match = re.search(r'raw_text\s*[:：]\s*(.+)', content, re.DOTALL)
    perm_match = re.search(r'permission_info\s*[:：]\s*(.+)', content, re.DOTALL)
    if raw_match:
        raw_text = raw_match.group(1).strip()
    if perm_match:
        permission_info = perm_match.group(1).strip()
        if permission_info.lower() in {"null", "none", "无"}:
            permission_info = None
    return {
        "filename": filename,
        "timestamp": timestamp,
        "raw_text": raw_text,
        "permission_info": permission_info
    }

instruction1 = """
你是一个截图分析专家，用户会给你多张截图的图片 URL 和对应文件名。你必须逐张调用工具 analyze_image_url_with_flowus 来对每张图片进行识别分析，并根据返回结果完成以下任务：

请注意，你只输出 JSON，不加任何描述性前缀或结尾。不要输出“以下是分析结果”之类的话。

1. 对每张截图使用工具 analyze_image_url_with_flowus，获取以下字段：
   - `filename`: 原始图片文件名
   - `raw_text`: 图像中识别出的所有文字内容
   - `permission_info`: 若存在权限说明，则为提取的权限说明文本，否则为 null
   - `timestamp`: 从文件名中提取的 13 位时间戳（如 abc_1753201142089.png → 1753201142089）

2. 根据每张图片的 permission_info 字段判断：
   - 若 permission_info 非空，表示该图片包含权限说明，agent2.success 为 true；
   - 若 permission_info 为 null，表示该图片未识别到权限说明，agent2.success 为 false；
   - 请将 permission_info 原文填入 agent2.permission_info。

3. 对每条成功识别出权限说明的图片，还需判断其用途类型（type），归类为以下之一：
["storage", "location", "take picture and record video", "photo media and files", "audio", "剪切板", "悬浮窗", "manage phone call", "查看使用的应用", "身体活动数据", "contact", "calendar"]

若 permission_info 非空，根据其内容判断 type（如下方映射表）；
若 permission_info 为 null，但 raw_text 中出现了“Allow XX to …”或“是否允许 XX 使用 … 权限”等系统权限弹窗提示，也应从中推断 type 并视为成功（agent3.success 为 true）；
若无法推断用途，则 agent3.success 为 false，type 和 timestamp 也为 null。

请根据 permission_info 的内容判断用途类型：
   - “文件、下载、缓存” → storage
   - “定位、地图、位置” → location
   - “拍照、摄像、录像” → take picture and record video
   - “相册、图库、媒体文件” → photo media and files
   - “麦克风、语音、录音” → audio
   - “剪贴板” → 剪切板
   - “悬浮窗、画中画” → 悬浮窗
   - “拨打电话、通话记录” → manage phone call
   - “使用情况访问权限” → 查看使用的应用
   - “步数、加速度传感器” → 身体活动数据
   - “联系人、通讯录” → contact
   - “日历、日程、提醒” → calendar

若未识别出权限说明，则 type 为 null。

4. 所有 raw_text 字段应按图片逐项记录到 debug_output 中。

5. 最终请输出如下格式 JSON：

如果至少有一张截图识别出权限说明（即 agent2 中存在 success 为 true 的项）：
json
{
  "from": "agent1",
  "status": true,
  "agent2": [
    {
      "filename": "mapapp_1753200000000.png",
      "success": true,
      "permission_info": "我们会使用您的位置信息推荐附近服务"
    },
    {
      "filename": "callapp_1755787770000.jpg",
      "success": false,
      "permission_info": null
    }
  ],
  "agent3": [
    {
      "filename": "mapapp_1753200000000.png",
      "success": true,
      "timestamp": "1753200000000",
      "type": "location"
    },
    {
      "filename": "callapp_1755787770000.jpg",
      "success": true,
      "timestamp": "1755787770000",
      "type": "manage phone call"
    }
  ],
  "debug_output": [
    {
      "filename": "mapapp_1753200000000.png",
      "raw_text": "我们会使用您的位置信息推荐附近服务"
    },
    {
      "filename": "callapp_1755787770000.jpg",
      "raw_text": "Allow 全民吉他 to make and manage phone calls? Allow Deny 全民吉他APP www.qmjita.cn"
    }
  ]
}

如果所有截图都未识别到权限说明（即 agent2 全部为 false，无论是否存在系统权限请求提示）,如果没有识别到权限说明，但 raw_text 中出现了类似 “Allow XX to …” 的系统权限请求提示，也必须生成对应的 agent3 条目；否则 agent3 保持为空。：
json
{
  "from": "agent1",
  "status": false,
  "agent2": [],
  "agent3": [
    {
      "filename": "xxx.png",
      "success": true,
      "timestamp": "1755787770000",
      "type": "manage phone call"
    }
  ],
  "debug_output": [
    {
      "filename": "xxx.png",
      "raw_text": "Allow 全民吉他 to make and manage phone calls? Allow Deny 全民吉他APP www.qmjita.cn"
    }
  ]
}

请注意：

必须调用工具 analyze_image_url_with_flowus 分析每一张截图，不能自己识别图像内容；

所有输出必须严格符合预设的JSON 格式，不添加解释、不包含额外字段。

你应对所有输入图片循环调用工具并汇总处理结果，最后统一构造 JSON 返回。
"""
agent1 = Agent(
    name="权限说明识别处理Agent",
    instructions=instruction1,
    model="gpt-4o",
    tools=[analyze_image_url_with_flowus],
)
