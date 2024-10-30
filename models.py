from enum import Enum
from datetime import datetime

class UserStatus(Enum):
    BOT = "bot"
    PENDING = "pending"
    WITH_AGENT = "with_agent"

class HandoffStatus(Enum):
    WAITING = "waiting"
    ASSIGNED = "assigned"
    COMPLETED = "completed"

class AgentStatus(Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"

class Agent:
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.status = AgentStatus.OFFLINE
        self.active_chats = []
        self.created_at = datetime.utcnow()

class HandoffRequest:
    def __init__(self, user_id, timestamp=None):
        self.user_id = user_id
        self.status = HandoffStatus.WAITING
        self.agent_id = None
        self.timestamp = timestamp or datetime.utcnow()
