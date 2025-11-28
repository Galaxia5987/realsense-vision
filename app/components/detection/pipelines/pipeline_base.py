from abc import abstractmethod


class PipelineBase:
    @abstractmethod
    def get_jpeg(self) -> bytes:
        pass

    @abstractmethod
    def get_depth_jpeg(self) -> bytes:
        pass

    @abstractmethod
    def iterate(self): 
        pass