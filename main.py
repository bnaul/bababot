"""Google Cloud Run function that receives a Slack webhook POST."""

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class SlackChallenge(BaseModel):
    challenge: str


class SlackEvent(BaseModel):
    """A Slack event.

    Example:
        {
        "token": "ZZZZZZWSxiZZZ2yIvs3peJ",
        "team_id": "T123ABC456",
        "api_app_id": "A123ABC456",
        "event": {
            "type": "app_mention",
            "user": "U123ABC456",
            "text": "What is the hour of the pearl, <@U0LAN0Z89>?",
            "ts": "1515449522.000016",
            "channel": "C123ABC456",
            "event_ts": "1515449522000016"
        },
        "type": "event_callback",
        "event_id": "Ev123ABC456",
        "event_time": 1515449522000016,
        "authed_users": [
            "U0LAN0Z89"
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
    authed_users: list[str]


@app.post("/slack/event")
def respond_to_event(event: SlackEvent | SlackChallenge):
    """Respond to a Slack Events API webhook."""
    if getattr(event, "challenge", None) is not None:
        return event.challenge
    print(event.dict())
