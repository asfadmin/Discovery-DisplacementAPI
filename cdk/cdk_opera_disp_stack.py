import json

from aws_cdk import (
    Duration,
    Stack,
    aws_apigateway as apigateway,
    aws_apigatewayv2 as apigatewayV2,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_ec2 as ec2,
    aws_iam as iam,
    # aws_efs as efs,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr_assets as ecr_assets,
    CfnOutput,
    CfnResource,
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
            ecs_vpc_kwargs = {}
        else:
            vpc = ec2.Vpc.from_lookup(self, "EDCVPC", vpc_id=vpc_id)
            subnet_selection = ec2.SubnetSelection(
                subnet_filters=[
                    ec2.SubnetFilter.by_ids(
                        subnet_ids=subnet_ids
                    )
                ]
            )
            security_group = ec2.SecurityGroup.from_security_group_id(
                self,
                'EDCSecurityGroup',
                security_group
            )

            lambda_vpc_kwargs = {
                'vpc': vpc,
                'vpc_subnets': subnet_selection,
                'security_groups': [security_group],
            }

            ecs_vpc_kwargs = {
                'vpc': vpc,
                'task_subnets': subnet_selection,
                'security_groups': [security_group],
            }

            apigateway_kwargs = {
                'endpoint_configuration': apigateway.EndpointConfiguration(
                    # https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.EndpointConfiguration.html
                    types=[apigateway.EndpointType.PRIVATE]
                ),
            }

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
            # architecture=_lambda.Architecture.ARM_64,
            **lambda_vpc_kwargs
        )


        self.opera_timeseries_function.add_to_role_policy(iam.PolicyStatement(
            actions=['s3:GetObject', 's3:ListBucket'],
            resources=[
                'arn:aws:s3:::asf-cumulus-test-opera-products/*',
                'arn:aws:s3:::asf-cumulus-test-opera-products/'
            ]
        ))

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
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS
            ),
            deploy_options=apigateway.StageOptions(
                access_log_destination=apigateway.LogGroupLogDestination(
                    logs.LogGroup(
                        self,
                        'DispServiceApiLogGroup',
                        retention=logs.RetentionDays.THREE_MONTHS,
                    )
                ),
                access_log_format=apigateway.AccessLogFormat.custom(json.dumps({
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
                })),
            ),
            **apigateway_kwargs
        )

        self.setup_fargate(dockerfileDir=dockerfileDir, ecs_vpc_kwargs=ecs_vpc_kwargs, apigateway_kwargs=apigateway_kwargs)
        

    def setup_fargate(self, dockerfileDir: str, ecs_vpc_kwargs: dict, apigateway_kwargs: dict):
        dockerImageAsset = ecr_assets.DockerImageAsset(self, "DispServiceDockerImage",
            directory=dockerfileDir,
            invalidation=ecr_assets.DockerImageAssetInvalidationOptions(
                build_args=False
            )
        )

        # self.fargate_service = ecs_patterns.NetworkLoadBalancedFargateService(
        #     self,
        #     'DispServiceFargateWebServer',
        #     memory_limit_mib=16384,
        #     cpu=2048,
        #     task_image_options=ecs_patterns.NetworkLoadBalancedTaskImageOptions(
        #         image=ecs.ContainerImage.from_docker_image_asset(dockerImageAsset),
        #         # container_port=8080,
        #     ),
        #     # listener_port=8080,
        #     public_load_balancer=False,
        #     health_check_grace_period=Duration.minutes(2),
        #     **ecs_vpc_kwargs
        # )
        # # self.fargate_service.service
        # self.fargate_service.task_definition.add_to_task_role_policy(
        #     iam.PolicyStatement(
        #                 actions=['s3:GetObject', 's3:ListBucket'],
        #                 resources=[
        #                     'arn:aws:s3:::asf-cumulus-test-opera-products/*',
        #                     'arn:aws:s3:::asf-cumulus-test-opera-products/'
        #                 ]
        #             )
        # )

        # cluster = ecs.Cluster(self, "OperaDispFargateCluster", vpc=ecs_vpc_kwargs['vpc'])
        # cluster.add_capacity(
        #     "DefaultAutoScalingGroupCapacity",
        #     instance_type=ec2.InstanceType("t2.xlarge"),
        #     desired_capacity=1
        # )
        task_definition = ecs.FargateTaskDefinition(
            self,
            "OperaDispFargateECSTask",
            cpu=2048,
            memory_limit_mib=16384
        )
        # port_mapping = ecs.PortMapping(container_port=8080)
        container = task_definition.add_container(
            id="OperaDispFargateContainer", 
            image=ecs.ContainerImage.from_docker_image_asset(dockerImageAsset),
        )#.add_port_mappings(port_mapping)

        container.add_port_mappings(
            ecs.PortMapping(
                container_port=8080,
                host_port=8080,
            )
        )
        task_definition.add_to_task_role_policy(
            iam.PolicyStatement(
                        actions=['s3:GetObject', 's3:ListBucket'],
                        resources=[
                            'arn:aws:s3:::asf-cumulus-test-opera-products/*',
                            'arn:aws:s3:::asf-cumulus-test-opera-products/'
                        ]
                    )
        )

        security_group = ec2.SecurityGroup(self, "OperaDispServiceSecurityGroup", vpc=ecs_vpc_kwargs['vpc'])
        security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(ecs_vpc_kwargs['vpc'].vpc_cidr_block),
            connection=ec2.Port.tcp(8080),
            description="Allow http from Opera Disp API Load Balancer"
        )

        cluster = ecs.Cluster(self, "OperaDispFargateCluster", vpc=ecs_vpc_kwargs['vpc'])
        fargate_service = ecs_patterns.NetworkLoadBalancedFargateService(
            self, 
            "OperaDispFargateService", 
            cluster=cluster,
            task_definition=task_definition,
            task_subnets= ecs_vpc_kwargs['task_subnets'],
            # listener_port=8080,
            security_groups= [*ecs_vpc_kwargs['security_groups'], security_group],
            memory_limit_mib=16384,
            cpu=2048,
            desired_count=1,
            max_healthy_percent=100,
            min_healthy_percent=0,
            # vpc=ecs_vpc_kwargs['vpc'],
            public_load_balancer=False,
        )

        # CfnOutput(
        #     self,
        #     "OperaDispFargateLoadBalancerDNS",
        #     value=fargate_service.load_balancer.load_balancer_dns_name,
        # )

        # self.nlb = self.fargate_service.load_balancer

        # create custom VPC integration linking API Gateway to our private Fargate Load Balancer
        # AWS cdk docs not comprehensive on this workflow, example taken from here
        # https://github.com/aws/aws-cdk/issues/26612#issuecomment-1664176179
        self.dispApi = apigatewayV2.HttpApi(
            self,
            'DispServiceFargateApi',
            create_default_stage=True,
            cors_preflight=apigatewayV2.CorsPreflightOptions(
                allow_origins=['*'],
                allow_methods=[apigatewayV2.CorsHttpMethod.POST, apigatewayV2.CorsHttpMethod.GET, apigatewayV2.CorsHttpMethod.HEAD, apigatewayV2.CorsHttpMethod.OPTIONS],
            ),
            # deploy_options=apigateway.StageOptions(
                # access_log_destination=apigateway.LogGroupLogDestination(
                #     logs.LogGroup(
                #         self,
                #         'DispServiceFargateApiLogGroup',
                #         retention=logs.RetentionDays.THREE_MONTHS,
                #     )
                # ), # type: ignore
            #     access_log_format=apigateway.AccessLogFormat.custom(json.dumps({
            #         'sourceIp': '$context.identity.sourceIp',
            #         'httpMethod': '$context.httpMethod',
            #         'path': '$context.path',
            #         'status': '$context.status',
            #         'responseLength': '$context.responseLength',
            #         'responseLatency': '$context.responseLatency',
            #         'requestTime': '$context.requestTime',
            #         'protocol': '$context.protocol',
            #         'userAgent': '$context.identity.userAgent',
            #         'requestId': '$context.requestId',
            #     })),
            # ),
            # **apigateway_kwargs
        )

        http_vpc_link = CfnResource(
            self,
            'DispAPIHTTPLink',
            type='AWS::ApiGatewayV2::VpcLink',
            # properties= {
                # 'Name': "V2 VPC Link",
                # 'SubnetIds': ecs_vpc_kwargs['task_subnets'],
                # 'SecurityGroupIds': ecs_vpc_kwargs['security_groups'],
        # }
        )

        # link = apigateway.VpcLink(
        #     self,
        #     "DispServiceFargateLink",
        #     description="Link between the network load balance for the fargate service",
        #     targets=[fargate_service.load_balancer],
        # )

        # self.dispApi.root.add_resource("{proxy+}")
        
        vpc_integration = apigatewayV2.CfnIntegration(
            self,
            'DispAPIVPCIntegration',
            description='DISP API VPC Integration',
            integration_type="HTTP_PROXY",
            connection_id=http_vpc_link.ref,
            connection_type='VPC_LINK',
            api_id=self.dispApi.http_api_id,
            integration_method='ANY',
            payload_format_version='1.0',
            integration_uri= fargate_service.listener.listener_arn, #"http://" + fargate_service.load_balancer.load_balancer_dns_name + "/{proxy}",
            # options=apigateway.IntegrationOptions(
            #     connection_type=apigateway.ConnectionType.VPC_LINK,
            #     request_parameters={
            #         "integration.request.path.proxy": "method.request.path.proxy"
            #     },
            #     vpc_link=link,
            #     integration_responses=[
            #         apigateway.IntegrationResponse(
            #             status_code="200",
            #             response_parameters={
            #                 "application/json": ""
            #             }
            #         )
            #     ]
            # ),
        )

        apigatewayV2.CfnRoute(
            self,
            'DispAPIRoute',
            api_id=self.dispApi.http_api_id,
            route_key='ANY /{proxy+}',
            target=f'integrations/{vpc_integration.ref}'
        )

        CfnOutput(
            self,
            'dispAPIUrl',
            value=self.dispApi.url, # type: ignore
        )

        # self.dispApi.root.add_method(
        #     "ANY",
        #     vpc_integration,
        #     request_parameters={"method.request.path.proxy": True},
        #     method_responses=[
        #         apigateway.MethodResponse(
        #             status_code="200"
        #         )
        #     ]
        # )
        # effectively do what LambdaRestApi.handler manually
        # default_method_options = apigateway.MethodOptions(
        #     request_parameters={"method.request.path.proxy": True},
        # )
        # self.dispApi.root.add_proxy(
        #     default_integration=vpc_integration,
        #     default_method_options=default_method_options,
        # )
