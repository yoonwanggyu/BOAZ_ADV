from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

from neo4j_graphrag.embeddings.base import Embedder

if TYPE_CHECKING:
    import openai

# OpenAI 임베딩을 위한 추상 클래스
class BaseOpenAIEmbeddings(Embedder, abc.ABC):
    client: openai.OpenAI

    def __init__(self, model: str = "text-embedding-3-large", dimensions: int = 256, **kwargs: Any) -> None:
        try:
            import openai
        except ImportError:
            raise ImportError(
                """Could not import openai python client.
                Please install it with `pip install "neo4j-graphrag[openai]"`."""
            )
        self.openai = openai
        self.model = model
        self.dimensions = dimensions
        self.client = self._initialize_client(**kwargs)

    @abc.abstractmethod
    def _initialize_client(self, **kwargs: Any) -> Any:
        """
        Initialize the OpenAI client.
        Must be implemented by subclasses.
        """
        pass

    def embed_query(self, text: str, **kwargs: Any) -> list[float]:
        # dimensions가 kwargs에 없으면 self.dimensions 사용
        if "dimensions" not in kwargs and self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        response = self.client.embeddings.create(input=text, model=self.model, **kwargs)
        embedding: list[float] = response.data[0].embedding
        return embedding

# OpenAI 임베딩을 위한 클래스
class SMCEmbeddings(BaseOpenAIEmbeddings):
    """
    OpenAI embeddings class.
    This class uses the OpenAI python client to generate embeddings for text data.

    Args:
        model (str): The name of the OpenAI embedding model to use. Defaults to "text-embedding-ada-002".
        kwargs: All other parameters will be passed to the openai.OpenAI init.
    """

    def _initialize_client(self, **kwargs: Any) -> Any:
        return self.openai.OpenAI(**kwargs) 