from aws_cdk import (
    Stack,
    cloudformation_include as cfn_inc
)
from constructs import Construct


class CdkOIDCRoleStack(Stack):

    def __init__(
        self, scope: Construct, construct_id: str, **kwargs
    ) -> None:

        super().__init__(scope, construct_id, **kwargs)

        # Only needs to be done once per account
        self.oidc_role_template = cfn_inc.CfnInclude(
            self,
            "OIDCProviderTemplate",
            template_file="oidc-provider.yml"
        )

        self.oidc_role_template = cfn_inc.CfnInclude(
            self,
            "OIDCRoleTemplate",
            template_file="github-actions-oidc.yml"
        )
