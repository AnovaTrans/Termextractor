"""
Configuration manager for TermExtractor-Pro
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import os


class ConfigManager:
    """Manages application configuration"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        """Singleton pattern"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        config_path = Path(__file__).parent / "config.yaml"
        
        if not config_path.exists():
            print(f"⚠️  Config file not found at {config_path}")
            self._config = self._get_defaults()
            return
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            self._config = self._get_defaults()
    
    @staticmethod
    def _get_defaults() -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'app': {
                'name': 'TermExtractor-Pro',
                'version': '1.0.0',
            },
            'extraction': {
                'default_relevance_threshold': 70.0,
                'chunk_size': 12000,
            },
            'api': {
                'timeout_seconds': 60,
                'rate_limit_per_minute': 50,
            },
            'ui': {
                'theme': 'light',
            },
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Example: config.get('extraction.default_relevance_threshold')
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            
            if value is None:
                return default
        
        return value if value is not None else default
    
    def get_app_config(self) -> Dict[str, Any]:
        """Get app configuration"""
        return self._config.get('app', {})
    
    def get_extraction_config(self) -> Dict[str, Any]:
        """Get extraction configuration"""
        return self._config.get('extraction', {})
    
    def get_api_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return self._config.get('api', {})
    
    def get_model_config(self) -> Dict[str, Any]:
        """Get model selection configuration"""
        return self._config.get('model_selection', {})
    
    def get_translation_lookup_config(self) -> Dict[str, Any]:
        """Get translation lookup configuration"""
        return self._config.get('translation_lookup', {})
    
    def get_derivative_config(self) -> Dict[str, Any]:
        """Get derivative discovery configuration"""
        return self._config.get('derivative_discovery', {})
    
    def get_export_config(self) -> Dict[str, Any]:
        """Get export configuration"""
        return self._config.get('export', {})
    
    def get_ui_config(self) -> Dict[str, Any]:
        """Get UI configuration"""
        return self._config.get('ui', {})
    
    def get_model(self, purpose: str = 'extraction') -> str:
        """
        Get model name for specific purpose.
        
        Args:
            purpose: One of 'extraction', 'domain_classification', 'fuzzy_refinement'
            
        Returns:
            Model name
        """
        model_config = self.get_model_config()
        
        model_key = f"{purpose}_model"
        # Last-ditch fallback only when config.yaml has no model_selection at all.
        return model_config.get(model_key, model_config.get('default_model', 'claude-haiku-4-5'))
    
    def reload(self) -> None:
        """Reload configuration from file"""
        self._load_config()


# Global config instance
config = ConfigManager()


def get_config() -> ConfigManager:
    """Get global config instance"""
    return config
