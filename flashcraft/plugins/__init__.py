from abc import ABC, abstractmethod, abstractstaticmethod
from dataclasses import dataclass
from datetime import datetime
import importlib
import inspect
from typing import List, cast


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

    def setup(self) -> None:
        pass

    @abstractmethod
    def validate_configuration(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def download_prefix(
        self,
        remote_prefix: str,
        local_path: str,
        *,
        delete_missing_from_local: bool = False,
    ):
        raise NotImplementedError

    @abstractmethod
    def upload_prefix(
        self,
        local_path: str,
        remote_prefix: str,
        *,
        delete_missing_from_remote: bool = False,
        skip_untouched_since: datetime = datetime.fromtimestamp(0),
    ):
        raise NotImplementedError


def get_storage_plugin(config: dict) -> StoragePlugin:
    mod = importlib.import_module(f"flashcraft.plugins.{config['plugin']}")
    candidates = []
    for name in dir(mod):
        obj = getattr(mod, name)
        if (
            inspect.isclass(obj)
            and issubclass(obj, StoragePlugin)
            and obj != StoragePlugin
        ):
            candidates.append(obj)
    assert len(candidates) == 1, candidates
    (cls,) = candidates
    plugin = cast(StoragePlugin, cls())
    for opt in plugin.get_options():
        setattr(plugin, opt.internal_name, config["options"][opt.internal_name])
    plugin.setup()
    return plugin


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
    runtime_config: str

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
