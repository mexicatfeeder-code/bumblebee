from typing import Literal, Optional
from pydantic import BaseModel, Field

SessionType = Literal['focus', 'short_break', 'long_break']
ChatRole = Literal['user', 'assistant', 'system']

class Task(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    estimated_pomodoros: int = Field(default=1, ge=1, le=4)
    completed: bool = False
    sort_order: int = 0
    created_at: str
    category: Optional[str] = None

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    estimated_pomodoros: int = Field(default=1, ge=1, le=4)
    category: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    estimated_pomodoros: Optional[int] = Field(default=None, ge=1, le=4)
    completed: Optional[bool] = None
    sort_order: Optional[int] = None
    category: Optional[str] = None

class TaskOrderItem(BaseModel):
    id: str
    sort_order: int
    estimated_pomodoros: Optional[int] = Field(default=None, ge=1, le=4)

class PomodoroSession(BaseModel):
    id: str
    task_id: Optional[str] = None
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: int
    type: SessionType
    completed: bool

class PomodoroSessionCreate(BaseModel):
    task_id: Optional[str] = None
    duration_seconds: int = Field(ge=1)
    type: SessionType
    completed: bool = False

class PomodoroSessionUpdate(BaseModel):
    ended_at: Optional[str] = None
    completed: Optional[bool] = None

class ChatMessage(BaseModel):
    id: str
    role: ChatRole
    content: str
    timestamp: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    tasks: list[Task]

class PlanItem(BaseModel):
    task_id: str
    sort_order: int
    estimated_pomodoros: int = Field(ge=1, le=4)
