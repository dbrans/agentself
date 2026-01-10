"""User communication capability.

Provides the agent with the ability to communicate with the user.
Messages are queued and can be retrieved by the outer runtime.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class PendingQuestion:
    """A question waiting for user response."""
    question: str
    callback: Callable[[str], None] | None = None


from agentself.capabilities.base import Capability


class UserCommunicationCapability(Capability):
    """Communicate with the user (output queue, input queue)."""
    
    name = "user"
    description = "Communicate with the user via messages and questions."
    
    def __init__(self):
        """Initialize with empty message queues."""
        self._output_queue: deque[str] = deque()
        self._pending_questions: deque[PendingQuestion] = deque()
        self._responses: dict[str, str] = {}
    
    def say(self, message: str) -> None:
        """Send a message to the user.
        
        Args:
            message: The message to display to the user.
        """
        self._output_queue.append(message)
    
    def ask(self, question: str) -> str:
        """Ask the user a question and get a response.
        
        Note: In sandbox mode, this will pause execution until
        the outer runtime provides a response.
        
        Args:
            question: The question to ask.
            
        Returns:
            The user's response.
        """
        # Queue the question
        self._pending_questions.append(PendingQuestion(question=question))
        
        # In a real implementation, this would block/await
        # For now, check if we have a pre-loaded response
        if question in self._responses:
            return self._responses[question]
        
        # Return placeholder - outer runtime should handle this
        return f"[Awaiting response to: {question}]"
    
    # Methods for the outer runtime to use
    
    def get_pending_messages(self) -> list[str]:
        """Get and clear all pending output messages.
        
        This is called by the outer runtime to retrieve messages
        the agent wants to send to the user.
        """
        messages = list(self._output_queue)
        self._output_queue.clear()
        return messages
    
    def get_pending_questions(self) -> list[str]:
        """Get all pending questions (without clearing).
        
        This is called by the outer runtime to see what questions
        are waiting for user input.
        """
        return [q.question for q in self._pending_questions]
    
    def provide_response(self, question: str, response: str) -> None:
        """Provide a response to a question.
        
        This is called by the outer runtime when the user responds.
        """
        self._responses[question] = response
        # Remove from pending
        self._pending_questions = deque(
            q for q in self._pending_questions if q.question != question
        )
