import boto3
import json
import logging
import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TARGET_DESCRIPTION = 'Cdk customer managed'

def get_policies_by_description(iam_client, description, account_id):
    """
    Lists all customer-managed policies in the specified account and
    returns those with the specified description.
    """
    policies_with_description = []
    paginator = iam_client.get_paginator('list_policies')
    try:
        for page in paginator.paginate(Scope='Local'):  # Only list customer-managed policies
            for policy in page['Policies']:
                if policy.get('Description') == description:
                    policies_with_description.append(policy)
        return policies_with_description
    except Exception as e:
        logger.error(f"Error listing policies: {e}")
        return []

def get_attached_roles_for_policy(iam_client, policy_arn, policy_name):
    """Lists roles attached to a given IAM policy."""
    try:
        response = iam_client.list_entities_for_policy(PolicyArn=policy_arn, EntityFilter='Role')
        return response.get('PolicyRoles', [])
    except Exception as e:
        logger.error(f"Error listing roles for policy '{policy_name}' ({policy_arn}): {e}")
        return []

def get_role_tags(iam_client, role_name):
    """Gets tags for a given IAM role."""
    try:
        response = iam_client.list_role_tags(RoleName=role_name)
        return {tag['Key']: tag['Value'] for tag in response.get('Tags', [])}
    except Exception as e:
        logger.error(f"Error getting tags for role '{role_name}': {e}")
        return {}

def get_policy_tags(iam_client, policy_arn, policy_name):
    """Gets tags for a given IAM policy."""
    try:
        response = iam_client.list_policy_tags(PolicyArn=policy_arn)
        return {tag['Key']: tag['Value'] for tag in response.get('Tags', [])}
    except Exception as e:
        logger.error(f"Error getting tags for policy '{policy_name}' ({policy_arn}): {e}")
        return {}

def apply_tags_to_policy(iam_client, policy_arn, policy_name, tags_to_apply):
    """Applies the given tags to an IAM policy."""
    if not tags_to_apply:
        logger.info(f"No new tags to apply to policy '{policy_name}' ({policy_arn}).")
        return True
    try:
        iam_client.tag_policy(PolicyArn=policy_arn, Tags=[{'Key': k, 'Value': v} for k, v in tags_to_apply.items()])
        logger.info(f"Successfully applied tags: {tags_to_apply} to policy '{policy_name}' ({policy_arn}).")
        return True
    except Exception as e:
        logger.error(f"Error tagging policy '{policy_name}' ({policy_arn}) with tags {tags_to_apply}: {e}")
        return False

def handler(event, context):
    """
    Goes through all customer-managed IAM policies in the account,
    finds those with the specified description, gets their attached roles,
    copies their tags, and applies them to the policies.
    The AWS account ID is retrieved from the context object.
    """
    iam = boto3.client('iam')
    results = {
        'policies_processed': 0,
        'policies_tagged': 0,
        'errors': [],
        'processing_started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

    account_id = context.invoked_function_arn.split(':')[4]
    logger.info(f"Retrieved AWS account ID from context: {account_id}")

    target_policies = get_policies_by_description(iam, TARGET_DESCRIPTION, account_id)
    logger.info(f"Found {len(target_policies)} policies with description '{TARGET_DESCRIPTION}'.")

    for policy in target_policies:
        results['policies_processed'] += 1
        policy_arn = policy['Arn']
        policy_name = policy['PolicyName']
        logger.info(f"Processing policy: {policy_name} ({policy_arn}) with description '{policy.get('Description')}'")

        attached_roles = get_attached_roles_for_policy(iam, policy_arn, policy_name)
        if not attached_roles:
            logger.info(f"No roles attached to policy '{policy_name}'.")
            continue

        all_role_tags = {}
        for role in attached_roles:
            role_name = role['RoleName']
            role_tags = get_role_tags(iam, role_name)
            if role_tags:
                logger.info(f"Found tags for role '{role_name}' attached to '{policy_name}': {role_tags}")
                all_role_tags.update(role_tags)
            else:
                logger.info(f"No tags found for role '{role_name}' attached to '{policy_name}'.")

        if all_role_tags:
            policy_tags = get_policy_tags(iam, policy_arn, policy_name)
            tags_to_apply = {k: v for k, v in all_role_tags.items() if k not in policy_tags}

            if apply_tags_to_policy(iam, policy_arn, policy_name, tags_to_apply):
                results['policies_tagged'] += 1
            else:
                results['errors'].append(f"Failed to tag policy '{policy_name}'.")
        else:
            logger.info(f"No role tags found for any roles attached to policy '{policy_name}'.")

    results['processing_finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    logger.info(json.dumps(results, indent=2))
    return results