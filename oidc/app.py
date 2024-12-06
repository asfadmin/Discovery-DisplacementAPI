#!/usr/bin/env python3

# from https://docs.aws.amazon.com/cdk/v2/guide/serverless_example.html
import aws_cdk as cdk
from cdk_oidc_role_stack import CdkOIDCRoleStack
import os

app = cdk.App()

env = cdk.Environment(
    account=os.getenv('CDK_DEFAULT_ACCOUNT'),
    region=os.getenv('CDK_DEFAULT_REGION')
)
CdkOIDCRoleStack(
    app,
    env=env,
    description='OIDC Role Stack',
    construct_id='CdkOperaDispStack',
)
app.synth()
