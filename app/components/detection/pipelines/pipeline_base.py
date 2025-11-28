from abc import abstractmethod


class PipelineBase:
    @abstractmethod
    def get_jpeg(self) -> bytes | None:
        pass

    @abstractmethod
    def get_depth_jpeg(self) -> bytes | None:
        pass

    @abstractmethod
    def iterate(self): 
        pass