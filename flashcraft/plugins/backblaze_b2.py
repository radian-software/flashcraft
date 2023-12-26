from datetime import datetime
from io import TextIOWrapper
from pathlib import Path
import sys
import time
from typing import cast
from b2sdk.scan.folder import B2Folder, LocalFolder

from b2sdk.scan.policies import ScanPoliciesManager
from b2sdk.sync.policy import NewerFileSyncMode
from b2sdk.sync.report import SyncReport
from b2sdk.sync.sync import KeepOrDeleteMode, Synchronizer as B2Synchronizer
from b2sdk.transfer.outbound.upload_source import UploadMode
from b2sdk.v2 import B2Api, InMemoryAccountInfo as B2InMemoryAccountInfo, parse_folder

from flashcraft.plugins import PluginConfigurationOption, StoragePlugin


class BackblazeB2StoragePlugin(StoragePlugin):
    def get_options(self):
        return [
            PluginConfigurationOption(
                display_name="Application Key ID",
                internal_name="key_id",
                nonempty_required=True,
                sensitive_value=True,
            ),
            PluginConfigurationOption(
                display_name="Application Key Secret",
                internal_name="key_secret",
                nonempty_required=True,
                sensitive_value=True,
            ),
            PluginConfigurationOption(
                display_name="Bucket name",
                internal_name="bucket",
                nonempty_required=True,
            ),
            PluginConfigurationOption(
                display_name="Bucket prefix",
                internal_name="prefix",
            ),
        ]

    key_id: str
    key_secret: str
    bucket: str
    prefix: str

    authorized: bool = False

    def setup(self) -> None:
        self.b2 = B2Api(B2InMemoryAccountInfo())

    def _ensure_authorized(self) -> None:
        if not self.authorized:
            self.b2.authorize_account("production", self.key_id, self.key_secret)
            self.authorized = True

    def validate_configuration(self) -> None:
        self._ensure_authorized()

    def _get_remote_path(self, remote_path: str) -> str:
        return (self.prefix.strip("/") + "/" + remote_path.strip("/")).lstrip("/")

    def download_prefix(
        self,
        remote_prefix: str,
        local_path: str,
        *,
        delete_missing_from_local: bool = False,
    ):
        self._ensure_authorized()
        Path(local_path).mkdir(exist_ok=True)
        B2Synchronizer(
            max_workers=10,
            policies_manager=ScanPoliciesManager(exclude_all_symlinks=True),
            newer_file_mode=NewerFileSyncMode.REPLACE,
            keep_days_or_delete=KeepOrDeleteMode.DELETE
            if delete_missing_from_local
            else KeepOrDeleteMode.NO_DELETE,
            upload_mode=UploadMode.INCREMENTAL,
        ).sync_folders(
            B2Folder(self.bucket, self._get_remote_path(remote_prefix), self.b2),
            LocalFolder(str(local_path)),
            now_millis=int(round(time.time() * 1000)),
            reporter=SyncReport(cast(TextIOWrapper, sys.stdout), no_progress=True),
        )

    def upload_prefix(
        self,
        local_path: str,
        remote_prefix: str,
        *,
        delete_missing_from_remote: bool = False,
        skip_untouched_since: datetime = datetime.fromtimestamp(0),
    ):
        self._ensure_authorized()
        B2Synchronizer(
            max_workers=10,
            policies_manager=ScanPoliciesManager(
                exclude_all_symlinks=True,
                exclude_modified_before=int(skip_untouched_since.timestamp() * 1000),
            ),
            newer_file_mode=NewerFileSyncMode.REPLACE,
            keep_days_or_delete=KeepOrDeleteMode.DELETE
            if delete_missing_from_remote
            else KeepOrDeleteMode.NO_DELETE,
            upload_mode=UploadMode.INCREMENTAL,
        ).sync_folders(
            LocalFolder(str(local_path)),
            B2Folder(self.bucket, self._get_remote_path(remote_prefix), self.b2),
            now_millis=int(round(time.time() * 1000)),
            reporter=SyncReport(cast(TextIOWrapper, sys.stdout), no_progress=True),
        )
