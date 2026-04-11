# -*- coding: utf-8 -*-
"""
Created on Sat Apr 11 19:46:04 2026

@author: Lee
"""

import os
import fitz  # 处理 PDF
import docx  # [新增] 处理 Word
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool

# ==========================================
# 1. 配置核心大脑：重定向至 DeepSeek API
# ==========================================
os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com"
# 请务必将下方替换为你自己的真实 API Key
os.environ["OPENAI_API_KEY"] = "sk-39a1a06301a442feb6c9e578ce227992" 
os.environ["OPENAI_MODEL_NAME"] = "deepseek-reasoner" 

# ==========================================
# 2. 打造专属工具：PDF 提取器
# ==========================================
@tool("PDF Document Reader")
def read_pdf(file_path: str) -> str:
    """
    这是一个用于读取本地 PDF 文献的工具。
    输入参数：PDF 文件的绝对或相对路径。
    返回：PDF 文件中的纯文本内容。
    """
    try:
        doc = fitz.open(file_path)
        text = ""
        # 提取前 5 页内容作为演示，防止超长论文导致 Token 溢出
        for page_num in range(min(5, doc.page_count)):
            text += doc.load_page(page_num).get_text()
        return text
    except Exception as e:
        return f"读取 PDF 失败，请检查路径。错误信息: {e}"
    
@tool("Word Document Reader")
def read_docx(file_path: str) -> str:
    """
    这是一个用于读取本地 Word (.docx) 文献的工具。
    输入参数：Word 文件的绝对或相对路径。
    返回：Word 文件中的纯文本内容。
    """
    try:
        doc = docx.Document(file_path)
        text = ""
        # 遍历文档中的每一段并提取文字
        for para in doc.paragraphs:
            # 过滤掉空行，将内容拼接起来
            if para.text.strip(): 
                text += para.text + "\n"
        return text
    except Exception as e:
        return f"读取 Word 文件失败，请确认文件是否为 .docx 格式以及路径是否正确。错误信息: {e}"

# ==========================================
# 3. 定义智能体 (Agents) 团队
# ==========================================
physics_researcher = Agent(
    role='计算物理研究员',
    goal='精确读取文献，提取核心的演化公式、边界条件或数据处理逻辑',
    backstory='你是一位严谨的学者，擅长使用工具阅读不同格式的原始文献。',
    # [关键修改] 现在把两个工具都交给它！
    tools=[read_pdf, read_docx], 
    verbose=True,
    allow_delegation=False
    )

frontend_developer = Agent(
    role='Streamlit 架构工程师',
    goal='将物理模型转化为直观的 Web 交互界面',
    backstory='你精通 Python 和 Streamlit，擅长将抽象的参数转化为滑动条（Slider），并将计算结果用图表展示出来。你只输出高质量、带注释的 Python 代码。',
    verbose=True,
    allow_delegation=False
)

# ==========================================
# 4. 封装工作流逻辑 (支持动态参数)
# ==========================================
def analyze_and_build(target_pdf_path):
    # 根据传入的路径动态生成任务
    task_analyze = Task(
        description=f'使用你的工具读取位于 "{target_pdf_path}" 的文件。提取文中提出的核心物理方程或数据处理算法，并详细解释其输入参数和预期输出。',
        expected_output='包含核心物理公式和参数说明的详细中文报告。',
        agent=physics_researcher
    )

    task_code = Task(
        description='仔细阅读研究员提供的物理模型报告。编写一个完整的 app.py 脚本。该脚本需使用 Streamlit 搭建界面，包含侧边栏的参数调节器，并在主页面绘制模拟结果或数据图表。',
        expected_output='一段完整、可直接运行的纯 Python 代码（app.py）。',
        agent=frontend_developer
    )

    # 组装并启动
    my_crew = Crew(
        agents=[physics_researcher, frontend_developer],
        tasks=[task_analyze, task_code],
        process=Process.sequential 
    )
    
    return my_crew.kickoff()

# ==========================================
# 5. 交互式启动入口
# ==========================================
if __name__ == "__main__":
    print("==========================================")
    print("🤖 科研与工程 Agent 团队已就绪")
    print("==========================================\n")
    
    # 动态获取用户输入的文件路径
    user_input_path = input("📁 请输入你要分析的 PDF 文件路径 (例如: D:/papers/solar.pdf 或 sample.pdf):\n> ").strip()

    # 路径安全检查：提前拦截无效路径，避免白白消耗 API 
    if not os.path.exists(user_input_path):
        print(f"\n❌ 错误: 找不到文件 '{user_input_path}'。")
        print("💡 提示: 请检查拼写，或者如果是跨盘符，请提供完整的绝对路径。")
    else:
        print(f"\n✅ 成功锁定文件: {user_input_path}")
        print("🚀 Agent 团队正在开始阅读和思考，请稍候...\n")
        
        # 启动核心分析流程
        final_result = analyze_and_build(user_input_path)
        
        print("\n==========================================")
        print("🎉 任务完成！前端工程师提供的最终代码方案如下：\n")
        print(final_result)