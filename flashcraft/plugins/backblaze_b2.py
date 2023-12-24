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
