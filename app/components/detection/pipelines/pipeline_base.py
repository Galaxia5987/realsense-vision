from abc import abstractmethod


class PipelineBase:
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the pipeline"""
        pass

    @abstractmethod
    def get_jpeg(self) -> bytes | None:
        pass

    @abstractmethod
    def get_depth_jpeg(self) -> bytes | None:
        pass

    def get_output(self):
        return None

    @abstractmethod
    def iterate(self): 
        pass
