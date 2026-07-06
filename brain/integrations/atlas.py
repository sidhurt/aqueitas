"""Atlas: optional remote-worker integration (AWS Fargate + Tailscale + Telegram).

Disabled by default. Enable by setting ATLAS_ENABLED=true and providing:
  AQUEITAS_TAILSCALE_IP, TAILSCALE_AUTHKEY,
  AWS_ECS_CLUSTER, AWS_ECS_TASK, AWS_SUBNET_ID (+ standard AWS credentials),
  and optionally TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID for notifications.

Everything Atlas needs — routes, models, dispatcher, and its own schema —
lives in this module so the core vault never depends on it.
"""
import json
import logging
import os
import uuid
from enum import Enum
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, Field

from database import db
from services.embedding import generate_embedding
from services.retrieval import search_vault
from utils.prompt_forge import forge_contextual_prompt

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Models ---

class MobileDispatchRequest(BaseModel):
    mission_prompt: str = Field(..., description="The complex task or prompt from the mobile client.")
    priority_level: Optional[str] = Field(None, description="Optional priority level for the mission.")

class MobileDispatchResponse(BaseModel):
    status: str = Field(..., description="Status of the dispatch request.")
    mission_id: str = Field(..., description="The generated UUID for tracking this specific mission.")

class AtlasCallbackStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class AtlasCallbackRequest(BaseModel):
    mission_id: str = Field(..., description="The string tracking ID of the completed mission.")
    status: AtlasCallbackStatus = Field(..., description="Outcome of the external computation.")
    result_payload: Dict[str, Any] = Field(..., description="The JSON results or error details from the Atlas node.")


# --- Schema (feature-owned; only created when Atlas is enabled) ---

async def ensure_atlas_schema(pool):
    async with pool.acquire() as connection:
        await connection.execute("""
            CREATE TABLE IF NOT EXISTS atlas_missions (
                mission_id VARCHAR PRIMARY KEY,
                payload TEXT,
                status VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


# --- Dispatcher ---

class AtlasDispatcher:
    def __init__(self, region_name: str = None):
        import boto3  # local import: boto3 is only required when Atlas is enabled
        region = region_name or os.environ.get('AWS_REGION', 'us-east-1')
        self.ecs_client = boto3.client('ecs', region_name=region)
        self.cluster = os.environ.get('AWS_ECS_CLUSTER', 'atlas-sandbox-cluster')
        self.task_definition = os.environ.get('AWS_ECS_TASK', 'atlas-sandbox-task')
        self.subnet = os.environ.get('AWS_SUBNET_ID')

    def launch_worker(self, mission_id: str, mission_prompt: str, tailscale_authkey: str, aqueitas_tailscale_ip: str) -> str:
        """Commands AWS Fargate to spin up an Atlas node for a specific mission.
        Returns the Task ARN if successful, or raises an Exception."""
        from botocore.exceptions import ClientError

        if not self.subnet:
            raise ValueError("AWS_SUBNET_ID is not configured.")

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


def trigger_atlas_worker(mission_id: str, mission_prompt: str):
    """Background task wrapper to handle the synchronous boto3 call."""
    my_tailscale_ip = os.environ.get("AQUEITAS_TAILSCALE_IP")
    auth_key = os.environ.get("TAILSCALE_AUTHKEY")

    if not auth_key or not my_tailscale_ip:
        logger.error("Atlas dispatch aborted: TAILSCALE_AUTHKEY and AQUEITAS_TAILSCALE_IP must both be set.")
        return

    dispatcher = AtlasDispatcher()
    try:
        task_arn = dispatcher.launch_worker(
            mission_id=mission_id,
            mission_prompt=mission_prompt,
            tailscale_authkey=auth_key,
            aqueitas_tailscale_ip=my_tailscale_ip
        )
        logger.info(f"Atlas task launched in background: {task_arn}")
    except Exception as e:
        logger.error(f"Failed to launch Atlas worker in background: {e}")


# --- Endpoints ---

@router.post("/api/mobile/dispatch", response_model=MobileDispatchResponse, status_code=status.HTTP_202_ACCEPTED)
async def mobile_dispatch(request: MobileDispatchRequest, background_tasks: BackgroundTasks):
    """The Mobile Dispatch Contract.
    Intercepts the prompt, retrieves sovereign context, forges an augmented payload, and dispatches Atlas."""
    raw_prompt = request.mission_prompt.strip()
    logger.info(f"AQUEITAS: Mobile dispatch received. Priority: {request.priority_level}")

    if not db.pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized.")

    mission_id = f"msn-{uuid.uuid4().hex[:8]}"
    logger.info(f"ATLAS SYSTEM: Dispatch initiated. Mission ID: {mission_id}")

    try:
        query_vector = await generate_embedding(raw_prompt)

        async with db.pool.acquire() as connection:
            retrieved_context = await search_vault(query_vector, 5, connection)

        if retrieved_context:
            logger.info("ATLAS SYSTEM: Context acquired. Augmenting payload.")
            final_mission_prompt = forge_contextual_prompt(raw_prompt, retrieved_context)
        else:
            logger.warning("ATLAS SYSTEM: No relevant context found. Firing raw payload.")
            final_mission_prompt = raw_prompt

        async with db.pool.acquire() as connection:
            await connection.execute("""
                INSERT INTO atlas_missions (mission_id, payload, status)
                VALUES ($1, $2, 'PENDING')
            """, mission_id, final_mission_prompt)

        background_tasks.add_task(trigger_atlas_worker, mission_id, "FETCH_PAYLOAD_VIA_TAILSCALE")

        return MobileDispatchResponse(status="dispatched", mission_id=mission_id)

    except Exception as e:
        logger.error(f"FATAL: Dispatch pipeline collapsed: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal orchestration failure.")


@router.get("/api/internal/mission/{mission_id}")
async def fetch_mission_payload(mission_id: str):
    """Sovereign Fetch Endpoint. Atlas pulls the full prompt over Tailscale before execution."""
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database pool not initialized.")

    async with db.pool.acquire() as connection:
        row = await connection.fetchrow("""
            UPDATE atlas_missions
            SET status = 'FETCHED'
            WHERE mission_id = $1
            RETURNING payload
        """, mission_id)

    if not row:
        raise HTTPException(status_code=404, detail="Mission payload not found.")

    return {"mission_id": mission_id, "payload": row["payload"]}


async def send_telegram_notification(mission_id: str, mission_status: str, result_payload: dict):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.warning("Telegram credentials not found in environment.")
        return

    emoji = "🟢" if mission_status == "SUCCESS" else "🚨"

    text = (
        f"{emoji} **Atlas Mission {mission_status}**\n\n"
        f"**ID:** `{mission_id}`\n\n"
        f"**Payload:**\n```json\n{json.dumps(result_payload, indent=2)}\n```"
    )

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Telegram notification sent for mission {mission_id}")
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")


@router.post("/api/internal/atlas-callback")
async def atlas_callback(request: AtlasCallbackRequest):
    """The Atlas Callback Contract.
    Receives the final result payload from the ephemeral Fargate node via Tailscale."""
    logger.info(f"⚡ [ATLAS CALLBACK] Mission: {request.mission_id} | Status: {request.status.value}")

    await send_telegram_notification(
        str(request.mission_id),
        request.status.value,
        request.result_payload
    )

    return {"status": "acknowledged", "recorded_state": request.status.value}
