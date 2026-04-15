from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ArxivPaperTool

from paper_reader_ollama.tools.custom_tool import LocalPDFReaderTool


@CrewBase
class PaperReaderOllamaCrew:
    """研究生级论文精读团队"""

    ollama_llm = LLM(
        model="openai/deepseek-r1:7b",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        temperature=0.1,
    )

    # 实例化工具
    arxiv_tool = ArxivPaperTool()
    pdf_tool = LocalPDFReaderTool()

    @agent
    def 理论拆解员(self) -> Agent:
        return Agent(
            config=self.agents_config["理论拆解员"],
            llm=self.ollama_llm,
            tools=[self.arxiv_tool, self.pdf_tool],  # 理论拆解需要阅读工具
            verbose=True,
        )

    @agent
    def 复现审查员(self) -> Agent:
        return Agent(
            config=self.agents_config["复现审查员"],
            llm=self.ollama_llm,
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def Idea启发导师(self) -> Agent:
        return Agent(
            config=self.agents_config["Idea启发导师"],
            llm=self.ollama_llm,
            verbose=True,
            allow_delegation=False,
        )

    @task
    def 理论拆解任务(self) -> Task:
        return Task(
            config=self.tasks_config["理论拆解任务"],
        )

    @task
    def 复现审查任务(self) -> Task:
        return Task(
            config=self.tasks_config["复现审查任务"],
        )

    @task
    def 撰写导师报告任务(self) -> Task:
        return Task(
            config=self.tasks_config["撰写导师报告任务"],
            # 注意：这里的 output_file 我们已经在 main.py 中动态控制了，
            # 所以这里不再硬编码，直接去掉即可。
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
