#!/usr/bin/env python
import os
import sys
from paper_reader_ollama.crew import PaperReaderOllamaCrew
os.environ["OPENAI_API_KEY"] = "not-needed"
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"

def run():
    paper_source = input("请输入 arXiv 论文 ID (如 2304.08467) 或本地 PDF 文件路径: ").strip()

    if paper_source.lower().endswith('.pdf'):
        tool = PaperReaderOllamaCrew.pdf_tool
        paper_content = tool._run(paper_source)
        if "错误" in paper_content:
            print(paper_content)
            return
    else:
        tool = PaperReaderOllamaCrew.arxiv_tool
        paper_content = tool._run(f"https://arxiv.org/abs/{paper_source}")
        if not paper_content:
            print("无法获取论文内容，请检查 arXiv ID 或网络。")
            return

    inputs = {"paper_content": paper_content}
    result = PaperReaderOllamaCrew().crew().kickoff(inputs=inputs)
    print("\n" + "="*50)
    print("分析完成！报告已保存至 论文分析报告.md")
    print("="*50)

if __name__ == "__main__":
    run()