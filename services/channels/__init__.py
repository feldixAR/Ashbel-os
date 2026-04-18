"""Channel services — readiness layer for all outreach channels."""
from .channel_base import ChannelResult, ChannelStatus
from .channel_router import channel_router

__all__ = ["ChannelResult", "ChannelStatus", "channel_router"]
