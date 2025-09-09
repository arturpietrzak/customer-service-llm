import os
import yaml
from typing import Dict, Optional, Any
import logging
from dotenv import load_dotenv

load_dotenv()

from .base import BaseLLMProvider, MockProvider
from .openrouter_provider import OpenRouterProvider
from .replicate_provider import ReplicateProvider

logger = logging.getLogger(__name__)


class ProviderFactory:
    
    PROVIDER_MAP = {
        "openrouter": OpenRouterProvider,
        "replicate": ReplicateProvider,
        "mock": MockProvider,
    }
    
    def __init__(self, config_path: str = "config/models_openrouter.yaml"):
        self.config_path = config_path
        self.models_config = self._load_models_config()
    
    def _load_models_config(self) -> Dict:
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.error(f"Models config file not found: {self.config_path}")
            return {"models": {}, "providers": {}}
        except Exception as e:
            logger.error(f"Error loading models config: {e}")
            return {"models": {}, "providers": {}}
    
    def get_provider(self, model_id: str) -> Optional[BaseLLMProvider]:
        if model_id not in self.models_config.get("models", {}):
            logger.error(f"Model {model_id} not found in configuration")
            return None
        
        model_config = self.models_config["models"][model_id]
        provider_name = model_config.get("provider")
        
        if provider_name not in self.PROVIDER_MAP:
            logger.error(f"Provider {provider_name} not implemented")
            return None
        
        api_key = self._get_api_key(provider_name)
        if not api_key and provider_name != "mock":
            logger.error(f"API key not found for provider {provider_name}")
            return None
        
        base_url = None
        provider_config = self.models_config.get("providers", {}).get(provider_name, {})
        if "base_url" in provider_config:
            base_url = provider_config["base_url"]
        
        provider_class = self.PROVIDER_MAP[provider_name]
        return provider_class(api_key=api_key or "", base_url=base_url)
    
    def _get_api_key(self, provider_name: str) -> Optional[str]:
        key_map = {
            "openrouter": "OPENROUTER_API_KEY",
            "replicate": "REPLICATE_API_TOKEN",
        }
        
        env_var = key_map.get(provider_name)
        if env_var:
            return os.getenv(env_var)
        
        return None
    
    def get_model_config(self, model_id: str) -> Optional[Dict]:
        return self.models_config.get("models", {}).get(model_id)
    
    def list_available_models(self) -> Dict[str, Dict]:
        return self.models_config.get("models", {})
    
    def get_models_by_provider(self, provider_name: str) -> Dict[str, Dict]:
        models = {}
        for model_id, config in self.models_config.get("models", {}).items():
            if config.get("provider") == provider_name:
                models[model_id] = config
        return models
    
    def validate_configuration(self) -> Dict[str, Any]:
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "available_models": 0,
            "available_providers": set()
        }
        
        models = self.models_config.get("models", {})
        validation_result["available_models"] = len(models)
        
        for model_id, config in models.items():
            provider = config.get("provider")
            if not provider:
                validation_result["errors"].append(f"Model {model_id} missing provider")
                validation_result["valid"] = False
                continue
            
            validation_result["available_providers"].add(provider)
            
            if provider not in self.PROVIDER_MAP:
                validation_result["warnings"].append(f"Provider {provider} not implemented")
            
            api_key = self._get_api_key(provider)
            if not api_key and provider != "mock":
                validation_result["warnings"].append(f"API key not found for provider {provider}")
        
        validation_result["available_providers"] = list(validation_result["available_providers"])
        
        return validation_result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate LLM provider configuration")
    parser.add_argument("--config", default="config/models_openrouter.yaml", help="Path to models config file")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    factory = ProviderFactory(args.config)
    result = factory.validate_configuration()
    
    print(f"Configuration validation: {'✅ PASSED' if result['valid'] else '❌ FAILED'}")
    print(f"Available models: {result['available_models']}")
    print(f"Available providers: {', '.join(result['available_providers'])}")
    
    if result['errors']:
        print("\n❌ Errors:")
        for error in result['errors']:
            print(f"  - {error}")
    
    if result['warnings']:
        print("\n⚠️ Warnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
    
    print("\n🧪 Testing provider creation:")
    models = factory.list_available_models()
    for model_id in list(models.keys())[:3]:
        provider = factory.get_provider(model_id)
        status = "✅" if provider else "❌"
        print(f"  {status} {model_id} ({models[model_id].get('provider', 'unknown')})")
    
    return 0 if result['valid'] else 1


if __name__ == "__main__":
    exit(main())