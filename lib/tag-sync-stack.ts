import { Stack, Duration, App, type StackProps, Fn } from 'aws-cdk-lib';
import { Function, Runtime, Code } from 'aws-cdk-lib/aws-lambda';
import { Role, ServicePrincipal, PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { Rule, Schedule } from 'aws-cdk-lib/aws-events';
import { LambdaFunction } from 'aws-cdk-lib/aws-events-targets';
import { Construct } from 'constructs';
import { join } from 'path';

export class TagSyncStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // Define the IAM role for the Lambda function
    const lambdaRole = new Role(this, 'TagSyncLambdaRole', {
      assumedBy: new ServicePrincipal('lambda.amazonaws.com'),
      description: 'IAM role for the tag synchronization Lambda function',
    });

    // Grant necessary IAM permissions to the role
    lambdaRole.addToPolicy(
      new PolicyStatement({
        actions: [
          'iam:ListPolicies',
          'iam:GetPolicyVersion',
          'iam:ListPolicyVersions',
          'iam:ListAttachedRolePolicies',
          'iam:ListRolesForPolicy',
          'iam:GetRole',
          'iam:ListRoleTags',
          'iam:TagPolicy',
          'iam:UntagPolicy', // Consider if you need this
        ],
        resources: ['*'], // Consider scoping down resources for better security
      })
    );
    lambdaRole.addToPolicy(
      new PolicyStatement({
        actions: ['logs:CreateLogGroup', 'logs:CreateLogStream', 'logs:PutLogEvents'],
        resources: ['arn:aws:logs:*:*:*'],
      })
    );

    const tagSyncLambda = new Function(this, 'TagSyncLambda', {
      runtime: Runtime.PYTHON_3_12, // Choose your preferred runtime
      handler: 'main.copy_role_tags_to_customer_managed_policy',
      code: Code.fromAsset(join(__dirname, 'lambda')), // Assuming 'lambda' folder is at the same level
      role: lambdaRole,
      timeout: Duration.minutes(5), // Adjust as needed
      environment: {
        AWS_ACCOUNT_ID: Fn.ref('AWS::AccountId'),
      }, // Add any environment variables if required
    });

    const rule = new Rule(this, 'DailyTagSyncRule', {
      schedule: Schedule.cron({ minute: '0', hour: '0', day: '*', month: '*', year: '*' }),
      description: 'Triggers the tag synchronization Lambda daily at 00:00 UTC (1:00 AM WAT)',
      targets: [new LambdaFunction(tagSyncLambda)],
    });
  }
}

// How to use it in the main file
const app = new App();
new TagSyncStack(app, 'TagSyncStack', {
  env: { region: 'your-aws-region' }, // Replace 'your-aws-region'
});