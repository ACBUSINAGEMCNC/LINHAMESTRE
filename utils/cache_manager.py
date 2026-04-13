"""
Sistema de cache para métricas e dados calculados
Suporta Redis (produção) e fallback para cache em memória (desenvolvimento)
"""
import json
import time
import logging
from functools import wraps
from typing import Any, Optional, Callable
import os

logger = logging.getLogger(__name__)

# Tentar importar Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis não disponível. Usando cache em memória.")

class CacheManager:
    """Gerenciador de cache com suporte a Redis e fallback para memória"""
    
    def __init__(self):
        self.redis_client = None
        self.memory_cache = {}
        self.cache_stats = {'hits': 0, 'misses': 0, 'sets': 0}
        
        # Tentar conectar ao Redis se disponível
        if REDIS_AVAILABLE:
            redis_url = os.getenv('REDIS_URL') or os.getenv('REDIS_TLS_URL')
            if redis_url:
                try:
                    self.redis_client = redis.from_url(
                        redis_url,
                        decode_responses=True,
                        socket_connect_timeout=2,
                        socket_timeout=2
                    )
                    # Testar conexão
                    self.redis_client.ping()
                    logger.info("✓ Redis conectado com sucesso")
                except Exception as e:
                    logger.warning(f"Falha ao conectar Redis: {e}. Usando cache em memória.")
                    self.redis_client = None
    
    def get(self, key: str) -> Optional[Any]:
        """Busca valor no cache"""
        try:
            if self.redis_client:
                value = self.redis_client.get(key)
                if value:
                    self.cache_stats['hits'] += 1
                    return json.loads(value)
                self.cache_stats['misses'] += 1
                return None
            else:
                # Cache em memória
                if key in self.memory_cache:
                    entry = self.memory_cache[key]
                    if entry['expires_at'] > time.time():
                        self.cache_stats['hits'] += 1
                        return entry['value']
                    else:
                        del self.memory_cache[key]
                self.cache_stats['misses'] += 1
                return None
        except Exception as e:
            logger.error(f"Erro ao buscar cache {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Define valor no cache com TTL em segundos"""
        try:
            self.cache_stats['sets'] += 1
            if self.redis_client:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
            else:
                # Cache em memória
                self.memory_cache[key] = {
                    'value': value,
                    'expires_at': time.time() + ttl
                }
                # Limpar entradas expiradas (máximo 1000 entradas)
                if len(self.memory_cache) > 1000:
                    self._cleanup_memory_cache()
        except Exception as e:
            logger.error(f"Erro ao definir cache {key}: {e}")
    
    def delete(self, key: str):
        """Remove valor do cache"""
        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self.memory_cache.pop(key, None)
        except Exception as e:
            logger.error(f"Erro ao deletar cache {key}: {e}")
    
    def invalidate_pattern(self, pattern: str):
        """Invalida todas as chaves que correspondem ao padrão"""
        try:
            if self.redis_client:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            else:
                # Cache em memória
                keys_to_delete = [k for k in self.memory_cache.keys() if pattern.replace('*', '') in k]
                for key in keys_to_delete:
                    del self.memory_cache[key]
        except Exception as e:
            logger.error(f"Erro ao invalidar padrão {pattern}: {e}")
    
    def _cleanup_memory_cache(self):
        """Remove entradas expiradas do cache em memória"""
        now = time.time()
        expired_keys = [k for k, v in self.memory_cache.items() if v['expires_at'] <= now]
        for key in expired_keys:
            del self.memory_cache[key]
    
    def get_stats(self):
        """Retorna estatísticas do cache"""
        total = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total * 100) if total > 0 else 0
        return {
            **self.cache_stats,
            'hit_rate': round(hit_rate, 2),
            'backend': 'redis' if self.redis_client else 'memory',
            'memory_entries': len(self.memory_cache) if not self.redis_client else None
        }

# Instância global
cache = CacheManager()

def cached(key_prefix: str, ttl: int = 300):
    """Decorator para cachear resultado de funções"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Gerar chave de cache baseada nos argumentos
            cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
            
            # Tentar buscar do cache
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            # Executar função e cachear resultado
            logger.debug(f"Cache MISS: {cache_key}")
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        
        return wrapper
    return decorator
