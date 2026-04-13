"""
Utilitário para monitorar e logar queries lentas do SQLAlchemy
"""
import time
import logging
from functools import wraps
from sqlalchemy import event
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Threshold em segundos para considerar query lenta
SLOW_QUERY_THRESHOLD = 0.5

class QueryMonitor:
    """Monitor de performance de queries"""
    
    def __init__(self, threshold=SLOW_QUERY_THRESHOLD):
        self.threshold = threshold
        self.slow_queries = []
        self.query_count = 0
        self.total_time = 0
    
    def setup_monitoring(self, engine):
        """Configura monitoramento de queries no engine SQLAlchemy"""
        
        @event.listens_for(engine, "before_cursor_execute")
        def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            conn.info.setdefault('query_start_time', []).append(time.time())
        
        @event.listens_for(engine, "after_cursor_execute")
        def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            total = time.time() - conn.info['query_start_time'].pop(-1)
            self.query_count += 1
            self.total_time += total
            
            if total > self.threshold:
                # Query lenta detectada
                self.slow_queries.append({
                    'duration': total,
                    'statement': statement[:500],  # Limitar tamanho
                    'parameters': str(parameters)[:200] if parameters else None
                })
                
                logger.warning(
                    f"🐌 SLOW QUERY ({total:.3f}s): {statement[:200]}..."
                )
    
    def get_stats(self):
        """Retorna estatísticas de queries"""
        return {
            'total_queries': self.query_count,
            'total_time': round(self.total_time, 3),
            'avg_time': round(self.total_time / self.query_count, 3) if self.query_count > 0 else 0,
            'slow_queries_count': len(self.slow_queries),
            'slow_queries': self.slow_queries[-10:]  # Últimas 10
        }
    
    def reset_stats(self):
        """Reseta estatísticas"""
        self.slow_queries = []
        self.query_count = 0
        self.total_time = 0

# Instância global do monitor
query_monitor = QueryMonitor()

def monitor_route_performance(f):
    """Decorator para monitorar performance de rotas"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        query_monitor.reset_stats()
        
        try:
            result = f(*args, **kwargs)
            duration = time.time() - start_time
            
            stats = query_monitor.get_stats()
            if duration > 1.0 or stats['slow_queries_count'] > 0:
                logger.warning(
                    f"⚠️ Route {f.__name__} took {duration:.3f}s | "
                    f"Queries: {stats['total_queries']} | "
                    f"Slow: {stats['slow_queries_count']}"
                )
            
            return result
        except Exception as e:
            logger.error(f"❌ Error in route {f.__name__}: {e}")
            raise
    
    return decorated_function
