from typing import Any, List, Optional, Dict
from crewai.llms.base_llm import BaseLLM
from pydantic import Field, model_validator
import ollama

class OllamaNativeLLM(BaseLLM):
    """符合 CrewAI BaseLLM 接口的 Ollama 原生客户端"""
    
    model_name: str = Field(default="deepseek-r1:7b", alias="model")
    base_url: str = Field(default="http://localhost:11434")
    temperature: float = 0.1
    max_tokens: int = 8192
    client: Optional[Any] = None
    
    @model_validator(mode="after")
    def init_client(self) -> "OllamaNativeLLM":
        self.client = ollama.Client(host=self.base_url)
        return self
    
    def call(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """执行模型调用并返回文本响应"""
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    "temperature": kwargs.get("temperature", self.temperature),
                    "num_predict": kwargs.get("max_tokens", self.max_tokens),
                    "num_ctx": 16384,  # <-- 加上这行！手动将上下文窗口扩大到 16K
                }
            )
            return response["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama 调用失败: {str(e)}") from e

    async def ainvoke(self, *args, **kwargs):
        """异步调用（暂不实现）"""
        raise NotImplementedError("异步调用未实现，请使用同步 call 方法")