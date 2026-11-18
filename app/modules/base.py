"""Base module interface for PS5 Management Server."""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class ModuleStatus(str, Enum):
    """Module status."""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class ModuleInfo:
    """Module information."""
    name: str
    version: str
    description: str
    dependencies: List[str]
    status: ModuleStatus = ModuleStatus.UNINITIALIZED
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}


class BaseModule(ABC):
    """Base class for all modules."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.status = ModuleStatus.UNINITIALIZED
        self._info = None
    
    @property
    @abstractmethod
    def info(self) -> ModuleInfo:
        """Return module information."""
        pass
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the module."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """Shutdown the module."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Health check for the module."""
        pass
    
    def get_status(self) -> ModuleStatus:
        """Get current module status."""
        return self.status
    
    def set_status(self, status: ModuleStatus):
        """Set module status."""
        self.status = status