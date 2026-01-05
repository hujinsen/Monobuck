文本生成模型能够基于输入的提示词（Prompt）创作出逻辑清晰、连贯的文本。

文本生成模型所需的输入可以是简单的关键词、一句话概述或是更复杂的指令和上下文信息。模型通过分析海量数据学习语言模式，广泛应用于：

内容创作：生成新闻报道、商品介绍及短视频脚本。

客户服务：驱动聊天机器人提供全天候支持，解答常见问题。

文本翻译：实现跨语言的快速精准转换。

摘要生成：提炼长文、报告及邮件的核心内容。

法律文档编写：生成合同模板、法律意见书的基础框架。

更多示例可以参考文本生成样例。

模型选型建议
服务地域
阿里云百炼提供中国大陆（北京）地域和国际（新加坡）地域的模型服务，选择邻近地域调用可降低网络延迟。

通用模型
通义千问Max、通义千问Plus 和通义千问Flash 均已升级至Qwen3系列，并兼容OpenAI调用方式，适用于智能客服、文本创作、内容润色以及摘要总结等多种场景。

通义千问Plus：在效果、速度和成本上表现均衡，是多数场景的推荐选择。

通义千问Max ：通义千问系列效果最好的模型，适合处理复杂、多步骤任务。

通义千问Flash ：通义千问系列速度最快、成本极低的模型，适用于执行简单任务。

特定场景模型
针对明确的业务需求，阿里云百炼提供多种专用优化模型，覆盖代码能力、超长文档、翻译、数据挖掘、法律、意图理解、角色扮演、深入研究等领域。

多模态模型
通义千问VL（文+图->文）：具备图像理解能力，支持光学字符识别（OCR）、视觉推理和图文理解等任务。

通义千问Omni（全模态-> 文+音）：支持视频、音频、图片、文本等多种数据输入，生成文本和语音输出，以应对跨模态复杂任务。

语音识别模型（音->文）：识别并转写音频中的语音内容，支持中文（含粤语等各种方言）、英文、日语、韩语等。

第三方模型
阿里云百炼支持 DeepSeek、Kimi、GLM等众多知名的第三方大语言模型，完整模型列表请参考文本生成-第三方模型。

核心概念
文本生成模型的输入为提示词（Prompt），它由一个或多个消息（Message）对象构成。每条消息由角色（Role）和内容（Content）组成，具体为：

系统消息（System Message）：设定模型扮演的角色或遵循的指令。若不指定，默认为"You are a helpful assistant"。

用户消息（User Message）：用户向模型提出的问题或输入的指令。

助手消息（Assistant Message）：模型的回复内容。

输入为消息数组messages，通常包含一个 system 消息（推荐）和一个 user 消息。

system消息是可选的，但建议使用它来设定模型的角色和行为准则，以获得更稳定、一致的输出。
 
[
    {"role": "system", "content": "你是一个有帮助的助手，需要提供精准、高效且富有洞察力的回应，随时准备协助用户处理各种任务与问题。"},
    {"role": "user", "content": "你是谁？"}
]
输出的响应对象中会包含模型回复的内容，角色为assistant，内容是根据输入生成的回复。

 
{
    "role": "assistant",
    "content": "你好！我是Qwen，是阿里巴巴集团旗下的通义实验室自主研发的超大规模语言模型。我可以帮助你回答问题、创作文字、进行逻辑推理、编程等。我能够理解并生成多种语言，支持多轮对话和复杂任务处理。如果你有任何需要帮助的地方，尽管告诉我！"
}
快速开始
本节以调用通义千问模型为例，介绍文本生成模型的基础用法。若想获得更高质量的生成结果，可参考深度思考。

您需要已获取API Key并配置API Key到环境变量。如果通过OpenAI SDK或DashScope SDK进行调用，还需要安装SDK。

同步调用
OpenAI兼容DashScope
PythonJavaNode.js（HTTP）Go（HTTP）C#（HTTP）PHP（HTTP）curl
示例代码
 
import json
import os
from dashscope import Generation
import dashscope

# 若使用新加坡地域的模型，请释放下列注释
# dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "你是谁？"},
]
response = Generation.call(
    # 新加坡和北京地域的API Key不同。获取API Key：https://help.aliyun.com/zh/model-studio/get-api-key
    # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key = "sk-xxx",
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    model="qwen-plus",
    messages=messages,
    result_format="message",
)

if response.status_code == 200:
    print(response.output.choices[0].message.content)
    # 如需查看完整响应，请取消下列注释
    # print(json.dumps(response, default=lambda o: o.__dict__, indent=4))
else:
    print(f"HTTP返回码：{response.status_code}")
    print(f"错误码：{response.code}")
    print(f"错误信息：{response.message}")
    print("请参考文档：https://help.aliyun.com/zh/model-studio/developer-reference/error-code")
返回结果
 
我是通义千问，阿里巴巴集团旗下的通义实验室自主研发的超大规模语言模型。我可以帮助你回答问题、创作文字，比如写故事、写公文、写邮件、写剧本、逻辑推理、编程等等，还能表达观点，玩游戏等。如果你有任何问题或需要帮助，欢迎随时告诉我！
异步调用
处理高并发请求时，调用异步接口能有效提升程序效率。

OpenAI兼容DashScope
DashScope SDK的文本生成异步调用，目前仅支持Python。

 
# DashScope Python SDK版本需要不低于 1.19.0
import asyncio
import platform
from dashscope.aigc.generation import AioGeneration
import os
import dashscope 

# 若使用新加坡地域的模型，请释放下列注释
# dashscope.base_http_api_url = "https://dashscope-intl.aliyuncs.com/api/v1"

# 定义异步任务列表
async def task(question):
    print(f"发送问题: {question}")
    response = await AioGeneration.call(
        # 若没有配置环境变量，请用阿里云百炼API Key将下行替换为：api_key="sk-xxx",
        api_key=os.getenv("DASHSCOPE_API_KEY"),
        model="qwen-plus",  # 模型列表：https://help.aliyun.com/zh/model-studio/getting-started/models
        messages=[{"role": "system", "content": "You are a helpful assistant."},
                  {"role": "user", "content": question}],
        result_format="message",
    )
    print(f"模型回复: {response.output.choices[0].message.content}")

# 主异步函数
async def main():
    questions = ["你是谁？", "你会什么？", "天气怎么样？"]
    tasks = [task(q) for q in questions]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    # 设置事件循环策略
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # 运行主协程
    asyncio.run(main(), debug=False)
返回结果
注意：由于调用是异步的，实际运行时响应的返回顺序可能与示例不同。

 
发送问题: 你是谁？
发送问题: 你会什么？
发送问题: 天气怎么样？
模型回复: 你好！我是通义千问，阿里巴巴集团旗下的通义实验室自主研发的超大规模语言模型。我可以帮助你回答问题、创作文字，比如写故事、写公文、写邮件、写剧本、逻辑推理、编程等等，还能表达观点，玩游戏等。如果你有任何问题或需要帮助，欢迎随时告诉我！
模型回复: 您好！我目前无法实时获取天气信息。您可以告诉我您所在的城市或地区，我会尽力为您提供一些通用的天气建议或信息。或者您也可以使用天气应用查看实时天气情况。
模型回复: 我会很多技能，比如：

1. **回答问题**：无论是学术问题、生活常识还是专业知识，我都可以尝试帮你解答。
2. **创作文字**：我可以写故事、公文、邮件、剧本等各类文本。
3. **逻辑推理**：我可以帮助你解决一些逻辑推理问题，比如数学题、谜语等。
4. **编程**：我可以提供编程帮助，包括代码编写、调试和优化。
5. **多语言支持**：我支持多种语言，包括但不限于中文、英文、法语、西班牙语等。
6. **观点表达**：我可以为你提供一些观点和建议，帮助你做出决策。
7. **玩游戏**：我们可以一起玩文字游戏，比如猜谜语、成语接龙等。

如果你有任何具体的需求或问题，欢迎告诉我，我会尽力帮助你！
应用于生产环境
构建高质量的上下文
直接向大语言模型提供大量原始信息，会因上下文容量限制而导致成本增加和效果下降。

为解决此问题，上下文工程（Context Engineering）通过以下技术，将最相关、最精准的知识动态加载到模型的上下文中，从而显著提升生成质量和效率：

提示词工程（Prompt Engineering）：提示词（Prompt）是向大语言模型输入的文本指令。提示词工程通过精心设计和优化提示词，可以更精准地引导模型，使其输出结果更符合预期。这个过程包括以下步骤：

payukogjvzcwbvvabpvc.png

若想了解更多，可参考文生文Prompt指南、阿里云百炼 Prompt工程页面。

检索增强生成（RAG）：从外部知识库中检索信息，为模型提供回答依据。

工具调用（Tool）：使模型能调用搜索引擎、API等外部工具，以获取实时信息或执行特定任务。

记忆机制（Memory）：为模型建立长短期记忆，使其能够理解连续对话的历史信息。

若想系统了解，可参考阿里云大模型高级工程师ACP认证课程。

配置关键参数
消息角色设置
建议将角色定义、背景信息和行为规范置于系统消息（System Message）中，而将具体的单次任务指令通过用户消息（User Message）下达，以获得更稳定、一致的回答，优化模型表现。

回复多样性（temperature 和 top_p）
用于控制生成文本的多样性。数值越高，内容越多样，数值越低，内容越确定。

temperature 的取值范围为 [0, 2)，侧重调整随机性，而 top_p的取值范围为 [0, 1]，通过设定概率阈值筛选词语。为准确评估参数效果，建议每次只调整其中一个参数。

高多样性（建议temperature>0.7）：适用于创意写作、广告文案、头脑风暴、聊天应用等场景。

高确定性（建议temperature<0.3）：适用于事实问答、技术文档、法律文本、代码生成等要求准确的场景。

原理介绍

temperature：

temperature 越高，Token 概率分布变得更平坦（即高概率 Token 的概率降低，低概率 Token 的概率上升），使得模型在选择下一个 Token 时更加随机。

temperature 越低，Token 概率分布变得更陡峭（即高概率 Token 被选取的概率更高，低概率 Token 的概率更低），使得模型更倾向于选择高概率的少数 Token。

top_p：

top_p 采样是指从最高概率（最核心）的 Token 集合中进行采样。它将所有可能的下一个 Token 按概率从高到低排序，然后从概率最高的 Token 开始累加概率，直至概率总和达到阈值（例如80%，即 top_p=0.8），最后从这些概率最高、概率总和达到阈值的 Token 中随机选择一个用于输出。

top_p 越高，考虑的 Token 越多，因此生成的文本更多样。

top_p 越低，考虑的 Token 越少，因此生成的文本更集中和确定。

不同场景的参数配置示例

更多功能
上文介绍了基础的交互方式。针对更复杂的场景，可参考：

多轮对话：适用于追问、信息采集等需要连续交流的场景。

流式输出：适用于聊天机器人、实时代码生成等需要即时响应的场景，可以提升用户体验，并避免因响应时间过长导致的超时。

深度思考：适用于复杂推理、策略分析等需要更高质量、更具条理的深度回答的场景。

结构化输出：当需要模型按稳定的 JSON 格式回复，以便于程序调用或数据解析时使用。

前缀续写：适用于代码补全、长文写作等需要模型接续已有文本的场景。

API 参考
模型调用的完整参数列表，请参考 OpenAI 兼容 API 参考和DashScope API 参考。

常见问题
Q：通义千问 API 为何无法分析网页链接？
A：通义千问 API 本身不具备直接访问和解析网页链接的能力，可以通过Function Calling、MCP等功能，或结合 Python 的 Beautiful Soup 等网页抓取工具读取网页信息。

Q：网页端通义千问和通义千问 API 的回复为什么不一致？
A：网页端通义千问在通义千问 API 的基础上做了额外的工程优化，因此可以达到解析网页、联网搜索、画图、制作 PPT等功能，这些本身并不属于大模型 API 的能力，可以通过联网搜索、Function Calling、MCP等功能优化模型的效果。

Q：如何处理模型超时的情况？
A：使用流式输出可避免超时。

非流式调用若超过 300 秒未完成，服务将中断请求，但返回已生成的内容，且不再报超时错误。此时响应头将包含x-dashscope-partialresponse: true，表示返回的是超时前的部分结果。

支持该机制的模型如下：

支持的模型

qwen-max-2024-09-19 及之后的模型

qwen-plus-2024-11-25 及之后的模型

qwen-flash-2025-07-28 及之后的模型

qwen-turbo-2024-11-01 及之后的模型

qwen-vl-max-2025-01-25 及之后的模型

qwen-vl-plus-2025-01-02 及之后的模型

qwen-long-2025-01-25 及之后的模型

qwen3 开源模型（qwen3-235b-a22b、qwen3-32b、qwen3-30b-a3b、qwen3-14b、qwen3-8b、qwen3-4b、qwen3-1.7b、qwen3-0.6b）

qwen2.5开源模型（qwen2.5-14b-instruct-1m、qwen2.5-7b-instruct-1m、qwen2.5-72b-instruct、qwen2.5-32b-instruct、qwen2.5-14b-instruct、qwen2.5-7b-instruct、qwen2.5-3b-instruct、qwen2.5-1.5b-instruct、qwen2.5-0.5b-instruct）

若无法获取响应头参数（例如通过 SDK 调用），可通过 finish_reason字段辅助判断，若为null，表示生成内容不完整（但不一定是触发了超时）。
大模型可续写不完整的内容，详情请参见：基于不完整输出进行续写。

Java SDK 暂不支持前缀续写功能。