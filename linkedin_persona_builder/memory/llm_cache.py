import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime
from openai import AsyncOpenAI
from data.redis.redis_utils import redis_manager
from orchestrator.config import settings
import logging

logger = logging.getLogger(__name__)


class LLMCache:
    """
    LLM response caching system for cost optimization and consistency
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    def _generate_cache_key(self, prompt: str, model: str, temperature: float, 
                          operation: str) -> str:
        """Generate cache key from prompt parameters"""
        # Create hash from prompt content and parameters
        content = f"{prompt}:{model}:{temperature}"
        prompt_hash = hashlib.md5(content.encode()).hexdigest()
        return f"{operation}:{prompt_hash}"
    
    async def get_cached_response(self, prompt: str, model: str = None, 
                                temperature: float = None, operation: str = "general") -> Optional[str]:
        """Get cached LLM response if available"""
        try:
            model = model or settings.openai_model
            temperature = temperature or settings.temperature
            
            cache_key = self._generate_cache_key(prompt, model, temperature, operation)
            cached = await redis_manager.get_cached_llm_response(operation, cache_key)
            
            if cached:
                logger.info(f"Cache hit for {operation}", cache_key=cache_key[:16])
                return cached
            
            return None
            
        except Exception as e:
            logger.error(f"Cache retrieval failed: {e}")
            return None
    
    async def cache_response(self, prompt: str, response: str, model: str = None,
                           temperature: float = None, operation: str = "general") -> bool:
        """Cache LLM response"""
        try:
            model = model or settings.openai_model
            temperature = temperature or settings.temperature
            
            cache_key = self._generate_cache_key(prompt, model, temperature, operation)
            success = await redis_manager.cache_llm_response(operation, cache_key, response, model)
            
            if success:
                logger.info(f"Response cached for {operation}", cache_key=cache_key[:16])
            
            return success
            
        except Exception as e:
            logger.error(f"Cache storage failed: {e}")
            return False
    
    async def call_llm_with_cache(self, prompt: str, model: str = None,
                                temperature: float = None, operation: str = "general",
                                max_tokens: int = 1000) -> Optional[str]:
        """Call LLM with caching - main method for LLM interactions"""
        try:
            # Try cache first
            cached_response = await self.get_cached_response(prompt, model, temperature, operation)
            if cached_response:
                return cached_response
            
            # Make LLM call
            model = model or settings.openai_model
            temperature = temperature or settings.temperature
            
            logger.info(f"Making LLM call for {operation}", model=model)
            start_time = datetime.now()
            
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful business strategist named Paul."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"LLM response received", response_time_ms=response_time, operation=operation)
            
            if response.choices and response.choices[0].message:
                result = response.choices[0].message.content
                
                # Cache the response
                await self.cache_response(prompt, result, model, temperature, operation)
                
                return result
            
            return None
            
        except Exception as e:
            logger.error(f"LLM call failed for {operation}: {e}")
            return None
    
    async def parse_json_response(self, prompt: str, operation: str = "json_parse",
                                max_retries: int = 2) -> Optional[Dict[str, Any]]:
        """Call LLM expecting JSON response with retry logic"""
        for attempt in range(max_retries + 1):
            try:
                response = await self.call_llm_with_cache(
                    prompt=prompt,
                    operation=operation,
                    temperature=0.1,  # Lower temperature for JSON consistency
                    max_tokens=1000
                )
                
                if not response:
                    continue
                
                # Try to parse as JSON
                try:
                    return json.loads(response)
                except json.JSONDecodeError as json_error:
                    logger.warning(f"JSON parse failed (attempt {attempt + 1}): {json_error}")
                    
                    if attempt < max_retries:
                        # Add explicit JSON instruction for retry
                        prompt += "\n\nIMPORTANT: Respond with ONLY valid JSON, no additional text."
                        continue
                    else:
                        # Try to extract JSON from response
                        return self._extract_json_from_text(response)
                
            except Exception as e:
                logger.error(f"JSON response attempt {attempt + 1} failed: {e}")
                if attempt == max_retries:
                    return None
        
        return None
    
    def _extract_json_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract JSON from text that might have extra content"""
        try:
            # Look for JSON-like content between braces
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        return None
    
    async def get_embedding(self, text: str) -> Optional[list]:
        """Get text embedding for semantic similarity"""
        try:
            response = await self.client.embeddings.create(
                model=settings.openai_embedding_model,
                input=text
            )
            
            if response.data and response.data[0].embedding:
                return response.data[0].embedding
            
            return None
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None
    
    async def calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts"""
        try:
            embedding1 = await self.get_embedding(text1)
            embedding2 = await self.get_embedding(text2)
            
            if not embedding1 or not embedding2:
                return 0.0
            
            # Calculate cosine similarity
            import numpy as np
            
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Cosine similarity formula
            dot_product = np.dot(vec1, vec2)
            magnitude1 = np.linalg.norm(vec1)
            magnitude2 = np.linalg.norm(vec2)
            
            if magnitude1 == 0 or magnitude2 == 0:
                return 0.0
            
            similarity = dot_product / (magnitude1 * magnitude2)
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Similarity calculation failed: {e}")
            return 0.0
    
    async def clear_cache(self, operation: str = None) -> bool:
        """Clear cached responses (for testing or reset)"""
        try:
            # This would require additional Redis operations
            # For now, just log the request
            logger.info(f"Cache clear requested for operation: {operation or 'all'}")
            return True
        except Exception as e:
            logger.error(f"Cache clear failed: {e}")
            return False


# Global LLM cache instance
llm_cache = LLMCache()
