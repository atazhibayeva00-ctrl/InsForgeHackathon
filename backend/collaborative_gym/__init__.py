"""A minimal, faithful vendoring of the Collaborative Gym (Co-Gym) core API.

This package mirrors the structure of SALT-NLP/collaborative-gym so the
Collaborative Investment Copilot can be modeled as a real ``CoEnv`` task
environment. Only the pieces needed to define and run an environment locally
are included (no Redis nodes / Runner); the FastAPI server drives the
environment directly via ``env.step(role, action)``.

Reference: https://github.com/SALT-NLP/collaborative-gym (MIT License).
"""

from collaborative_gym.core import CoEnv, ObservationTypes, TeamMemberConfig

__all__ = ["CoEnv", "ObservationTypes", "TeamMemberConfig"]
