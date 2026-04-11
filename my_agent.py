# -*- coding: utf-8 -*-
"""
Created on Sat Apr 11 19:46:04 2026

@author: Lee
"""

import os
import subprocess
import sys
import time
import glob
import zipfile
import io
import asyncio
import pickle
import json
from datetime import datetime
from typing import List, Dict, Any
import fitz  # 处理 PDF
import docx  # 处理 Word
from crewai import Agent, Task, Crew, Process
from crewai.tools import tool
from crewai_tools import SerperDevTool, ScrapeWebsiteTool

# ================================== ========
# 1. 配置核心大脑：重定向至 DeepSeek API
# ==========================================
os.environ["OPENAI_API_BASE"] = "https://api.deepseek.com"
# 请务必将下方替换为你自己的真实 API Key
os.environ["OPENAI_API_KEY"] = "sk-39a1a06301a442feb6c9e578ce227992" 
os.environ["OPENAI_MODEL_NAME"] = "deepseek-reasoner" 

search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()

# ==========================================
# 2. 打造专属工具：文件提取器
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
        return f"文件: {os.path.basename(file_path)}\n{text}"
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
        return f"文件: {os.path.basename(file_path)}\n{text}"
    except Exception as e:
        return f"读取 Word 文件失败，请确认文件是否为 .docx 格式以及路径是否正确。错误信息: {e}"

# ==========================================
# 3. 定义智能体 (Agents) 团队
# ==========================================
physics_researcher = Agent(
    role='计算物理研究员',
    goal='精确读取文献并补充最新研究背景',
    backstory='...',
    tools=[read_pdf, read_docx, search_tool], # 物理学家现在可以上网了！
    verbose=True,
    allow_delegation=False
)

analysis_synthesizer = Agent(
    role='科研综合分析专家',
    goal='对比分析多篇论文的核心发现，识别共性和差异，形成综合研究报告',
    backstory='你擅长从多篇相关文献中提取关键信息，进行交叉比对和综合分析，生成具有洞察力的总结报告。',
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

web_launcher = Agent(
    role='应用部署专家',
    goal='自动化部署和启动 Streamlit 应用',
    backstory='你擅长应用部署和自动化流程，能够确保生成的代码正确运行并启动网页服务。',
    verbose=True,
    allow_delegation=False
)

# ==========================================
# 4. 封装工作流逻辑 (支持多个文件)
# ==========================================
def analyze_and_build_multiple(file_paths: List[str]):
    """
    分析多个文件并构建应用的完整流程
    """
    
    # 第一步：创建针对每个文件的单独分析任务
    individual_analysis_tasks = []
    
    for idx, file_path in enumerate(file_paths, 1):
        file_name = os.path.basename(file_path)
        
        task = Task(
            description=f'''
            请分析第 {idx} 个文件: "{file_path}"。
            使用你的工具读取该文件，提取以下关键信息：
            1. 论文标题和研究目标
            2. 核心物理模型和方程
            3. 关键参数和变量定义
            4. 数据处理方法
            5. 主要结论和发现
            
            请为每个文件提供清晰、结构化的分析报告。
            ''',
            expected_output=f'文件 "{file_name}" 的详细分析报告，包含结构化信息。',
            agent=physics_researcher,
            output_file=f"analysis_report_{idx}_{os.path.splitext(file_name)[0]}.txt"
        )
        individual_analysis_tasks.append(task)
    
    # 第二步：综合分析任务
    synthesis_task = Task(
        description=f'''
        基于以上 {len(file_paths)} 个文件的分析报告，进行综合分析：
        
        1. 识别多篇论文的共同主题和核心物理原理
        2. 比较不同论文中方法的异同点
        3. 提取可用于构建交互式模型的关键参数
        4. 总结最具代表性的物理方程
        5. 提出一个综合的数据处理流程建议
        
        请提供一份综合研究报告，为后续的应用开发提供指导。
        ''',
        expected_output='一份综合研究报告，包含多篇论文的核心比较和统一框架。',
        agent=analysis_synthesizer,
        output_file="synthesis_report.txt"
    )
    
    # 第三步：代码生成任务
    code_generation_task = Task(
        description='''
        根据综合分析报告，开发一个 Streamlit Web 应用：
    
        要求：
        1. 创建一个完整的 app.py 文件
        2. 包含侧边栏，用于调节关键物理参数
        3. 实现多个标签页，展示不同论文的核心模型
        4. 包含数据可视化图表
        5. 添加交互式控件（滑块、选择器、按钮等）
        6. 提供模型对比功能
        7. 添加PDF导出功能：在侧边栏或主界面添加按钮，可以将当前分析结果导出为PDF报告
        8. 集成一键截图保存为PDF的功能（可选使用playwright）
        9. 添加会话状态保存/加载功能，便于下次恢复
    
        确保代码结构清晰，注释完整，可以直接运行。
        注意：生成的app.py应当包含必要的导入（如streamlit, reportlab, weasyprint, pickle等）以及对应的函数实现。
        ''',
        expected_output='一个完整、可直接运行的 Streamlit 应用代码（app.py），包含PDF导出和状态保存功能。',
        agent=frontend_developer,
        output_file="app.py"
    )
    
    # 第四步：应用启动任务
    launch_task = Task(
        description='''
        完成应用部署准备：
        1. 确保 app.py 文件已正确生成
        2. 检查必要的依赖包
        3. 准备启动脚本
        4. 验证应用可以正常运行
        ''',
        expected_output='应用部署准备完成，可以启动 Streamlit 服务。',
        agent=web_launcher
    )
    
    # 组装并启动
    all_tasks = individual_analysis_tasks + [synthesis_task, code_generation_task, launch_task]
    
    my_crew = Crew(
        agents=[physics_researcher, analysis_synthesizer, frontend_developer, web_launcher],
        tasks=all_tasks,
        process=Process.sequential 
    )
    
    return my_crew.kickoff()

def launch_streamlit_app():
    """
    启动生成的 Streamlit 应用
    """
    app_file = "app.py"
    
    if not os.path.exists(app_file):
        print(f"❌ 错误: 未找到 {app_file} 文件")
        return False
    
    print("🚀 正在启动 Streamlit 应用...")
    
    try:
        # 使用 subprocess 启动 Streamlit
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", app_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 等待几秒让应用启动
        time.sleep(3)
        
        print("✅ Streamlit 应用已启动！")
        print("🌐 请在浏览器中访问: http://localhost:8501")
        print("📋 按 Ctrl+C 停止应用")
        
        # 保持进程运行
        try:
            process.wait()
        except KeyboardInterrupt:
            print("\n🛑 正在停止应用...")
            process.terminate()
            
        return True
        
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

# ==========================================
# 6. 辅助文件生成函数
# ==========================================
def generate_helper_files(file_paths: List[str]) -> None:
    """
    生成一键启动、Docker、备份等辅助文件
    """
    # 1. 生成 start_app.py
    start_app_content = '''
# -*- coding: utf-8 -*-
import subprocess
import webbrowser
import time
import sys

def start_streamlit():
    """一键启动 Streamlit 应用"""
    # 检查依赖
    try:
        import streamlit
    except ImportError:
        print("正在安装依赖...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # 启动 Streamlit
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 等待应用启动
    time.sleep(3)
    
    # 自动打开浏览器
    webbrowser.open("http://localhost:8501")
    
    print("🌐 应用已启动: http://localhost:8501")
    print("📋 按 Ctrl+C 停止应用")
    
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\\n🛑 正在停止应用...")
        process.terminate()
        process.wait()
        print("✅ 应用已停止")

if __name__ == "__main__":
    start_streamlit()
'''
    with open("start_app.py", "w", encoding="utf-8") as f:
        f.write(start_app_content)
    print("✅ 已生成 start_app.py")
    
    # 2. 生成 requirements.txt
    req_content = '''streamlit>=1.28.0
fitz>=0.0.1.dev2
python-docx>=1.1.0
crewai>=0.28.0
reportlab>=4.0.0
weasyprint>=58.0
playwright>=1.40.0
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
sunpy>=5.0.0
astropy>=5.3.0
'''
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write(req_content)
    print("✅ 已生成 requirements.txt")
    
    # 3. 生成 Dockerfile
    dockerfile_content = '''FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
COPY . .
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
'''
    with open("Dockerfile", "w", encoding="utf-8") as f:
        f.write(dockerfile_content)
    print("✅ 已生成 Dockerfile")
    
    # 4. 生成 docker-compose.yml
    compose_content = '''version: '3.8'
services:
  literature-app:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./app.py:/app/app.py
      - ./data:/app/data
      - ./reports:/app/reports
'''
    with open("docker-compose.yml", "w", encoding="utf-8") as f:
        f.write(compose_content)
    print("✅ 已生成 docker-compose.yml")
    
    # 5. 生成 save_project.py
    save_project_content = '''# -*- coding: utf-8 -*-
import os
import shutil
import zipfile
from datetime import datetime
import glob

def backup_project():
    """备份整个项目"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backup_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    
    # 要备份的文件模式
    patterns = [
        "app.py",
        "my_agent.py",
        "requirements.txt",
        "start_app.py",
        "Dockerfile",
        "docker-compose.yml",
        "save_project.py",
        "*.txt",
        "*.json",
        "*.pdf"
    ]
    
    for pattern in patterns:
        for file in glob.glob(pattern):
            if os.path.isfile(file):
                shutil.copy2(file, backup_dir)
    
    # 创建ZIP压缩包
    zip_filename = f"literature_app_backup_{timestamp}.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(backup_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, backup_dir)
                zipf.write(file_path, arcname)
    
    # 清理临时备份目录
    shutil.rmtree(backup_dir)
    
    print(f"✅ 项目已备份到: {zip_filename}")
    return zip_filename

if __name__ == "__main__":
    backup_project()
'''
    with open("save_project.py", "w", encoding="utf-8") as f:
        f.write(save_project_content)
    print("✅ 已生成 save_project.py")
    
    # 6. 生成 PDF导出模块示例
    pdf_module_content = '''# pdf_export.py - PDF导出功能模块
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from weasyprint import HTML
import tempfile

def generate_simple_pdf(content_list):
    """生成简单PDF"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "文献分析报告")
    c.setFont("Helvetica", 12)
    y = 720
    for line in content_list:
        c.drawString(100, y, line)
        y -= 20
    c.save()
    buffer.seek(0)
    return buffer

def html_to_pdf(html_string):
    """HTML转PDF"""
    pdf_bytes = HTML(string=html_string).write_pdf()
    return io.BytesIO(pdf_bytes)

# 示例HTML模板
SAMPLE_HTML = """
<html>
<head><style>body{font-family:Arial; margin:40px;}</style></head>
<body>
    <h1>研究报告</h1>
    <p>自动生成的PDF报告，包含所有分析结果。</p>
</body>
</html>
"""
'''
    with open("pdf_export.py", "w", encoding="utf-8") as f:
        f.write(pdf_module_content)
    print("✅ 已生成 pdf_export.py")

# ==========================================
# 5. 交互式启动入口
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("🤖 科研与工程 Agent 团队 - 多论文分析版")
    print("=" * 60)
    
    # 获取多个文件路径
    print("\n📁 请按以下格式输入多个文件路径：")
    print("   1. 使用分号 (;) 分隔多个文件")
    print("   2. 支持 PDF 和 Word (.docx) 格式")
    print("   3. 示例: paper1.pdf; paper2.docx; research.docx")
    print("\n" + "-" * 40)
    
    user_input = input("请输入文件路径列表：\n> ").strip()
    
    # 处理输入，分割文件路径
    file_paths = [path.strip() for path in user_input.split(';') if path.strip()]
    
    if not file_paths:
        print("\n❌ 错误: 未提供有效的文件路径")
        sys.exit(1)
    
    # 验证所有文件是否存在
    valid_files = []
    invalid_files = []
    
    for path in file_paths:
        if os.path.exists(path):
            valid_files.append(path)
        else:
            invalid_files.append(path)
    
    if invalid_files:
        print(f"\n⚠️  以下文件不存在：")
        for f in invalid_files:
            print(f"   - {f}")
    
    if not valid_files:
        print("\n❌ 错误: 没有找到任何有效文件")
        sys.exit(1)
    
    print(f"\n✅ 成功锁定 {len(valid_files)} 个文件：")
    for i, path in enumerate(valid_files, 1):
        print(f"   {i}. {os.path.basename(path)} ({path})")
    
    # 询问是否继续
    proceed = input("\n是否开始分析？(y/n): ").strip().lower()
    if proceed != 'y':
        print("操作已取消")
        sys.exit(0)
    
    print("\n🚀 Agent 团队开始工作，请稍候...")
    print("=" * 60)
    
    # 启动核心分析流程
    try:
        final_result = analyze_and_build_multiple(valid_files)
        
        print("\n" + "=" * 60)
        print("🎉 分析任务完成！")
        print("=" * 60)
        
        # 生成辅助文件
        print("\n🛠️  生成辅助文件...")
        generate_helper_files(valid_files)
        
        # 显示生成的文件
        print("\n📁 生成的文件：")
        generated_files = ["app.py", "start_app.py", "requirements.txt", 
                          "Dockerfile", "docker-compose.yml", "save_project.py",
                          "pdf_export.py"]
        for i, path in enumerate(valid_files, 1):
            file_name = os.path.splitext(os.path.basename(path))[0]
            generated_files.append(f"analysis_report_{i}_{file_name}.txt")
        generated_files.append("synthesis_report.txt")
        
        for file in generated_files:
            if os.path.exists(file):
                print(f"   ✓ {file}")
            else:
                print(f"   ✗ {file} (未找到)")
        
        # 询问是否启动应用
        print("\n" + "=" * 60)
        launch_choice = input("是否立即启动 Streamlit 应用？(y/n): ").strip().lower()
        
        if launch_choice == 'y':
            print("\n" + "=" * 60)
            launch_streamlit_app()
        else:
            print("\n📋 手动启动应用：")
            print("   1. 一键启动: python start_app.py")
            print("   2. Docker启动: docker-compose up")
            print("   3. 直接运行: streamlit run app.py")
            print("   4. 备份项目: python save_project.py")
            
    except Exception as e:
        print(f"\n❌ 分析过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        print("💡 请检查 API 密钥和文件格式是否正确")
