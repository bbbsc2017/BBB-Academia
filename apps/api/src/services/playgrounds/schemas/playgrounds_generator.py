
from pydantic import BaseModel


class PlaygroundContext(BaseModel):
    playground_name: str
    playground_description: str
    course_uuid: str | None = None
    course_name: str | None = None


class StartPlaygroundSession(BaseModel):
    playground_uuid: str
    prompt: str
    context: PlaygroundContext


class SendPlaygroundMessage(BaseModel):
    session_uuid: str
    playground_uuid: str
    message: str
    current_html: str | None = None


class PlaygroundMessage(BaseModel):
    role: str  # "user" or "model"
    content: str


class PlaygroundSessionResponse(BaseModel):
    session_uuid: str
    iteration_count: int
    max_iterations: int
    html_content: str | None
    message_history: list[PlaygroundMessage]


class PlaygroundSessionData(BaseModel):
    session_uuid: str
    playground_uuid: str
    iteration_count: int
    max_iterations: int
    message_history: list[PlaygroundMessage]
    current_html: str | None
    context: PlaygroundContext
