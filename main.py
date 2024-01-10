"""Google Cloue Run function that receives a Slack webhook POST."""

import logging
import os

import requests
from openai import OpenAI
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "trumpbot-1470174245960")
GPT_MODEL_ID = "ft:gpt-3.5-turbo-0613:replica::8fBMHKDg"
SYSTEM_PROMPT = """You are John Flinchbaugh talking to his friends on Slack.

You are a Dallas Mavericks and Texas Rangers fan, you like music and have a very silly non-sensical Slack persona.

Whenever you are asked a question, you always answer with confidence, and never say "I dunno" or "Haha".
"""

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
    logging.error(f"{request}: {exc_str}")
    content = {'status_code': 10422, 'message': exc_str, 'data': None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


class SlackChallenge(BaseModel):
    challenge: str


class SlackEvent(BaseModel):
    """A Slack event.

    Example:
        {
          "token": "zBgqfYxzWd1a9Hdsf5O1w6NN",
          "team_id": "T0NSVARPH",
          "api_app_id": "A06D6D4KNJW",
          "event": {
            "client_msg_id": "c2d0bcf0-49f6-4766-8dc3-86634d5fd569",
            "type": "app_mention",
            "text": "<@U06D8SU3UKE> speak!",
            "user": "U0NTAV5S9",
            "ts": "1704903988.355699",
            "blocks": [
              {
                "type": "rich_text",
                "block_id": "d8MID",
                "elements": [
                  {
                    "type": "rich_text_section",
                    "elements": [
                      {
                        "type": "user",
                        "user_id": "U06D8SU3UKE"
                      },
                      {
                        "type": "text",
                        "text": " speak!"
                      }
                    ]
                  }
                ]
              }
            ],
            "team": "T0NSVARPH",
            "channel": "C05FX3D6B3M",
            "event_ts": "1704903988.355699"
          },
          "type": "event_callback",
          "event_id": "Ev06DCKYLSBE",
          "event_time": 1704903988,
          "authorizations": [
            {
              "enterprise_id": null,
              "team_id": "T0NSVARPH",
              "user_id": "U06D8SU3UKE",
              "is_bot": true,
              "is_enterprise_install": false
            }
          ]
        }
    """
    token: str
    team_id: str
    api_app_id: str
    event: dict
    type: str
    event_id: str
    event_time: int
    authorizations: list


def query_gpt_model(prompt, max_tokens=256, temperature=0.6):
    """Sends a prompt to the GPT model and returns its response."""
    client = OpenAI()

    completion = client.chat.completions.create(
        model=GPT_MODEL_ID,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return completion.choices[0].message.content

@app.post("/slack/event")
def respond_to_event(event: SlackEvent | SlackChallenge):
    """Respond to a Slack Events API webhook."""
    if getattr(event, "challenge", None) is not None:
        return event.challenge
    print(event.dict())
    gpt_response = query_gpt_model(event.event.get("text", "Hi Baba").removeprefix("<@U06D8SU3UKE> "))
    user = event.event.get("user")
    response = f"<@{user}> {gpt_response}"
    requests.post(
        "https://hooks.slack.com/services/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",
        json={"text": response},
    )
    return response
