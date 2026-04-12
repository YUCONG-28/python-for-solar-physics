# src/paper_reader_ollama/tools/custom_tool.py
from crewai_tools import BaseTool
import pdfplumber
import os

class LocalPDFReaderTool(BaseTool):
    name: str = "本地论文PDF阅读器"
    description: str = "读取本地PDF格式的学术论文全文，返回文本内容用于分析。"

    def _run(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return f"错误：文件 {file_path} 不存在。"
        try:
            full_text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + "\n"
            # DeepSeek-R1 的上下文较长，可以多取一些
            return full_text[:15000]
        except Exception as e:
            return f"读取PDF时出错: {str(e)}"