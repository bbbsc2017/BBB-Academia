"""Request/response schemas for AI image generation (nano banana)."""


from pydantic import BaseModel


class GenerateImageRequest(BaseModel):
    org_id: int
    prompt: str
    # Ephemeral refine-session id (Redis). Omitted on the first generation; the
    # response returns a session_uuid to pass back on subsequent refine turns.
    session_uuid: str | None = None
    # For iterative refinement / editing: the file_id of a previously-generated
    # AI image in THIS org. The backend reads its bytes straight from storage
    # (no client fetch → no CORS/credentials issues). Preferred over base64.
    source_file_id: str | None = None
    # Fallback: the source image sent back as a base64 data URL (client-held).
    source_image_base64: str | None = None
    # Optional context the image is generated for (recorded in durable history).
    course_id: int | None = None
    activity_id: int | None = None


class GenerateImageResponse(BaseModel):
    ai_generation_uuid: str
    session_uuid: str
    file_id: str
    media_url: str
    prompt: str


class AIImageHistoryItem(BaseModel):
    ai_generation_uuid: str
    session_uuid: str | None = None
    prompt: str
    file_id: str
    media_url: str
    creation_date: str | None = None
