import json
import pathlib
import re
from typing import List

import boto3
from botocore.config import Config as BotoConfig

from flashcraft.plugins import (
    PluginConfigurationOption,
    ServerParameters,
    ServerPlugin,
    ServerStatus,
)


ARN_REGEX = re.compile(
    r"arn:aws:(?P<service>[^:/]+)::(?P<account>[^:/]+):(?P<type>[^:/]+)/(?P<resource>[^:/]+)"
)

USER_DATA = (
    r"""

yum install docker -y
docker run -d --rm --network host {self.docker_image}

""".strip()
    + "\n"
)

# curl -fsSL instances.vantage.sh/instances.json | jq 'map(select(.generation == "current" and (.arch | any(. == "x86_64")) and (.storage.size | not) and (.regions | length >= 10) and (.pricing["us-west-1"].linux.ondemand)) | {key: .instance_type, value: {cpu: .vCPU, memory: .memory, price: .pricing["us-west-1"].linux.ondemand}}) | from_entries' > amazon_ec2_pricing.json
PRICING_DATA_FILE = pathlib.Path(__file__).resolve().parent / "amazon_ec2_pricing.json"


class AmazonEC2ServerPlugin(ServerPlugin):
    @staticmethod
    def get_options():
        return [
            PluginConfigurationOption(
                display_name="AWS Access Key ID",
                internal_name="key_id",
                nonempty_required=True,
                sensitive_value=True,
            ),
            PluginConfigurationOption(
                display_name="AWS Access Key Secret",
                internal_name="key_secret",
                nonempty_required=True,
                sensitive_value=True,
            ),
            PluginConfigurationOption(
                display_name="AWS Region",
                internal_name="region",
                default_value="us-west-1",
                nonempty_required=True,
            ),
            PluginConfigurationOption(
                display_name="EC2 Subnet",
                internal_name="subnet",
                nonempty_required=True,
            ),
            PluginConfigurationOption(
                display_name="EC2 Security Group",
                internal_name="security_group",
                nonempty_required=True,
            ),
            PluginConfigurationOption(
                display_name="SSH key name",
                internal_name="ssh_key",
            ),
        ]

    key_id: str
    key_secret: str
    region: str
    subnet: str
    security_group: str
    ssh_key: str

    def setup(self) -> None:
        kwargs = {
            "config": BotoConfig(
                region_name=self.region,
            ),
            "aws_access_key_id": self.key_id,
            "aws_secret_access_key": self.key_secret,
        }
        self.ec2 = boto3.client("ec2", **kwargs)
        self.iam = boto3.client("iam", **kwargs)
        self.ssm = boto3.client("ssm", **kwargs)
        self.sts = boto3.client("sts", **kwargs)
        self.instance_id_by_server_id_cache = {}
        with open(PRICING_DATA_FILE) as f:
            self.available_instance_types = json.load(f)

    def validate_configuration(self) -> None:
        my_arn = self.sts.get_caller_identity()["Arn"]
        assert (match := re.fullmatch(ARN_REGEX, my_arn))
        assert match.group("type") == "user"
        user_name = match.group("resource")
        iam_statements = []
        for policy in self.iam.list_user_policies(UserName=user_name)["PolicyNames"]:
            raise NotImplementedError("FIXME")
        for policy in self.iam.list_attached_user_policies(UserName=user_name)[
            "AttachedPolicies"
        ]:
            policy_version = self.iam.get_policy(PolicyArn=policy["PolicyArn"])[
                "Policy"
            ]["DefaultVersionId"]
            iam_statements.extend(
                self.iam.get_policy_version(
                    PolicyArn=policy["PolicyArn"], VersionId=policy_version
                )["PolicyVersion"]["Document"]["Statement"]
            )
        raise NotImplementedError("FIXME")

    def list_running_server_ids(self) -> List[str]:
        server_ids = []
        for reservation in self.ec2.describe_instances(
            Filters=[
                {
                    "Name": "tag:flashcraft",
                    "Values": ["true"],
                }
            ]
        )["Reservations"]:
            for instance in reservation["Instances"]:
                for tag in instance["Tags"]:
                    if tag["Key"] == "flashcraft_server_id":
                        server_ids.append(tag["Value"])
                        break
        return server_ids

    def delete_servers_by_id(self, server_ids: List[str]) -> None:
        instance_ids = []
        for reservation in self.ec2.describe_instances(
            Filters=[
                {
                    "Name": "tag:flashcraft",
                    "Values": ["true"],
                },
                {
                    "Name": "tag:flashcraft_server_id",
                    "Values": server_ids,
                },
            ]
        )["Reservations"]:
            for instance in reservation["Instances"]:
                instance_ids.append(instance["InstanceId"])
        self.ec2.terminate_instances(InstanceIds=instance_ids)

    def _get_best_instance_type(self, params: ServerParameters):
        matching_instances = []
        for instance, info in self.available_instance_types.items():
            if (
                info["cpu"] * 1000 >= params.minimum_cpu_millicores
                and info["memory"] >= params.minimum_memory_megabytes * 1000
            ):
                matching_instances.append(instance)
        return min(
            matching_instances,
            key=lambda inst: self.available_instance_types[inst]["price"],
        )

    def create_server(self, server_id: str, params: ServerParameters) -> None:
        tags = [
            {
                "Key": "flashcraft",
                "Value": True,
            },
            {
                "Key": "flashcraft_server_id",
                "Value": server_id,
            },
        ]
        kwargs = {
            "ImageId": self.ssm.get_parameter(
                Name="/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-ebs"
            )["Parameter"]["Value"],
            "InstanceType": self._get_best_instance_type(params),
            "SubnetId": self.subnet,
            "DisableApiTermination": False,
            "InstanceInitiatedShutdownBehavior": "terminate",
            "UserData": USER_DATA,
            "NetworkInterfaces": [
                {
                    "AssociatePublicIpAddress": True,
                    "DeleteOnTermination": True,
                }
            ],
            "TagSpecifications": [
                {
                    "ResourceType": "instance",
                    "Tags": tags,
                },
                {
                    "ResourceType": "volume",
                    "Tags": tags,
                },
                {
                    "ResourceType": "network-interface",
                    "Tags": tags,
                },
            ],
            "HibernationOptions": {
                "Configured": False,
            },
            "MetadataOptions": {
                "HttpTokens": "required",
                "HttpPutResponseHopLimit": 1,
                "HttpEndpoint": "disabled",
                "HttpProtocolIpv6": "disabled",
                "InstanceMetadataTags": "disabled",
            },
            "MaintenanceOptions": {
                "AutoRecovery": "disabled",
            },
            "DisableApiStop": False,
        }
        if self.ssh_key:
            kwargs["KeyName"] = self.ssh_key
        sg_info = self.ec2.describe_security_groups(
            Filters={"Name": "group-id", "Values": [self.security_group]}
        )["SecurityGroups"][0]
        if self.ec2.describe_vpcs(
            Filters={"Name": "vpc-id", "Values": [sg_info["VpcId"]]}
        )["Vpcs"][0]["IsDefault"]:
            kwargs["SecurityGroups"] = [sg_info["GroupName"]]
        else:
            kwargs["SecurityGroupIds"] = [self.security_group]
        self.ec2.run_instances(**kwargs)

    def get_server_status_by_id(self, server_id: str) -> ServerStatus:
        instance_info = self.ec2.describe_instances(
            Filters=[
                {
                    "Name": "tag:flashcraft",
                    "Values": ["true"],
                },
                {
                    "Name": "tag:flashcraft_server_id",
                    "Values": [server_id],
                },
            ]
        )["Reservations"][0]["Instances"][0]
        if (state_name := instance_info["State"]["Name"]) != "running":
            return ServerStatus(
                appears_healthy=False,
                status=f"EC2 instance is {state_name}",
            )
        return ServerStatus(
            appears_healthy=True,
            status="EC2 instance is running",
            ipv4_address=instance_info["PublicIpAddress"],
            ipv6_address=instance_info["Ipv6Address"],
        )
