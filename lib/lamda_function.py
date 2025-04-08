import boto3
import os
import json
from datetime import datetime

def get_all_stack_names(cf_client):
    """Retrieves a list of names of all 'CREATE_COMPLETE' and 'UPDATE_COMPLETE' CloudFormation stacks."""
    stack_names = []
    paginator = cf_client.get_paginator('list_stacks')
    for page in paginator.paginate(StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE']):
        for stack_summary in page['StackSummaries']:
            stack_names.append(stack_summary['StackName'])
    return stack_names

def get_stack_tags(cf_client, stack_name):
    """Retrieves tags for a given CloudFormation stack."""
    try:
        stack_response = cf_client.describe_stacks(StackName=stack_name)
        return {tag['Key']: tag['Value'] for tag in stack_response['Stacks'][0].get('Tags', [])}
    except cf_client.exceptions.StackNotExistsException:
        print(f"Warning: Stack '{stack_name}' not found.")
        return {}
    except Exception as e:
        print(f"Error describing stack '{stack_name}': {e}")
        return {}

def get_resources_in_stack(tagging_client, stack_name):
    """Retrieves a list of resources belonging to a given CloudFormation stack."""
    resources = []
    response = tagging_client.get_resources(
        TagFilters=[
            {
                'Key': 'aws:cloudformation:stack-name',
                'Values': [stack_name]
            }
        ],
        ResourceTypeFilters=[]
    )
    resources.extend(response['ResourceTagMappingList'])
    while 'PaginationToken' in response:
        response = tagging_client.get_resources(
            TagFilters=[
                {
                    'Key': 'aws:cloudformation:stack-name',
                    'Values': [stack_name]
                }
            ],
            ResourceTypeFilters=[],
            PaginationToken=response['PaginationToken']
        )
        resources.extend(response['ResourceTagMappingList'])
    return resources

def find_missing_tags(resource_tags, stack_tags):
    """Compares resource tags with stack tags and returns a dictionary of missing tags."""
    missing_tags = {}
    for key, value in stack_tags.items():
        if key not in resource_tags:
            missing_tags[key] = value
    return missing_tags

def apply_tags_to_resource(tagging_client, resource_arn, tags_to_apply):
    """Applies the given tags to the specified resource."""
    try:
        if tags_to_apply:
            tagging_client.tag_resources(
                ResourceARNList=[resource_arn],
                Tags=tags_to_apply
            )
            return True
        return True
    except Exception as e:
        print(f"Error adding tags to {resource_arn}: {e}")
        return False

def lambda_handler(event, context):
    """
    Retrieves tags from all CloudFormation stacks in the region, checks if
    resources belonging to those stacks have the stack's tags, and adds
    the missing tags to the resources. This version uses the AWS server's
    default timezone for logging timestamps.
    """
    region = os.environ.get('AWS_REGION')
    if not region:
        log_message = "Error: AWS_REGION environment variable not set."
        print(log_message)
        return {
            'statusCode': 400,
            'body': log_message
        }

    cf_client = boto3.client('cloudformation', region_name=region)
    tagging_client = boto3.client('resourcegroupstaggingapi', region_name=region)

    now = datetime.now()  # Uses the AWS server's default timezone (UTC)
    timestamp_str = now.strftime('%Y-%m-%d %H:%M:%S %Z%z')

    print(f"[{timestamp_str}] Starting daily tag synchronization (server timezone)...")

    all_stack_names = get_all_stack_names(cf_client)
    print(f"[{timestamp_str}] Found {len(all_stack_names)} CloudFormation stacks to process.")

    for stack_name in all_stack_names:
        print(f"[{timestamp_str}] Processing stack: {stack_name}")
        stack_tags = get_stack_tags(cf_client, stack_name)
        print(f"[{timestamp_str}] Stack '{stack_name}' tags: {stack_tags}")

        if not stack_tags:
            print(f"[{timestamp_str}] Stack '{stack_name}' has no tags to apply.")
            continue

        resources_in_stack = get_resources_in_stack(tagging_client, stack_name)
        print(f"[{timestamp_str}] Found {len(resources_in_stack)} resources in stack '{stack_name}'.")

        for resource_mapping in resources_in_stack:
            resource_arn = resource_mapping['ResourceARN']
            resource_tags = {tag['Key']: tag['Value'] for tag in resource_mapping.get('Tags', [])}
            missing_tags = find_missing_tags(resource_tags, stack_tags)

            if missing_tags:
                print(f"[{timestamp_str}] Resource '{resource_arn}' in stack '{stack_name}' is missing tags: {missing_tags}")
                if apply_tags_to_resource(tagging_client, resource_arn, list(missing_tags.items())):
                    print(f"[{timestamp_str}] Successfully added missing tags to '{resource_arn}'.")
                else:
                    print(f"[{timestamp_str}] Failed to add missing tags to '{resource_arn}'.")
            else:
                print(f"[{timestamp_str}] Resource '{resource_arn}' in stack '{stack_name}' has all stack tags.")

    log_message = f"[{timestamp_str}] Successfully completed daily tag synchronization (server timezone)."
    print(log_message)
    return {
        'statusCode': 200,
        'body': log_message
    }

# Example invocation (no specific event needed for scheduled runs)
if __name__ == "__main__":
    os.environ['AWS_REGION'] = 'your-aws-region'  # Replace with your desired region
    result = lambda_handler(None, None)
    print(json.dumps(result, indent=2))