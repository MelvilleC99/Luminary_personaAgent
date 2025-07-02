"""
LLM Tool with multi-provider support for OpenAI, Anthropic, and DeepSeek.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import openai
import anthropic

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from the LLM."""
        pass
    
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate text from a conversation."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation with connection isolation."""
    
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model
        # Don't store client instance - create fresh ones per request
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using OpenAI with fresh client connection."""
        try:
            logger.info(f"🔄 OpenAI request starting...")
            logger.info(f"🔄 Model: {self.model}")
            logger.info(f"🔄 Prompt length: {len(prompt)} chars")
            logger.info(f"🔄 Max tokens: {kwargs.get('max_tokens', 1000)}")
            logger.info(f"🔄 Temperature: {kwargs.get('temperature', 0.7)}")
            logger.info(f"🔄 Timeout: {kwargs.get('timeout', 60.0)}")
            
            # Create fresh client for each request to avoid connection corruption
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", 1000),
                temperature=kwargs.get("temperature", 0.7),
                timeout=kwargs.get("timeout", 60.0)
            )
            
            logger.info(f"✅ OpenAI response received successfully")
            result = response.choices[0].message.content
            logger.info(f"✅ Response content: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ OpenAI generation error: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            raise
        finally:
            # Ensure client is cleaned up
            if 'client' in locals():
                try:
                    await client.close()
                except:
                    pass
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate text from conversation using OpenAI with fresh client."""
        try:
            # Create fresh client for each request
            client = openai.AsyncOpenAI(api_key=self.api_key)
            
            response = await client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 1000),
                temperature=kwargs.get("temperature", 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI chat error: {e}")
            raise
        finally:
            # Ensure client is cleaned up
            if 'client' in locals():
                try:
                    await client.close()
                except:
                    pass


class AnthropicProvider(LLMProvider):
    """Anthropic/Claude provider implementation."""
    
    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Anthropic."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1000),
                messages=[{"role": "user", "content": prompt}],
                temperature=kwargs.get("temperature", 0.7)
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic generation error: {e}")
            raise
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate text from conversation using Anthropic."""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=kwargs.get("max_tokens", 1000),
                messages=messages,
                temperature=kwargs.get("temperature", 0.7)
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic chat error: {e}")
            raise


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider implementation (using OpenAI-compatible API)."""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.model = model
    
    async def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using DeepSeek."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=kwargs.get("max_tokens", 1000),
                temperature=kwargs.get("temperature", 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek generation error: {e}")
            raise
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Generate text from conversation using DeepSeek."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", 1000),
                temperature=kwargs.get("temperature", 0.7)
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek chat error: {e}")
            raise


class LLMTool:
    """Multi-provider LLM tool for the persona agent system."""
    
    def __init__(self, api_keys: Dict[str, str], llm_assignments: Dict[str, str], database=None):
        """
        Initialize the LLM tool with provider assignments.
        
        Args:
            api_keys: Dictionary of provider API keys
            llm_assignments: Dictionary mapping agents to LLM providers
            database: Database client for usage logging
        """
        self.api_keys = api_keys
        self.llm_assignments = llm_assignments
        self.providers = {}
        self.database = database
        
        # Initialize providers
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize LLM providers based on available API keys with isolated connections."""
        if "openai" in self.api_keys and self.api_keys["openai"]:
            self.providers["openai"] = OpenAIProvider(self.api_keys["openai"])
            logger.info("Initialized OpenAI provider with isolated connections")
        
        if "anthropic" in self.api_keys and self.api_keys["anthropic"]:
            self.providers["claude"] = AnthropicProvider(self.api_keys["anthropic"])
            self.providers["anthropic"] = self.providers["claude"]  # Alias
            logger.info("Initialized Anthropic provider")
        
        if "deepseek" in self.api_keys and self.api_keys["deepseek"]:
            self.providers["deepseek"] = DeepSeekProvider(self.api_keys["deepseek"])
            logger.info("Initialized DeepSeek provider")
    
    async def generate_for_agent(self, agent_name: str, prompt: str, session_id: str = None, **kwargs) -> str:
        """
        Generate text for a specific agent using its assigned LLM.
        
        Args:
            agent_name: Name of the agent requesting generation
            prompt: The prompt to process
            session_id: Optional session ID for usage logging
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text
        """
        import time
        start_time = time.time()
        
        provider_name = self.llm_assignments.get(agent_name, "openai")
        provider = self.providers.get(provider_name)
        
        if not provider:
            raise ValueError(f"No provider available for {provider_name}")
        
        logger.info(f"Generating for {agent_name} using {provider_name}")
        
        try:
            result = await provider.generate(prompt, **kwargs)
            processing_time = int((time.time() - start_time) * 1000)  # Convert to milliseconds
            
            # Log usage if database available - Non-blocking
            if self.database:
                # Fire-and-forget database logging to prevent blocking
                asyncio.create_task(self._log_usage(
                    session_id=session_id,
                    agent_type=agent_name,
                    action="generate",
                    provider=provider_name,
                    model=getattr(provider, 'model', 'unknown'),
                    input_tokens=self._estimate_tokens(prompt),
                    output_tokens=self._estimate_tokens(result),
                    processing_time_ms=processing_time,
                    success=True
                ))
            
            return result
            
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            
            # Log error if database available - Non-blocking
            if self.database:
                # Fire-and-forget error logging to prevent blocking
                asyncio.create_task(self._log_usage(
                    session_id=session_id,
                    agent_type=agent_name,
                    action="generate",
                    provider=provider_name,
                    model=getattr(provider, 'model', 'unknown'),
                    processing_time_ms=processing_time,
                    success=False,
                    error_message=str(e)
                ))
            
            raise
    
    async def chat_for_agent(self, agent_name: str, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        Generate chat response for a specific agent using its assigned LLM.
        
        Args:
            agent_name: Name of the agent requesting generation
            messages: Conversation messages
            **kwargs: Additional generation parameters
            
        Returns:
            Generated response
        """
        provider_name = self.llm_assignments.get(agent_name, "openai")
        provider = self.providers.get(provider_name)
        
        if not provider:
            raise ValueError(f"No provider available for {provider_name}")
        
        logger.info(f"Chat generation for {agent_name} using {provider_name}")
        return await provider.chat(messages, **kwargs)
    
    def get_available_providers(self) -> List[str]:
        """Return list of available providers."""
        return list(self.providers.keys())
    
    def get_agent_assignment(self, agent_name: str) -> str:
        """Get the LLM provider assigned to an agent."""
        return self.llm_assignments.get(agent_name, "openai")
    
    async def _log_usage(self, session_id: str, agent_type: str, action: str, 
                        provider: str, model: str, input_tokens: int = 0, 
                        output_tokens: int = 0, processing_time_ms: int = 0,
                        success: bool = True, error_message: str = None):
        """Log usage to database."""
        if not self.database:
            return
            
        try:
            usage_log = {
                'session_id': session_id,
                'agent_type': agent_type,
                'action': action,
                'provider': provider,
                'model': model,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
                'cost_usd': self._calculate_cost(provider, model, input_tokens, output_tokens),
                'processing_time_ms': processing_time_ms,
                'success': success,
                'error_message': error_message
            }
            
            await self.database.log_agent_interaction(usage_log)
            logger.debug(f"📊 Usage logged: {provider} - {input_tokens + output_tokens} tokens")
            
        except Exception as e:
            logger.error(f"Failed to log usage: {e}")
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters)."""
        if not text:
            return 0
        return max(1, len(text) // 4)
    
    def _calculate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate approximate cost in USD."""
        # Rough cost estimates (per 1K tokens)
        cost_map = {
            'openai': {
                'gpt-4': {'input': 0.03, 'output': 0.06},
                'gpt-3.5-turbo': {'input': 0.0015, 'output': 0.002},
            },
            'anthropic': {
                'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
                'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
            },
            'deepseek': {
                'deepseek-chat': {'input': 0.0003, 'output': 0.0006},
            }
        }
        
        provider_costs = cost_map.get(provider, {})
        model_costs = provider_costs.get(model, {'input': 0.001, 'output': 0.002})  # Default
        
        input_cost = (input_tokens / 1000) * model_costs.get('input', 0.001)
        output_cost = (output_tokens / 1000) * model_costs.get('output', 0.002)
        
        return round(input_cost + output_cost, 6)
