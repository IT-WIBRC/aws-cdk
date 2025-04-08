import { Stack, StackProps, CfnOutput, App, Duration } from 'aws-cdk-lib';
import { Rule, Schedule } from 'aws-cdk-lib/aws-events';
import { LambdaFunction as EventsLambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import { Function, Runtime, Code } from 'aws-cdk-lib/aws-lambda';
import { Role, ServicePrincipal, ManagedPolicy, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

interface GlobalTagSyncSchedulerStackProps extends StackProps {
  lambdaFunctionArn: string;
}

export class GlobalTagSyncSchedulerStack extends Stack {
  constructor(scope: Construct, id: string, props: GlobalTagSyncSchedulerStackProps) {
    super(scope, id, props);

    const ruleName = 'DailyTagSyncRuleServerTime';

    // Create a CloudWatch Events rule to trigger the Lambda function daily at midnight UTC (server time)
    const dailyTagSyncRule = new Rule(this, 'DailyTagSyncScheduleServerTime', {
      ruleName: ruleName,
      schedule: Schedule.cron({ minute: '0', hour: '0', day: '*', month: '*', year: '*' }), // Midnight UTC
      description: 'Triggers the tag synchronization Lambda daily at midnight UTC (server time)',
      enabled: true,
    });

    // Add the Lambda function as a target for the rule
    dailyTagSyncRule.addTarget(
      new EventsLambdaFunction(Function.fromFunctionArn(this, 'TagSyncLambda', props.lambdaFunctionArn))
    );

    // Output the name of the created CloudWatch Events rule
    new CfnOutput(this, 'DailyTagSyncRuleNameServerTime', {
      value: dailyTagSyncRule.ruleName,
      description: 'Name of the CloudWatch Events rule that triggers the tag synchronization Lambda daily at midnight UTC',
    });
  }
}

interface GlobalTagSyncRoleStackProps extends StackProps {
  lambdaFunctionName: string;
}

export class GlobalTagSyncRoleStack extends Stack {
  public readonly lambdaExecutionRole: Role;
  public readonly lambdaFunction: Function;

  constructor(scope: Construct, id: string, props: GlobalTagSyncRoleStackProps) {
    super(scope, id, props);

    const roleName = 'GlobalTagSyncerRole'; // More descriptive role name

    // Create the IAM role for the Lambda function
    this.lambdaExecutionRole = new Role(this, 'TagSyncerRole', {
      roleName: roleName,
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      description: 'IAM role for the Global Tag Synchronization Lambda function',
    });

    // Attach the basic execution policy for Lambda
    this.lambdaExecutionRole.addManagedPolicy(
      ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole')
    );

    // Attach a policy that allows listing all CloudFormation stacks (read-only)
    this.lambdaExecutionRole.addToPolicy(
      new PolicyStatement({
        actions: ['cloudformation:ListStacks', 'cloudformation:DescribeStacks'],
        resources: ['*'],
      })
    );

    // Attach a policy that allows getting and tagging resources across all stacks
    this.lambdaExecutionRole.addToPolicy(
      new PolicyStatement({
        actions: ['tag:GetResources', 'tag:TagResources'],
        resources: ['*'],
        conditions: {
          StringLike: {
            'aws:ResourceTag/aws:cloudformation:stack-name': '*',
          },
        },
      })
    );

    // Create the Lambda function
    this.lambdaFunction = new Function(this, 'TaggingFunction', {
      runtime: Runtime.PYTHON_3_11, // Or your preferred runtime
      handler: 'lambda_handler.lambda_handler',
      code: Code.fromAsset('.'), // Assuming Python code is at the root
      role: this.lambdaExecutionRole,
      functionName: props.lambdaFunctionName,
      environment: {
        'AWS_REGION': this.region,
      },
      timeout: Duration.minutes(5), // Adjust as needed
    });

    // Output the ARN of the Lambda function
    new CfnOutput(this, 'TaggingLambdaFunctionArn', {
      value: this.lambdaFunction.functionArn,
      description: 'ARN of the Global Tag Synchronization Lambda Function',
    });
  }
}

const app = new App();

const lambdaFunctionName = 'GlobalTagSyncer'; // More consistent function name

// Create the IAM Role and Lambda Function Stack
const roleAndLambdaStack = new GlobalTagSyncRoleStack(app, 'GlobalTagSyncerStack', { // More consistent stack name
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
  lambdaFunctionName: lambdaFunctionName,
});

// Create the Scheduler Stack, passing the Lambda Function ARN
new GlobalTagSyncSchedulerStack(app, 'GlobalTagSyncerSchedulerServerTime', { // New stack name for server time scheduler
  env: { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION },
  lambdaFunctionArn: roleAndLambdaStack.lambdaFunction.functionArn,
});

app.synth();