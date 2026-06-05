import boto3
import logging
from botocore.exceptions import ClientError
import os

logger = logging.getLogger(__name__)

class AtlasDispatcher:
    def __init__(self, region_name: str = 'us-east-1'):
        # Boto3 automatically picks up your AWS credentials from your environment or ~/.aws/credentials
        self.ecs_client = boto3.client('ecs', region_name=region_name)
        self.cluster = os.environ.get('AWS_ECS_CLUSTER', 'atlas-sandbox-cluster')
        self.task_definition = os.environ.get('AWS_ECS_TASK', 'atlas-sandbox-task')
        self.subnet = os.environ.get('AWS_SUBNET_ID', 'subnet-xxxxxxxxx')

    def launch_worker(self, mission_id: str, mission_prompt: str, tailscale_authkey: str, aqueitas_tailscale_ip: str = "100.x.y.z") -> str:
        """
        Commands AWS Fargate to spin up an Atlas node and pass it a specific mission.
        Returns the Task ARN if successful, or raises an Exception.
        """
        logger.info(f"ATLAS COMMAND: Dispatching worker for Mission [{mission_id}]")
        
        try:
            response = self.ecs_client.run_task(
                cluster=self.cluster,
                taskDefinition=self.task_definition,
                launchType='FARGATE',
                networkConfiguration={
                    'awsvpcConfiguration': {
                        'subnets': [self.subnet], 
                        'assignPublicIp': 'ENABLED'
                    }
                },
                overrides={
                    'containerOverrides': [
                        {
                            'name': 'sandbox-worker',
                            'environment': [
                                {'name': 'MISSION_ID', 'value': mission_id},
                                {'name': 'MISSION_PROMPT', 'value': mission_prompt},
                                {'name': 'TAILSCALE_AUTHKEY', 'value': tailscale_authkey},
                                {'name': 'AQUEITAS_TAILSCALE_IP', 'value': aqueitas_tailscale_ip} 
                            ]
                        }
                    ]
                }
            )
            
            if response.get('failures'):
                logger.error(f"FARGATE LAUNCH FAILURE: {response['failures']}")
                raise Exception(f"Failed to launch task: {response['failures']}")
                
            task_arn = response['tasks'][0]['taskArn']
            logger.info(f"ATLAS COMMAND: Worker launched successfully. Task ARN: {task_arn}")
            return task_arn
            
        except ClientError as e:
            logger.error(f"AWS API ERROR: {e}")
            raise
