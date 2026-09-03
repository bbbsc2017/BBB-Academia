"""Schemas for AI assignment generation.

The AI emits a strict ``AIAssignmentPlan`` whose per-task ``contents`` are
keyed by named sub-objects (quiz/form/short_answer/number_answer) rather than a
discriminated union — this is markedly more reliable for LLM structured output.
The service then post-processes each task into the exact ``AssignmentTask``
``contents`` shape the server graders expect (stamping the questionUUID /
optionUUID / blankUUID ids), so what the frontend previews and saves is valid.

Task-type source of truth: ``src/db/courses/assignments.py`` +
``src/services/courses/activities/assignments.py`` (the graders).
"""

from typing import Literal

from pydantic import BaseModel, Field

# The subset of AssignmentTaskTypeEnum the AI can generate. CODE (Judge0 test
# cases) and CUSTOM/OTHER (headless) are intentionally excluded — they need
# human-authored specifics. Teachers add those manually.
AIGeneratableTaskType = Literal[
    "QUIZ", "FORM", "SHORT_ANSWER", "NUMBER_ANSWER", "FILE_SUBMISSION"
]


# --- Per-type AI-facing contents (no ids; stamped server-side) ---

class AIQuizOption(BaseModel):
    text: str
    is_correct: bool


class AIQuizQuestion(BaseModel):
    question_text: str
    options: list[AIQuizOption] = Field(default_factory=list)


class AIQuizContents(BaseModel):
    questions: list[AIQuizQuestion] = Field(default_factory=list)


class AIFormBlank(BaseModel):
    placeholder: str
    correct_answer: str
    hint: str | None = None


class AIFormQuestion(BaseModel):
    question_text: str
    blanks: list[AIFormBlank] = Field(default_factory=list)


class AIFormContents(BaseModel):
    questions: list[AIFormQuestion] = Field(default_factory=list)


class AIShortAnswerContents(BaseModel):
    prompt: str
    correct_answers: list[str] = Field(default_factory=list)
    match_mode: Literal["exact", "case_insensitive", "contains", "regex"] = "case_insensitive"
    explanation: str | None = None


class AINumberAnswerContents(BaseModel):
    prompt: str
    correct_value: float
    tolerance: float = 0
    unit: str | None = None
    explanation: str | None = None


class AITask(BaseModel):
    title: str
    description: str
    hint: str = ""
    assignment_type: AIGeneratableTaskType
    # Exactly one of these should be populated, matching assignment_type. For
    # FILE_SUBMISSION all are null (contents is empty).
    quiz: AIQuizContents | None = None
    form: AIFormContents | None = None
    short_answer: AIShortAnswerContents | None = None
    number_answer: AINumberAnswerContents | None = None


class AIAssignmentPlan(BaseModel):
    title: str
    description: str
    grading_type: Literal[
        "ALPHABET", "NUMERIC", "PERCENTAGE", "PASS_FAIL", "GPA_SCALE"
    ] = "PERCENTAGE"
    tasks: list[AITask] = Field(default_factory=list)


# --- Request / response ---

class GenerateAssignmentRequest(BaseModel):
    org_id: int
    course_uuid: str
    prompt: str
    session_uuid: str | None = None
    num_tasks: int = 3
    allowed_task_types: list[AIGeneratableTaskType] | None = None


class GeneratedTask(BaseModel):
    """A task ready to POST to /assignments/{uuid}/tasks (server assigns ids)."""

    title: str
    description: str
    hint: str = ""
    assignment_type: str
    contents: dict
    max_grade_value: int = 100


class GeneratedAssignmentPlan(BaseModel):
    title: str
    description: str
    grading_type: str
    tasks: list[GeneratedTask] = Field(default_factory=list)


class GenerateAssignmentResponse(BaseModel):
    ai_generation_uuid: str
    session_uuid: str
    plan: GeneratedAssignmentPlan


class AIAssignmentHistoryItem(BaseModel):
    ai_generation_uuid: str
    session_uuid: str | None = None
    prompt: str
    plan: dict
    creation_date: str | None = None
