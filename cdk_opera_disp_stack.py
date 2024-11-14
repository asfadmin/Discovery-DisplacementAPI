from aws_cdk import (
    Duration,
    Stack,
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
        # self.create_lambda_layers()
        self.create_lambda_functions()
        # Define the Lambda function resource

    def create_lambda_functions(self):
        """
        Create the Lambda Functions for the FastAPI server.
        """
        dockerfileDir = './'
        self.opera_timeseries_function = _lambda.DockerImageFunction(
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

        self.lambda_function_url = self.opera_timeseries_function.add_function_url(
            auth_type=_lambda.FunctionUrlAuthType.NONE
        )
