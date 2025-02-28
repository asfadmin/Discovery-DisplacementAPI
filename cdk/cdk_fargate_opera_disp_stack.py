import json

from aws_cdk import (
    Stack,
    aws_apigateway as apigateway,
    aws_logs as logs,
    aws_ec2 as ec2,
    aws_iam as iam,
    # aws_efs as efs,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_ecr_assets as ecr_assets,
    CfnOutput,
    CfnResource,
    aws_events,
)
from constructs import Construct


class CdkFargateOperaDispStack(Stack):
    def __init__(
        self, scope: Construct, construct_id: str, deployment_environment: str, **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.deployment_environment = deployment_environment

        try:
            vpc_id = self.node.try_get_context('vpc_id')
            subnet_ids = self.node.try_get_context('subnet_ids').split(',')
            security_group = self.node.try_get_context('security_group')
            security_group_ids = security_group
            if not vpc_id:
                raise AttributeError()

        except AttributeError:
            fargate_vpc_kwargs = {}
            vpc_link_kwargs = {}
        else:
            vpc = ec2.Vpc.from_lookup(self, 'EDCVPC', vpc_id=vpc_id)
            subnet_selection = ec2.SubnetSelection(
                subnet_filters=[ec2.SubnetFilter.by_ids(subnet_ids=subnet_ids)]
            )
            security_group = ec2.SecurityGroup.from_security_group_id(
                self, 'EDCSecurityGroup', security_group
            )
            service_sg = ec2.SecurityGroup(self, "OperaDispServiceSecurityGroup", vpc=vpc)
            service_sg.add_ingress_rule(
                peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
                connection=ec2.Port.tcp(80),
            )

            fargate_vpc_kwargs = {
                'vpc': vpc,
                'task_subnets': subnet_selection,
                'security_groups': [security_group, service_sg],
            }

            vpc_link_kwargs = {
                'subnet_ids': subnet_ids,
                # 'security_group_ids': [security_group_ids],
            }

        dockerfileDir = '../'

        dockerImageAsset = ecr_assets.DockerImageAsset(
            self,
            'DispServiceDockerImage',
            directory=dockerfileDir,
            invalidation=ecr_assets.DockerImageAssetInvalidationOptions(build_args=False),
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
            self, 'OperaDispFargateECSTask', cpu=2048, memory_limit_mib=16384
        )
        # port_mapping = ecs.PortMapping(container_port=8080)
        container = task_definition.add_container(
            id='OperaDispFargateContainer',
            image=ecs.ContainerImage.from_docker_image_asset(dockerImageAsset),
        )  # .add_port_mappings(port_mapping)

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
                    'arn:aws:s3:::asf-cumulus-test-opera-products/',
                ],
            )
        )

        # security_group = ec2.SecurityGroup(
        #     self, 'OperaDispServiceSecurityGroup', vpc=ecs_vpc_kwargs['vpc']
        # )
        # security_group.add_ingress_rule(
        #     peer=ec2.Peer.ipv4(ecs_vpc_kwargs['vpc'].vpc_cidr_block),
        #     connection=ec2.Port.tcp(8080),
        #     description='Allow http from Opera Disp API Load Balancer',
        # )



        # cluster = ecs.Cluster(self, 'OperaDispFargateCluster', vpc=ecs_vpc_kwargs['vpc'])

        fargate_service = ecs_patterns.NetworkLoadBalancedFargateService(
            self,
            'OperaDispFargateService',
            task_definition=task_definition,
            memory_limit_mib=16384,
            cpu=2048,
            desired_count=1,
            min_healthy_percent=0,
            max_healthy_percent=100,
            public_load_balancer=False,
            listener_port=8080,
            **fargate_vpc_kwargs,
        )
       
        self.nlb = fargate_service.load_balancer
        # create custom VPC integration linking API Gateway to our private Fargate Load Balancer
        # AWS cdk docs not comprehensive on this workflow, example taken from here
        # https://github.com/aws/aws-cdk/issues/26612#issuecomment-1664176179
        # self.dispApi = apigatewayV2.HttpApi(
        #     self,
        #     'DispServiceFargateApi',
        #     api_name='DispServiceFargateApi',
        #     create_default_stage=True,
        #     cors_preflight=apigatewayV2.CorsPreflightOptions(
        #         allow_origins=['*'],
        #         allow_methods=[
        #             apigatewayV2.CorsHttpMethod.POST,
        #             apigatewayV2.CorsHttpMethod.GET,
        #             apigatewayV2.CorsHttpMethod.HEAD,
        #             apigatewayV2.CorsHttpMethod.OPTIONS,
        #         ],
        #     ),
        # )

        link = apigateway.VpcLink(
            self,
            'DispAPIFargateV1HTTPLink',
            vpc_link_name='Opera Disp Fargate V1 VPC Link',
            targets=[self.nlb]
            # subnet_ids=vpc_link_kwargs['subnet_ids']
        )
        integration = apigateway.Integration(
            type=apigateway.IntegrationType.HTTP_PROXY,
            integration_http_method='ANY',
            options=apigateway.IntegrationOptions(
                connection_type=apigateway.ConnectionType.VPC_LINK, vpc_link=link
            ),
        )

        self.disp_api = apigateway.RestApi(
            self,
            'DispServiceFargateStackApi',
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
            endpoint_configuration= apigateway.EndpointConfiguration(
                # https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_apigateway.EndpointConfiguration.html
                types=[apigateway.EndpointType.PRIVATE]
            ),
            default_integration=integration,
        )
        self.disp_api.root.add_proxy()


        CfnOutput(
            self,
            'dispAPIV1Url',
            value=self.disp_api.url,  # type: ignore
        )
