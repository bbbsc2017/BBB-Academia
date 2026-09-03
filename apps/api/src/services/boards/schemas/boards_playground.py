
from pydantic import BaseModel


class BoardsPlaygroundContext(BaseModel):
    board_name: str
    board_description: str


class StartBoardsPlaygroundSession(BaseModel):
    board_uuid: str
    block_uuid: str
    prompt: str
    context: BoardsPlaygroundContext


class SendBoardsPlaygroundMessage(BaseModel):
    session_uuid: str
    board_uuid: str
    block_uuid: str
    message: str
    current_html: str | None = None


class BoardsPlaygroundMessage(BaseModel):
    role: str  # "user" or "model"
    content: str


class BoardsPlaygroundSessionResponse(BaseModel):
    session_uuid: str
    iteration_count: int
    max_iterations: int
    html_content: str | None
    message_history: list[BoardsPlaygroundMessage]


class BoardsPlaygroundSessionData(BaseModel):
    session_uuid: str
    block_uuid: str
    board_uuid: str
    iteration_count: int
    max_iterations: int
    message_history: list[BoardsPlaygroundMessage]
    current_html: str | None
    context: BoardsPlaygroundContext
