import json

from aws_cdk import (
    Duration,
    Stack,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_efs as efs,
    RemovalPolicy,
)
from constructs import Construct


class CdkOperaDispStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, deployment_environment: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.deployment_environment = deployment_environment

        try:
            vpc_id = self.node.try_get_context('vpc_id')
            subnet_ids = self.node.try_get_context('subnet_ids').split(',')
            security_group = self.node.try_get_context('security_group')
            if not vpc_id:
                raise AttributeError()

        except AttributeError:
            lambda_vpc_kwargs = {}
            apigateway_kwargs = {}
            # file_system = None
        else:
            vpc = ec2.Vpc.from_lookup(self, 'EDCVPC', vpc_id=vpc_id)
            subnet_selection = ec2.SubnetSelection(
                subnet_filters=[ec2.SubnetFilter.by_ids(subnet_ids=subnet_ids)]
            )
            security_group = ec2.SecurityGroup.from_security_group_id(
                self, 'EDCSecurityGroup', security_group
            )

            lambda_vpc_kwargs = {
                'vpc': vpc,
                'vpc_subnets': subnet_selection,
                'security_groups': [security_group],
            }
            

            apigateway_kwargs = {
                'endpoint_configuration': apigateway.EndpointConfiguration(
                    # https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.EndpointConfiguration.html
                    types=[apigateway.EndpointType.PRIVATE]
                ),
            }

            file_system = efs.FileSystem(
                self,
                "OPERADispAPIEFS",
                vpc=vpc,
                performance_mode=efs.PerformanceMode.MAX_IO,
                throughput_mode=efs.ThroughputMode.BURSTING,
                lifecycle_policy=efs.LifecyclePolicy.AFTER_1_DAY,  # files are not transitioned to infrequent access (IA) storage by default
                out_of_infrequent_access_policy=efs.OutOfInfrequentAccessPolicy.AFTER_1_ACCESS,  # files are not transitioned back from (infrequent access) IA to primary storage by default
                # transition_to_archive_policy=efs.LifecyclePolicy.AFTER_7_DAYS,  # files are not transitioned to Archive by default
                replication_overwrite_protection=efs.ReplicationOverwriteProtection.ENABLED,
                removal_policy=RemovalPolicy.DESTROY,
            )
            self.access_point = file_system.add_access_point(
                "DispAPIAccessPoint",
                path="/",
                create_acl=efs.Acl(
                    owner_uid="1001", owner_gid="1001", permissions="750"
                ),
                # enforce the POSIX identity so lambda function will access with this identity
                posix_user=efs.PosixUser(uid="1001", gid="1001"),
            )
        
        

        dockerfileDir = '../'
        self.opera_timeseries_function = _lambda.DockerImageFunction(
            self,
            'DispServiceDockerFunction',
            code=_lambda.DockerImageCode.from_image_asset(
                dockerfileDir,
                # platform=Platform.LINUX_ARM64,
            ),
            function_name='DispServiceDockerAPIFunction',
            timeout=Duration.seconds(60),
            memory_size=10240,
            filesystem=_lambda.FileSystem.from_efs_access_point(
                ap=self.access_point, mount_path="/mnt/filesystem"
            ) if self.access_point else None,
            **lambda_vpc_kwargs,
        )


        self.opera_timeseries_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=['s3:GetObject', 's3:ListBucket'],
                resources=[
                    'arn:aws:s3:::asf-cumulus-test-opera-products/*',
                    'arn:aws:s3:::asf-cumulus-test-opera-products/',
                    'arn:aws:s3:::asf-cumulus-prod-opera-products/*',
                    'arn:aws:s3:::asf-cumulus-prod-opera-products/',
                ],
            )
        )

        # file_system = efs.FileSystem(self, "MyEfsFileSystem",
        #     vpc=vpc,
        #     lifecycle_policy=efs.LifecyclePolicy.AFTER_1_DAY,  # files are not transitioned to infrequent access (IA) storage by default
        #     performance_mode=efs.PerformanceMode.GENERAL_PURPOSE,  # default
        #     out_of_infrequent_access_policy=efs.OutOfInfrequentAccessPolicy.AFTER_1_ACCESS,  # files are not transitioned back from (infrequent access) IA to primary storage by default
        #     transition_to_archive_policy=efs.LifecyclePolicy.AFTER_7_DAYS,  # files are not transitioned to Archive by default
        #     replication_overwrite_protection=efs.ReplicationOverwriteProtection.ENABLED,
        #     throughput_mode=efs.ThroughputMode.BURSTING,
        #     one_zone=True,
        #     # vpc_subnets=ec2.SubnetSelection(
        #     # availability_zones=["us-west-1b"]
        #     # )
        # )

        apigateway.LambdaRestApi(
            self,
            'DispServiceApi',
            handler=self.opera_timeseries_function,
            proxy=True,
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS, allow_methods=apigateway.Cors.ALL_METHODS
            ),
            deploy_options=apigateway.StageOptions(
                access_log_destination=apigateway.LogGroupLogDestination(
                    logs.LogGroup(
                        self,
                        'DispServiceApiLogGroup',
                        retention=logs.RetentionDays.THREE_MONTHS,
                    )
                ), # type: ignore
                access_log_format=apigateway.AccessLogFormat.custom(
                    json.dumps(
                        {
                            'sourceIp': '$context.identity.sourceIp',
                            'httpMethod': '$context.httpMethod',
                            'path': '$context.path',
                            'status': '$context.status',
                            'responseLength': '$context.responseLength',
                            'responseLatency': '$context.responseLatency',
                            'requestTime': '$context.requestTime',
                            'protocol': '$context.protocol',
                            'userAgent': '$context.identity.userAgent',
                            'requestId': '$context.requestId',
                        }
                    )
                ),
            ),
            **apigateway_kwargs,
        )
