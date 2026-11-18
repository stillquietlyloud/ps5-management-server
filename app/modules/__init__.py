"""Module registry for managing all modules."""
from typing import Dict, Type, Any
from app.modules.base import BaseModule

# Import all modules
from app.modules.ftp_module import FTPModule
from app.modules.push_module import PushModule
from app.modules.pull_module import PullModule
from app.modules.save_backup_module import SaveBackupModule
from app.modules.save_restore_module import SaveRestoreModule
from app.modules.ppsa_module import PPSAModule
from app.modules.artwork_module import ArtworkModule
from app.modules.store_db_module import StoreDBModule
from app.modules.download_module import DownloadModule
from app.modules.convert_module import ConvertModule
from app.modules.info_module import InfoModule
from app.modules.exploit_module import ExploitModule


MODULE_REGISTRY: Dict[str, Type[BaseModule]] = {
    "ftp": FTPModule,
    "push": PushModule,
    "pull": PullModule,
    "save_backup": SaveBackupModule,
    "save_restore": SaveRestoreModule,
    "ppsa": PPSAModule,
    "artwork": ArtworkModule,
    "store_db": StoreDBModule,
    "download": DownloadModule,
    "convert": ConvertModule,
    "info": InfoModule,
    "exploit": ExploitModule,
}


MODULE_DEPENDENCIES = {
    "ftp": [],
    "push": ["ftp"],
    "pull": ["ftp"],
    "save_backup": ["ftp"],
    "save_restore": ["ftp"],
    "ppsa": ["ftp"],
    "artwork": [],
    "store_db": [],
    "download": ["store_db"],
    "convert": [],
    "info": [],
    "exploit": [],
}


def get_module_order() -> list:
    """Get modules in dependency order."""
    # Simple topological sort
    visited = set()
    order = []
    
    def visit(module_name: str):
        if module_name in visited:
            return
        visited.add(module_name)
        
        for dep in MODULE_DEPENDENCIES.get(module_name, []):
            visit(dep)
        
        order.append(module_name)
    
    for module_name in MODULE_REGISTRY:
        visit(module_name)
    
    return order


async def initialize_all_modules(config: Dict[str, Any] = None) -> Dict[str, BaseModule]:
    """Initialize all modules in dependency order."""
    modules = {}
    order = get_module_order()
    
    for name in order:
        module_class = MODULE_REGISTRY[name]
        module_config = config.get(name, {}) if config else {}
        module = module_class(module_config)
        await module.initialize()
        modules[name] = module
    
    return modules


async def shutdown_all_modules(modules: Dict[str, BaseModule]) -> None:
    """Shutdown all modules in reverse dependency order."""
    order = list(reversed(get_module_order()))
    
    for name in order:
        if name in modules:
            await modules[name].shutdown()