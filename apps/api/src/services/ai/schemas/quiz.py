"""Schemas for AI quiz generation (in-editor `blockQuiz`).

The AI emits a strict, schema-validated ``GeneratedQuiz``; the service then
stamps the ids the editor's ``blockQuiz`` node expects (quizId / question_id /
answer_id) so the frontend can insert it verbatim. This targets the *editor*
quiz block — NOT the graded assignment QUIZ task, which has a different shape.
"""

from typing import Literal

from pydantic import BaseModel, Field

# --- Structured model output (ids assigned server-side afterwards) ---

class GenQuizAnswer(BaseModel):
    answer: str
    correct: bool


class GenQuizQuestion(BaseModel):
    question: str
    # Only `multiple_choice` is generated: QuizBlockComponent renders every
    # question as multiple-choice, so a `custom_answer` would degenerate into a
    # single answer-revealing option.
    type: Literal["multiple_choice"] = "multiple_choice"
    answers: list[GenQuizAnswer] = Field(default_factory=list)


class GeneratedQuiz(BaseModel):
    questions: list[GenQuizQuestion] = Field(default_factory=list)


# --- Request / response ---

class GenerateQuizRequest(BaseModel):
    org_id: int
    prompt: str
    # When set, the quiz is grounded on the activity's existing content.
    activity_uuid: str | None = None
    # Ephemeral refine session (Redis). Omit on first call; pass back to refine.
    session_uuid: str | None = None
    num_questions: int = 5
    difficulty: Literal["easy", "medium", "hard"] | None = None


class GenerateQuizResponse(BaseModel):
    ai_generation_uuid: str
    session_uuid: str
    # Ready-to-insert `blockQuiz` attrs: {"quizId", "questions": [...]}.
    quiz: dict


class AIQuizHistoryItem(BaseModel):
    ai_generation_uuid: str
    session_uuid: str | None = None
    prompt: str
    quiz: dict
    creation_date: str | None = None
