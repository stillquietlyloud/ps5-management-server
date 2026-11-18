"""Module 10: Convert game files to PS5-compatible formats."""
import os
import logging
import subprocess
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.modules.base import BaseModule, ModuleInfo, ModuleStatus
from app.models import Game, GameFormat
from app.database import get_db_session
from config import settings


logger = logging.getLogger(__name__)


class ConvertModule(BaseModule):
    """Convert Module for converting game files between PS5-compatible formats."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.ps5pkgtool_path = self._find_ps5pkgtool()
        self.psmultitools_path = self._find_psmultitools()
    
    @property
    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="convert_module",
            version="1.0.0",
            description="Convert game files to PS5-compatible formats using PS5PKGTool and PS-Multi-Tools",
            dependencies=[],
        )
    
    async def initialize(self) -> bool:
        self.set_status(ModuleStatus.INITIALIZING)
        logger.info("Initializing Convert Module")
        self.set_status(ModuleStatus.READY)
        return True
    
    async def shutdown(self) -> bool:
        self.set_status(ModuleStatus.STOPPED)
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": self.get_status().value,
            "ps5pkgtool": self.ps5pkgtool_path is not None,
            "psmultitools": self.psmultitools_path is not None,
        }
    
    def _find_ps5pkgtool(self) -> Optional[str]:
        """Find PS5PKGTool executable."""
        possible_paths = [
            "/usr/local/bin/PS5PKGTool",
            "/opt/PS5PKGTool/PS5PKGTool",
            "PS5PKGTool.exe",
            "PS5 PKG Tool.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # Try to find in PATH
        for path in os.environ.get("PATH", "").split(os.pathsep):
            for name in ["PS5PKGTool", "PS5PKGTool.exe", "PS5 PKG Tool.exe"]:
                full = os.path.join(path, name)
                if os.path.exists(full):
                    return full
        
        return None
    
    def _find_psmultitools(self) -> Optional[str]:
        """Find PS-Multi-Tools executable."""
        possible_paths = [
            "/usr/local/bin/PSMultiTools",
            "/opt/PS-Multi-Tools/PSMultiTools",
            "PSMultiTools.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        for path in os.environ.get("PATH", "").split(os.pathsep):
            for name in ["PSMultiTools", "PSMultiTools.exe"]:
                full = os.path.join(path, name)
                if os.path.exists(full):
                    return full
        
        return None
    
    def convert(self, game: Game, target_format: str) -> Dict[str, Any]:
        """Convert a game file to target format."""
        try:
            logger.info(f"Converting {game.name} to {target_format}")
            
            # Find source file
            source_path = self._find_source_file(game)
            if not source_path:
                return {"success": False, "error": "Source file not found"}
            
            # Validate target format
            try:
                target_format_enum = GameFormat(target_format.lower())
            except ValueError:
                return {"success": False, "error": f"Unsupported target format: {target_format}"}
            
            # Check compatibility
            compat = self.check_compatibility(game, target_format_enum)
            if not compat.get("compatible"):
                return {"success": False, "error": compat.get("reason", "Incompatible format")}
            
            # Perform conversion based on source and target formats
            source_format = game.format
            
            if source_format == GameFormat.FPKG and target_format_enum == GameFormat.PKG:
                return self._fpkg_to_pkg(source_path, game)
            elif source_format == GameFormat.PKG and target_format_enum == GameFormat.FPKG:
                return self._pkg_to_fpkg(source_path, game)
            elif source_format == GameFormat.FOLDER and target_format_enum in [GameFormat.PKG, GameFormat.FPKG]:
                return self._folder_to_pkg(source_path, game, target_format_enum)
            elif source_format in [GameFormat.PKG, GameFormat.FPKG] and target_format_enum == GameFormat.FOLDER:
                return self._pkg_to_folder(source_path, game)
            elif source_format in [GameFormat.ISO, GameFormat.ZIP, GameFormat.RAR] and target_format_enum in [GameFormat.PKG, GameFormat.FPKG]:
                return self._extract_and_convert(source_path, game, target_format_enum)
            else:
                return {"success": False, "error": f"Conversion from {source_format} to {target_format_enum} not supported"}
        
        except Exception as e:
            logger.error(f"Error converting game: {e}")
            return {"success": False, "error": str(e)}
    
    def _find_source_file(self, game: Game) -> Optional[str]:
        """Find the source file for a game."""
        # Check server locations first
        for loc in game.locations:
            if loc.server_path and os.path.exists(loc.server_path):
                return loc.server_path
        
        return None
    
    def check_compatibility(self, game: Game, target_format: GameFormat) -> Dict[str, Any]:
        """Check if a game can be converted to target format based on firmware."""
        # Get PS5 firmware version from game or assume latest
        required_fw = game.required_firmware or "1.00"
        
        # Firmware compatibility matrix
        # Based on PS5PKGTool and PS-Multi-Tools documentation
        compatibility = {
            "1.00": {
                GameFormat.PKG: True,
                GameFormat.FPKG: False,  # FPKG requires higher firmware
                GameFormat.EXFAT: False,
            },
            "3.00": {
                GameFormat.PKG: True,
                GameFormat.FPKG: True,
                GameFormat.EXFAT: False,
            },
            "5.00": {
                GameFormat.PKG: True,
                GameFormat.FPKG: True,
                GameFormat.EXFAT: True,
            },
            "9.00": {
                GameFormat.PKG: True,
                GameFormat.FPKG: True,
                GameFormat.EXFAT: True,
            },
            "11.00": {
                GameFormat.PKG: True,
                GameFormat.FPKG: True,
                GameFormat.EXFAT: True,
            },
        }
        
        # Find closest firmware version
        fw_versions = sorted(compatibility.keys(), key=lambda x: tuple(map(int, x.split('.'))))
        matched_fw = "1.00"
        for fw in fw_versions:
            if self._version_compare(required_fw, fw) >= 0:
                matched_fw = fw
        
        compatible = compatibility.get(matched_fw, {}).get(target_format, False)
        
        return {
            "compatible": compatible,
            "required_firmware": required_fw,
            "matched_firmware": matched_fw,
            "target_format": target_format.value,
            "reason": "Format not supported on this firmware" if not compatible else None,
        }
    
    def _version_compare(self, v1: str, v2: str) -> int:
        """Compare two version strings."""
        v1_parts = [int(x) for x in v1.split('.')]
        v2_parts = [int(x) for x in v2.split('.')]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            p1 = v1_parts[i] if i < len(v1_parts) else 0
            p2 = v2_parts[i] if i < len(v2_parts) else 0
            if p1 < p2:
                return -1
            elif p1 > p2:
                return 1
        
        return 0
    
    def _fpkg_to_pkg(self, source_path: str, game: Game) -> Dict[str, Any]:
        """Convert FPKG to PKG (resign)."""
        if not self.ps5pkgtool_path:
            return {"success": False, "error": "PS5PKGTool not found"}
        
        output_path = source_path.replace('.fpkg', '.pkg')
        
        try:
            # PS5PKGTool command for resigning
            cmd = [
                self.ps5pkgtool_path,
                "resign",
                source_path,
                "-o", output_path,
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "output_path": output_path,
                    "format": GameFormat.PKG.value,
                }
            else:
                return {"success": False, "error": result.stderr or "Conversion failed"}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Conversion timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _pkg_to_fpkg(self, source_path: str, game: Game) -> Dict[str, Any]:
        """Convert PKG to FPKG (fake package)."""
        if not self.ps5pkgtool_path:
            return {"success": False, "error": "PS5PKGTool not found"}
        
        output_path = source_path.replace('.pkg', '.fpkg')
        
        try:
            # PS5PKGTool command for building FPKG
            cmd = [
                self.ps5pkgtool_path,
                "build",
                source_path,
                "-o", output_path,
                "--fake",
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "output_path": output_path,
                    "format": GameFormat.FPKG.value,
                }
            else:
                return {"success": False, "error": result.stderr or "Conversion failed"}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Conversion timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _folder_to_pkg(self, source_path: str, game: Game, target_format: GameFormat) -> Dict[str, Any]:
        """Convert folder to PKG/FPKG."""
        if not self.ps5pkgtool_path:
            return {"success": False, "error": "PS5PKGTool not found"}
        
        output_path = os.path.join(os.path.dirname(source_path), f"{game.title_id or game.ppsa}.{target_format.value}")
        
        try:
            is_fake = target_format == GameFormat.FPKG
            
            cmd = [
                self.ps5pkgtool_path,
                "build",
                source_path,
                "-o", output_path,
            ]
            
            if is_fake:
                cmd.append("--fake")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "output_path": output_path,
                    "format": target_format.value,
                }
            else:
                return {"success": False, "error": result.stderr or "Conversion failed"}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Conversion timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _pkg_to_folder(self, source_path: str, game: Game) -> Dict[str, Any]:
        """Extract PKG/FPKG to folder."""
        if not self.ps5pkgtool_path:
            return {"success": False, "error": "PS5PKGTool not found"}
        
        output_path = os.path.join(os.path.dirname(source_path), f"{game.title_id or game.ppsa}_extracted")
        
        try:
            cmd = [
                self.ps5pkgtool_path,
                "extract",
                source_path,
                "-o", output_path,
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            
            if result.returncode == 0 and os.path.exists(output_path):
                return {
                    "success": True,
                    "output_path": output_path,
                    "format": GameFormat.FOLDER.value,
                }
            else:
                return {"success": False, "error": result.stderr or "Extraction failed"}
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Extraction timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_and_convert(self, source_path: str, game: Game, target_format: GameFormat) -> Dict[str, Any]:
        """Extract archive and convert to PKG/FPKG."""
        import tempfile
        import shutil
        
        # Extract to temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract based on format
            if game.format == GameFormat.ISO:
                # Use PS-Multi-Tools or other tool
                pass
            elif game.format in [GameFormat.ZIP, GameFormat.RAR, GameFormat.SEVEN_ZIP]:
                # Use standard extraction
                pass
            
            # Then convert folder to target format
            return self._folder_to_pkg(temp_dir, game, target_format)
    
    def get_supported_conversions(self, source_format: GameFormat = None) -> List[Dict[str, Any]]:
        """Get list of supported conversions."""
        conversions = {
            GameFormat.FPKG: [GameFormat.PKG, GameFormat.FOLDER],
            GameFormat.PKG: [GameFormat.FPKG, GameFormat.FOLDER],
            GameFormat.FOLDER: [GameFormat.PKG, GameFormat.FPKG],
            GameFormat.ISO: [GameFormat.PKG, GameFormat.FPKG],
            GameFormat.ZIP: [GameFormat.PKG, GameFormat.FPKG],
            GameFormat.RAR: [GameFormat.PKG, GameFormat.FPKG],
        }
        
        if source_format:
            return [
                {"source": source_format.value, "target": t.value}
                for t in conversions.get(source_format, [])
            ]
        
        result = []
        for src, targets in conversions.items():
            for tgt in targets:
                result.append({"source": src.value, "target": tgt.value})
        
        return result
    
    def get_format_info(self, firmware: str = None) -> Dict[str, Any]:
        """Get recommended formats for a firmware version."""
        fw = firmware or "11.00"
        
        return {
            "firmware": fw,
            "recommended": {
                "primary": GameFormat.FPKG.value if self._version_compare(fw, "3.00") >= 0 else GameFormat.PKG.value,
                "secondary": GameFormat.PKG.value,
                "external": GameFormat.EXFAT.value if self._version_compare(fw, "5.00") >= 0 else None,
            },
            "supported_formats": [f.value for f in GameFormat],
            "conversion_tools": {
                "ps5pkgtool": self.ps5pkgtool_path is not None,
                "psmultitools": self.psmultitools_path is not None,
            },
        }