from aws_cdk import (
    Duration,
    Stack,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
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
            'DispServiceDockerFunctionTest',
            code=_lambda.DockerImageCode.from_image_asset(
                dockerfileDir,
                platform=Platform.LINUX_ARM64,
            ),
            function_name='DispServiceDockerAPIFunctionTest',
            timeout=Duration.seconds(30),
            memory_size=10240,
            architecture=_lambda.Architecture.ARM_64,
        )

        api = apigateway.LambdaRestApi(
            self,
            'DispServiceApi',
            handler=opera_timeseries_function,
            proxy=True,
        )
