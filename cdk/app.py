# from https://docs.aws.amazon.com/cdk/v2/guide/serverless_example.html
import os

import aws_cdk as cdk

# from cdk_fargate_opera_disp_stack import CdkFargateOperaDispStack
from cdk_opera_disp_stack import CdkOperaDispStack

app = cdk.App()

env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')
)
CdkOperaDispStack(
    app,
    env=env,
    description='Displacement Timeseries Stack',
    construct_id='CdkOperaDispStack',
    deployment_environment='test',
)

# CdkFargateOperaDispStack(
#     app,
#     env=env,
#     description='Displacement Timeseries Fargate Stack',
#     construct_id='CdkFargateOperaDispStack',
#     deployment_environment='test',
# )

app.synth()
