"""Evaluator factory for creating different types of evaluators."""

import logging

from ..providers.provider_factory import ProviderFactory
from .models import EvaluationConfig
from .judge import LLMJudge

logger = logging.getLogger(__name__)



class EvaluatorFactory:
    
    @staticmethod
    def create_evaluator(
        evaluator_type: str, 
        config: EvaluationConfig, 
        provider_factory: ProviderFactory
    ):
        if evaluator_type == "llm-judge":
            return LLMJudge(config, provider_factory)
        else:
            raise ValueError(f"Unknown evaluator type: {evaluator_type}. Valid types: llm-judge")