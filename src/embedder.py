from __future__ import annotations
from typing import TYPE_CHECKING, Any
from neo4j_graphrag.embeddings.base import Embedder
import abc

if TYPE_CHECKING:
    import openai

class BaseOpenAIEmbeddings(Embedder, abc.ABC):
    client: openai.OpenAI

    def __init__(self, model: str = "text-embedding-3-large", dimensions: int = 256, **kwargs: Any) -> None:
        try:
            import openai
        except ImportError:
            raise ImportError(
                """openai python client를 import할 수 없습니다.
                `pip install "neo4j-graphrag[openai]"`로 설치해주세요."""
            )
        self.openai = openai
        self.model = model
        self.dimensions = dimensions
        self.client = self._initialize_client(**kwargs)

    @abc.abstractmethod
    def _initialize_client(self, **kwargs: Any) -> Any:
        """
        OpenAI 클라이언트를 초기화
        하위 클래스에서 구현
        """
        pass

    def embed_query(self, text: str, **kwargs: Any) -> list[float]:
        if "dimensions" not in kwargs and self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        response = self.client.embeddings.create(input=text, model=self.model, **kwargs)
        embedding: list[float] = response.data[0].embedding
        return embedding

class SMCEmbeddings(BaseOpenAIEmbeddings):
    """
    OpenAI 임베딩 클래스
    이 클래스는 OpenAI python client를 사용하여 텍스트 데이터의 임베딩을 생성

    Args:
        model (str): 사용할 OpenAI 임베딩 모델의 이름. 기본값은 "text-embedding-ada-002"
        kwargs: 기타 모든 매개변수는 openai.OpenAI 초기화에 전달
    """

    def _initialize_client(self, **kwargs: Any) -> Any:
        return self.openai.OpenAI(**kwargs) 