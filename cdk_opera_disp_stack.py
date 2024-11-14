from aws_cdk import (
    Duration,
    Stack,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    aws_logs as logs
)
from aws_cdk.aws_ecr_assets import Platform
from constructs import Construct


class CdkOperaDispStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str, deployment_environment: str, **kwargs
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)
        self.deployment_environment = deployment_environment

        dockerfileDir = './'
        opera_timeseries_function = _lambda.DockerImageFunction(
            self,
            'DispServiceDockerFunction',
            code=_lambda.DockerImageCode.from_image_asset(
                dockerfileDir,
                platform=Platform.LINUX_ARM64,
            ),
            function_name='DispServiceDockerAPIFunction',
            timeout=Duration.seconds(30),
            memory_size=10240,
            architecture=_lambda.Architecture.ARM_64,
            log_group=logs.LogGroup(
                self,
                'DispServiceDockerFunctionLogGroup',
                log_group_name='/aws/lambda/DispServiceDockerFunction',
                retention=logs.RetentionDays.THREE_MONTHS,
            ),
        )

        api = apigateway.LambdaRestApi(
            self,
            'DispServiceApi',
            handler=opera_timeseries_function,
            proxy=True,
            deploy_options=apigateway.StageOptions(
                access_log_destination=apigateway.LogGroupLogDestination(
                    logs.LogGroup(
                        self,
                        'DispServiceApiLogGroup',
                        retention=logs.RetentionDays.THREE_MONTHS,
                    )
                ),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                )
            )
        )
