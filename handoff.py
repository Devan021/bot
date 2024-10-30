from typing import Optional
from datetime import datetime
import logging
from models import UserStatus, HandoffStatus

logger = logging.getLogger(__name__)

class HandoffHandler:
    def __init__(self, users_collection, handoff_collection, agents_collection):
        self.users = users_collection
        self.handoffs = handoff_collection
        self.agents = agents_collection

    def request_handoff(self, user_id: str) -> bool:
        try:
            # Update user status
            self.users.update_one(
                {'phone_number': user_id},
                {'$set': {'status': UserStatus.PENDING.value}}
            )

            # Create handoff request
            handoff = {
                'user_id': user_id,
                'status': HandoffStatus.WAITING.value,
                'created_at': datetime.utcnow(),
                'agent_id': None
            }
            self.handoffs.insert_one(handoff)
            return True
        except Exception as e:
            logger.error(f"Handoff request error: {e}")
            return False

    def get_pending_requests(self):
        try:
            return list(self.handoffs.find({'status': HandoffStatus.WAITING.value}))
        except Exception as e:
            logger.error(f"Get pending requests error: {e}")
            return []

    def assign_agent(self, request_id: str, agent_id: str) -> bool:
        try:
            result = self.handoffs.update_one(
                {'_id': request_id, 'status': HandoffStatus.WAITING.value},
                {
                    '$set': {
                        'status': HandoffStatus.ASSIGNED.value,
                        'agent_id': agent_id,
                        'assigned_at': datetime.utcnow()
                    }
                }
            )
            if result.modified_count > 0:
                self.users.update_one(
                    {'phone_number': request_id},
                    {'$set': {'status': UserStatus.WITH_AGENT.value}}
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Agent assignment error: {e}")
            return False
