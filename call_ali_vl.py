import os
import base64
import json
from openai import OpenAI

# 将图像编码为 Base64 格式
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key="xxxxxx",  # 从环境变量中获取 API Key
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",  # 设置基础 URL
)

# # 将本地图像路径替换为你的实际路径
# base64_image = encode_image("path/to/your/image.png")

# # 调用 qwen-vl-plus 模型
# completion = client.chat.completions.create(
#     model="qwen-vl-7B",  # 使用 qwen-vl-plus 模型
#     messages=[
#         {
#             "role": "system",
#             "content": [{"type": "text", "text": "你是一个帮助识别学号和姓名的助手。如果图片中有学号和姓名，请以 JSON 格式返回；如果没有，则返回 None。"}],
#         },
#         {
#             "role": "user",
#             "content": [
#                 {
#                     "type": "image_url",
#                     "image_url": {"url": f"data:image/png;base64,{base64_image}"},  # 传入 Base64 编码的图像
#                 },
#                 {"type": "text", "text": "请识别图片中是否有学号和姓名，如果有，请以 JSON 格式返回，格式为：{'学号': 'xxx', '姓名': 'xxx'}；如果没有，则返回 None。"},  # 用户问题
#             ],
#         },
#     ],
# )

# # 解析模型的回复
# response = completion.choices[0].message.content

# # 尝试将回复解析为 JSON，如果失败则返回 None
# try:
#     result = json.loads(response) if response != "None" else None
# except json.JSONDecodeError:
#     result = None

# # 输出结果
# print(result)

def parse_model_response(response):
    """
    处理模型返回的文本，确保其可以被正确解析为 JSON 格式
    :param response: 模型返回的文本
    :return: 处理后的 JSON 字符串
    """
    try:
        # 去除可能的 ```json\n 和 \n```
        response = response.replace("```json\n", "").replace("\n```", "")
        # 去除可能的单引号，替换为双引号
        # response = response.replace("'", '"')
        # 尝试加载 JSON，如果成功则返回处理后的文本
        json.loads(response)
        return response
    except json.JSONDecodeError:
        # 如果解析失败，返回 None
        return None

def recognize_student_info(image_bytes):
    """
    封装好的学生信息识别函数
    :param image_bytes: 图像字节数据
    :return: 识别结果字典 {'学号': 'xxx', '姓名': 'xxx'} 或 None
    """
    # 将图像字节转换为Base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    try:
        # 调用阿里云视觉模型
        completion = client.chat.completions.create(
            model="qwen2.5-vl-72b-instruct",
            # model="qwen-vl-plus",
            messages=[
                {
                    "role": "system",
                    "content": [{"type": "text", "text": "你是一个帮助识别学号和姓名的助手。如果图片中有学号和姓名，请以 JSON 格式返回；如果没有，则返回 None。"}],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                        },
                        {"type": "text", "text": "请识别图片中是否有学号和姓名，如果有，请以 JSON 格式返回，格式为：{'学号': 'xxx', '姓名': 'xxx'}；如果没有，则返回 None。"},
                    ],
                },
            ],
        )
        
        # 解析响应
        response = completion.choices[0].message.content
        # print(response)
        # 处理模型返回的文本
        processed_response = parse_model_response(response)
        return json.loads(processed_response) if processed_response else None
    except Exception as e:
        print(f"OCR识别失败: {e}")
        return None
