from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from typing import List


@dataclass
class PluginConfigurationOption:
    display_name: str
    internal_name: str
    default_value: str = ""
    nonempty_required: bool = False
    sensitive_value: bool = False


class StoragePlugin(ABC):
    @abstractstaticmethod
    def get_options() -> List[PluginConfigurationOption]:
        raise NotImplementedError


class ServerPluginMisconfiguredError(Exception):
    pass


@dataclass
class ServerParameters:
    minimum_cpu_millicores: int
    minimum_memory_megabytes: int
    minimum_disk_space_megabytes: int


@dataclass
class ServerStatus:
    appears_healthy: bool
    status: str
    ipv4_address: str = ""
    ipv6_address: str = ""


class ServerPlugin(ABC):
    docker_image: str

    @abstractstaticmethod
    def get_options() -> List[PluginConfigurationOption]:
        raise NotImplementedError

    def setup(self) -> None:
        pass

    @abstractmethod
    def validate_configuration(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_running_server_ids(self) -> List[str]:
        raise NotImplementedError

    @abstractmethod
    def delete_servers_by_id(self, server_ids: List[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_server(self, server_id: str, params: ServerParameters) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_server_status_by_id(self, server_id: str) -> ServerStatus:
        raise NotImplementedError
