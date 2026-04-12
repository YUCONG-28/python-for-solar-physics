from crewai import Agent, Crew, Process, Task, LLM  # <-- 引入官方 LLM
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ArxivPaperTool
from paper_reader_ollama.tools.custom_tool import LocalPDFReaderTool
from langchain_ollama import ChatOllama

@CrewBase
class PaperReaderOllamaCrew:
    """三智能体协作的论文阅读团队"""

    # 直接使用 CrewAI 内置的 LLM 类，它会自动处理各种复杂的上下文和通信问题！
    ollama_llm = LLM(
        model="openai/deepseek-r1:7b",  # <--- 换成我们刚生成的 16k 版本
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        temperature=0.1,
        # max_tokens=2048, # 保持注释状态
        # num_ctx=16384,   # <--- 把这行删掉！不要在代码里传了
    )

    # 实例化工具
    arxiv_tool = ArxivPaperTool()
    pdf_tool = LocalPDFReaderTool()

    @agent
    def 摘要提取员(self) -> Agent:
        return Agent(
            config=self.agents_config["摘要提取员"],
            llm=self.ollama_llm,
            tools=[self.arxiv_tool, self.pdf_tool],
            verbose=True,
        )

    @agent
    def 批判分析员(self) -> Agent:
        return Agent(
            config=self.agents_config["批判分析员"],
            llm=self.ollama_llm,
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def 报告撰写员(self) -> Agent:
        return Agent(
            config=self.agents_config["报告撰写员"],
            llm=self.ollama_llm,
            verbose=True,
            allow_delegation=False,
        )

    @task
    def 提取摘要任务(self) -> Task:
        return Task(
            config=self.tasks_config["提取摘要任务"],
        )

    @task
    def 批判分析任务(self) -> Task:
        return Task(
            config=self.tasks_config["批判分析任务"],
        )

    @task
    def 撰写报告任务(self) -> Task:
        return Task(
            config=self.tasks_config["撰写报告任务"],
            output_file="论文分析报告.md"
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )