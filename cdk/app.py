#!/usr/bin/env python3

# from https://docs.aws.amazon.com/cdk/v2/guide/serverless_example.html
import aws_cdk as cdk
from cdk_opera_disp_stack import CdkOperaDispStack
import os

app = cdk.App()

env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION')
)
CdkOperaDispStack(
    app,
    env=env,
    description='Displacement Timeseries Stack',
    construct_id='CdkOperaDispStack',
    deployment_environment='test',
)
app.synth()
