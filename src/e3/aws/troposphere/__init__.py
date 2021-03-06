from __future__ import annotations
from abc import ABC, abstractmethod
from troposphere import AWSObject, Template
from e3.aws import cfn, name_to_id
from e3.aws.troposphere.iam.policy_document import PolicyDocument
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional, Union


class Construct(ABC):
    """Represent one or multiple troposphere AWSObject.

    AWSObjects are accessible with resources attribute.
    """

    @abstractmethod
    def resources(self, stack: Stack) -> list[AWSObject]:
        """Return a list of troposphere AWSObject.

        Objects returned can be added to a troposphere template with
        add_resource Template method.

        :param stack: the stack that contains the construct
        """
        pass

    def cfn_policy_document(self, stack: Stack) -> PolicyDocument:
        """Return the IAM policy needed by CloudFormation to manage the stack.

        :param stack: the stack that contains the construct
        """
        return PolicyDocument([])

    def create_data_dir(self, root_dir: str) -> None:
        """Put data in root_dir before export to S3 bucket referenced by the stack.

        :param root_dir: local directory in which data should be stored. Data will
            be then uploaded to an S3 bucket accessible from the template. The
            target location is the one received by resources method. Note that
            the same root_dir is shared by all resources in your stack.
        """
        pass


class Stack(cfn.Stack):
    """Cloudformation stack using troposphere resources."""

    def __init__(
        self,
        stack_name: str,
        description: Optional[str] = None,
        cfn_role_arn: Optional[str] = None,
        s3_bucket: Optional[str] = None,
        s3_key: Optional[str] = None,
    ) -> None:
        """Initialize Stack attributes.

        :param stack_name: stack name
        :param cfn_role_arn: role asssumed by cloud formation to create the stack
        :param description: a description of the stack
        :param s3_bucket: s3 bucket used to store data needed by the stack
        :param s3_key: s3 prefix in s3_bucket in which data is stored
        """
        super().__init__(
            stack_name,
            cfn_role_arn=cfn_role_arn,
            description=description,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
        )
        self.constructs: list[Construct | AWSObject] = []
        self.template = Template()

    def add(self, element: Union[AWSObject, Construct, Stack]) -> Stack:
        """Add a Construct or AWSObject to the stack.

        :param element: if a resource an AWSObject or Construct add the resource
             to the stack. If a stack merge its resources into the current stack.
        """
        if isinstance(element, Stack):
            constructs = element.constructs

        else:
            constructs = [element]

        # Add the new constructs (non expanded)
        self.constructs += constructs

        # Update the template
        resources = []
        for construct in constructs:
            if isinstance(construct, Construct):
                resources += construct.resources(stack=self)
            if isinstance(construct, AWSObject):
                resources.append(construct)
        self.template.add_resource(resources)

        return self

    def cfn_policy_document(self) -> PolicyDocument:
        """Return stack necessary policy document for CloudFormation."""
        result = PolicyDocument([])
        for construct in self.constructs:
            if isinstance(construct, Construct):
                result += construct.cfn_policy_document(stack=self)

        return result

    def __getitem__(self, resource_name: str) -> AWSObject:
        """Return AWSObject associated with resource_name.

        :param resource_name: name of the resource to retrieve
        """
        return self.template.resources[name_to_id(resource_name)]

    def export(self) -> dict:
        """Export stack as dict.

        :return: a dict that can be serialized as YAML to produce a template
        """
        result = self.template.to_dict()
        if self.description is not None:
            result["Description"] = self.description
        return result

    def create_data_dir(self, root_dir: str) -> None:
        """Populate root_dir with data needed by all constructs in the stack.

        :param root_dir: the local directory in which to store the data
        """
        for construct in self.constructs:
            if isinstance(construct, Construct):
                construct.create_data_dir(root_dir)
