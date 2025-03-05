from .state import GraphState
from abc import ABC, abstractmethod

# 기본 노드 
# 나중에 core에서 이 노드를 상속받아 구현하게 되어있음

class BaseNode(ABC):
    def __init__(self, verbose=False, **kwargs):
        self.name = self.__class__.__name__
        self.verbose = verbose

    @abstractmethod
    def execute(self, state: GraphState) -> GraphState:
        pass

    def log(self, message: str, **kwargs):
        if self.verbose:
            print(f"[{self.name}] {message}")
            for key, value in kwargs.items():
                print(f"  {key}: {value}")

    def __call__(self, state: GraphState) -> GraphState:
        return self.execute(state)
