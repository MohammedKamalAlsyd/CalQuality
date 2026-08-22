import os
import logging
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

bedrock = None
logger = logging.getLogger(__name__)

# ==========================================
# AWS BEDROCK CLIENT
# ==========================================
def get_bedrock_client():
    """Handles automatic (AWS CLI) and manual AWS login."""
    if bedrock: return bedrock
    session_params = {}
    if os.getenv("AWS_ACCESS_KEY_ID"):
        session_params["aws_access_key_id"] = os.getenv("AWS_ACCESS_KEY_ID")
        session_params["aws_secret_access_key"] = os.getenv("AWS_SECRET_ACCESS_KEY")
        session_params["region_name"] = os.getenv("AWS_REGION", "us-east-1")

    try:
        session = boto3.Session(**session_params)
        client = session.client("bedrock-runtime")
        return client
    except (NoCredentialsError, PartialCredentialsError):
        print("\n❌ AWS Credentials not found! Run 'aws configure'.")
        return None
    
bedrock = get_bedrock_client()
# ==========================================
# Robust response text extraction
# ==========================================
def extract_response_text(response: dict) -> str:
    """
    Safely extract the assistant's text from the Bedrock Converse response.

    Handles variations where content blocks might be structured differently
    across models or API updates.

    Args:
        response: The full response dictionary from bedrock.converse().

    Returns:
        The concatenated text from all text content blocks, or an empty string
        if extraction fails.
    """
    try:
        # Navigate the standard Converse response structure
        message = response.get("output", {}).get("message", {})
        content = message.get("content")

        # If content is missing completely
        if content is None:
            logger.warning("Bedrock response missing 'output.message.content'")
            return ""

        # If content is already a plain string (some models might do this)
        if isinstance(content, str):
            return content

        # Content is a list of blocks – gather text blocks
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    # Prefer the "text" key
                    if "text" in block:
                        parts.append(block["text"])
                    else:
                        # Fallback: use the string representation of the block
                        parts.append(str(block))
                else:
                    parts.append(str(block))
            return "".join(parts)

        # Last resort: convert whatever is there to a string
        return str(content)

    except Exception as e:
        logger.error("Error extracting response text: %s", e)
        return ""
    
# ==========================================
# Converse API wrapper
# ==========================================
def call_bedrock_converse(
    prompt:str,
    model_id: str,
    temperature: float = 0.0,
    max_tokens: int = 1000
) -> str:
    """
    Send a prompt to a Bedrock model and return the generated text.
    Returns an empty string if the client is not available or an error occurs.
    """
    if bedrock is None:
        print("Bedrock client not initialised. Skipping request.")
        return ""
    # Build inference config
    inference_config = {
        "maxTokens": max_tokens,
        "temperature": temperature,
    }
    try:
        response = bedrock.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig=inference_config,
        )
        return extract_response_text(response)
    except Exception as e:
        print(f"Bedrock API Error: {e}")
        return ""