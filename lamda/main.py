import boto3
import json
import logging

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_customer_managed_policies(iam_client):
    """Lists all customer-managed IAM policies in the account."""
    policies = []
    paginator = iam_client.get_paginator('list_policies')
    try:
        for page in paginator.paginate(Scope='Local', PolicyUsageFilter='PermissionsPolicy'):
            for policy in page['Policies']:
                if policy['PolicyType'] == 'CustomerManaged':
                    policies.append(policy)
        return policies
    except Exception as e:
        logger.error(f"Error listing customer-managed policies: {e}")
        return []

def get_attached_roles_for_policy(iam_client, policy_arn, policy_name):
    """Lists roles attached to a given IAM policy."""
    try:
        response = iam_client.list_roles_for_policy(PolicyArn=policy_arn)
        return response.get('Roles', [])
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
        iam_client.tag_policy(PolicyArn=policy_arn, Tags=[{'Key': key, 'Value': value} for key, value in tags_to_apply.items()])
        logger.info(f"Successfully applied tags: {tags_to_apply} to policy '{policy_name}' ({policy_arn}).")
        return True
    except Exception as e:
        logger.error(f"Error tagging policy '{policy_name}' ({policy_arn}) with tags {tags_to_apply}: {e}")
        return False

def copy_role_tags_to_customer_managed_policy(event, context):
    """
    Goes through all customer-managed IAM policies, gets roles, copies tags, and applies them.
    Includes robust error handling and logging.
    """
    iam = boto3.client('iam')
    results = {
        'policies_processed': 0,
        'policies_tagged': 0,
        'errors': []
    }

    customer_managed_policies = get_customer_managed_policies(iam)
    if not customer_managed_policies:
        logger.info("No customer-managed policies found or an error occurred while listing.")
        return results

    for policy in customer_managed_policies:
        results['policies_processed'] += 1
        policy_arn = policy['Arn']
        policy_name = policy['PolicyName']
        logger.info(f"Processing policy: {policy_name} ({policy_arn})")

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
            tags_to_apply = {key: value for key, value in all_role_tags.items() if key not in policy_tags}

            if apply_tags_to_policy(iam, policy_arn, policy_name, tags_to_apply):
                results['policies_tagged'] += 1
        else:
            logger.info(f"No role tags found for any roles attached to policy '{policy_name}'.")

    logger.info(json.dumps(results, indent=2))
    return results
