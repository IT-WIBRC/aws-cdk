import { Stack, StackProps } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { Instance, MachineImage, InstanceSize, InstanceClass, InstanceType, Vpc } from "aws-cdk-lib/aws-ec2";

export class CdkEc2DeployStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    const vpc = Vpc.fromLookup(
      this,
      "firstCdkVps",
      {
        isDefault: true,
      }
    );

    const instance = new Instance(
      this,
      "ecsInstance",
      {
        vpc,
        machineImage: MachineImage.latestAmazonLinux2023(),
        instanceType: InstanceType.of(InstanceClass.T2, InstanceSize.MICRO),
      }
    )
  }
}
