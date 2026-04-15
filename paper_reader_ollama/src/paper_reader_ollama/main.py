#!/usr/bin/env python
import glob
import os
import sys
import webbrowser

import markdown

from paper_reader_ollama.crew import PaperReaderOllamaCrew

os.environ["OPENAI_API_KEY"] = "not-needed"
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["NO_PROXY"] = "localhost,127.0.0.1,::1"
os.environ["no_proxy"] = "localhost,127.0.0.1,::1"


def save_and_open_html(md_content, title, filename_prefix):
    """将 Markdown 转换为精美的 HTML 并保存"""
    html_file_path = os.path.abspath(f"{filename_prefix}.html")
    md_file_path = os.path.abspath(f"{filename_prefix}.md")

    # 保存 Markdown 源码
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 转换为 HTML
    html_body = markdown.markdown(
        md_content, extensions=["tables", "fenced_code", "attr_list", "sane_lists"]
    )
    # 在 CSS 样式中加入图片美化
    """
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
    """

    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>

        <script>
        MathJax = {{
          tex: {{
            inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
            displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
            processEscapes: true,
            processEnvironments: true
          }},
          svg: {{
            fontCache: 'global'
          }}
        }};
        </script>
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        <style>
            body {{ font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif; max-width: 1000px; margin: 40px auto; padding: 20px; line-height: 1.8; color: #2c3e50; }}
            h1, h2, h3 {{ color: #1a252f; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; margin-top: 1.5em; }}
            /* 优化中英对照原文引用块的样式 */
            blockquote {{ border-left: 4px solid #e74c3c; margin: 1.5em 0; padding: 15px 20px; color: #555; background: #fdfefe; border-radius: 0 8px 8px 0; font-family: 'Georgia', serif; font-size: 0.95em; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }}
            code {{ background-color: #f8f9fa; padding: 3px 6px; border-radius: 4px; font-family: 'JetBrains Mono', Consolas, monospace; color: #e83e8c; font-size: 0.9em; }}
            pre code {{ color: #333; background: none; }}
            pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 8px; overflow-x: auto; }}
            /* 图片精美化排版 */
            img {{ max-width: 100%; height: auto; display: block; margin: 25px auto; border: 1px solid #e1e8ed; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); transition: transform 0.2s; }}
            img:hover {{ transform: scale(1.02); }}
            /* 表格样式 */
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
            th {{ background-color: #f8f9fa; }}
            .MathJax_Display {{ overflow-x: auto; overflow-y: hidden; padding: 10px 0; margin: 1em 0; }}
        </style>
    </head>
    <body>
        {html_body}
    </body>
    </html>
    """

    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # 自动调用系统默认浏览器
    webbrowser.open(f"file://{html_file_path}")
    print(f"✅ 报告已生成: {md_file_path}")


def run():
    print("=" * 50)
    print("🎓 欢迎使用研究生级文献阅读智能体")
    print("=" * 50)

    user_input = input(
        "👉 请输入单篇 arXiv ID、本地 PDF 路径，或【包含多个PDF的文件夹路径】: "
    ).strip()

    paper_sources = []

    # 1. 解析输入：判断是文件夹还是文件/ID
    if os.path.isdir(user_input):
        pdf_files = glob.glob(os.path.join(user_input, "*.pdf"))
        if not pdf_files:
            print(f"❌ 在文件夹 {user_input} 中没有找到任何 PDF 文件。")
            return
        paper_sources.extend(pdf_files)
        print(f"📂 成功扫描到 {len(paper_sources)} 篇 PDF 论文。")
    else:
        paper_sources = [p.strip() for p in user_input.split(",") if p.strip()]

    if not paper_sources:
        print("未检测到有效输入。")
        return

    # 2. 交互确认：是否开启对比功能
    enable_compare = False
    if len(paper_sources) > 1:
        print("\n" + "-" * 50)
        print("⚠️ 检测到多篇论文。您想要如何处理？")
        print(
            " [Y] 开启对比分析 (将所有论文合并喂给模型，寻找异同点。适合2-3篇，多了会超出模型记忆)"
        )
        print(" [N] 逐篇独立精读 (排队一篇一篇读，分别生成报告。适合大批量处理)")
        choice = input("请选择 (y/n，默认 n): ").strip().lower()
        if choice == "y":
            enable_compare = True

    # 3. 执行逻辑
    if enable_compare or len(paper_sources) == 1:
        # 模式 A：单篇阅读 或 多篇对比阅读（合并 Context）
        print(f"\n🚀 正在加载并分析内容，这可能需要几分钟...")
        all_papers_content = ""

        for idx, source in enumerate(paper_sources):
            if source.lower().endswith(".pdf"):
                content = PaperReaderOllamaCrew.pdf_tool._run(source)
            else:
                content = PaperReaderOllamaCrew.arxiv_tool._run(
                    f"https://arxiv.org/abs/{source}"
                )

            if "错误" in content or not content:
                print(f"⚠️ 跳过 {source}，读取失败。")
                continue

            all_papers_content += f"\n\n{'='*20}\n【论文 {idx+1}】来源：{os.path.basename(source)}\n{'='*20}\n{content}\n"

        if not all_papers_content.strip():
            return

        # 启动智能体
        inputs = {"paper_content": all_papers_content}
        result = PaperReaderOllamaCrew().crew().kickoff(inputs=inputs)

        # 保存并展示
        prefix = (
            "多文献对比报告"
            if enable_compare
            else f"文献精读报告_{os.path.basename(paper_sources[0]).replace('.pdf', '')}"
        )
        save_and_open_html(result.raw, prefix, prefix)

    else:
        # 模式 B：多篇独立精读（Loop 循环）
        print(f"\n🚀 开始批量逐篇阅读模式，共计 {len(paper_sources)} 篇任务。")
        for idx, source in enumerate(paper_sources):
            print("\n" + "=" * 50)
            print(
                f"⏳ 正在处理第 {idx+1}/{len(paper_sources)} 篇：{os.path.basename(source)}"
            )

            if source.lower().endswith(".pdf"):
                content = PaperReaderOllamaCrew.pdf_tool._run(source)
            else:
                content = PaperReaderOllamaCrew.arxiv_tool._run(
                    f"https://arxiv.org/abs/{source}"
                )

            if "错误" in content or not content:
                print(f"❌ 读取失败，已跳过。")
                continue

            inputs = {
                "paper_content": f"【论文】来源：{os.path.basename(source)}\n\n{content}"
            }

            # 为每篇论文独立实例化 Crew 并运行
            result = PaperReaderOllamaCrew().crew().kickoff(inputs=inputs)

            # 独立保存并打开
            filename_safe = (
                os.path.basename(source).replace(".pdf", "").replace(" ", "_")
            )
            save_and_open_html(
                result.raw, f"精读报告_{filename_safe}", f"独立精读报告_{filename_safe}"
            )

        print("\n🎉 所有批处理任务已完成！")


if __name__ == "__main__":
    run()
