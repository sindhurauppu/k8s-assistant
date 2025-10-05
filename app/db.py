import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime
import uuid


class FeedbackDatabase:
    """Handle PostgreSQL database operations for user feedback and conversations"""
    
    def __init__(self):
        """Initialize database connection using environment variables"""
        self.connection_params = {
            'host': os.environ.get('POSTGRES_HOST', 'localhost'),
            'port': os.environ.get('POSTGRES_PORT', '5432'),
            'database': os.environ.get('POSTGRES_DB', 'rag_feedback'),
            'user': os.environ.get('POSTGRES_USER', 'postgres'),
            'password': os.environ.get('POSTGRES_PASSWORD', '')
        }
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.connection_params)
    
    def test_connection(self):
        """Test database connection"""
        try:
            conn = self.get_connection()
            conn.close()
            return True, "Connection successful"
        except Exception as e:
            return False, str(e)
    
    def init_table(self):
        """Create feedback and conversations tables if they don't exist"""
        create_tables_query = """
        CREATE TABLE IF NOT EXISTS feedback (
            id UUID PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            feedback INTEGER NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            session_id TEXT
        );
        
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            relevance TEXT,
            relevance_explanation TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            eval_prompt_tokens INTEGER,
            eval_completion_tokens INTEGER,
            eval_total_tokens INTEGER,
            openai_cost DECIMAL(10, 6),
            response_time DECIMAL(10, 3),
            timestamp TIMESTAMP NOT NULL,
            session_id TEXT
        );
        
        CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp);
        CREATE INDEX IF NOT EXISTS idx_feedback_session ON feedback(session_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
        CREATE INDEX IF NOT EXISTS idx_conversations_relevance ON conversations(relevance);
        CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
        """
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(create_tables_query)
            conn.commit()
            cursor.close()
            conn.close()
            return True, "Database initialized successfully"
        except Exception as e:
            error_msg = f"Error initializing table: {e}"
            print(error_msg)
            return False, error_msg
    
    def save_conversation(self, conversation_id, question, answer, relevance, relevance_explanation,
                          prompt_tokens, completion_tokens, total_tokens,
                          eval_prompt_tokens, eval_completion_tokens, eval_total_tokens,
                          openai_cost, response_time, session_id=None):
        """
        Save conversation to database for monitoring
        
        Args:
            conversation_id: Unique conversation identifier
            question: User's question
            answer: RAG system's answer
            relevance: Relevance classification (RELEVANT/PARTLY_RELEVANT/NON_RELEVANT)
            relevance_explanation: Explanation of relevance rating
            prompt_tokens: Tokens used in prompt
            completion_tokens: Tokens in completion
            total_tokens: Total tokens for answer generation
            eval_prompt_tokens: Tokens used in evaluation prompt
            eval_completion_tokens: Tokens in evaluation completion
            eval_total_tokens: Total tokens for evaluation
            openai_cost: Total cost in USD
            response_time: Response time in seconds
            session_id: Optional session identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        insert_query = """
        INSERT INTO conversations 
        (id, question, answer, relevance, relevance_explanation, 
         prompt_tokens, completion_tokens, total_tokens,
         eval_prompt_tokens, eval_completion_tokens, eval_total_tokens,
         openai_cost, response_time, timestamp, session_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            timestamp = datetime.now()
            
            cursor.execute(insert_query, (
                conversation_id, question, answer, relevance, relevance_explanation,
                prompt_tokens, completion_tokens, total_tokens,
                eval_prompt_tokens, eval_completion_tokens, eval_total_tokens,
                openai_cost, response_time, timestamp, session_id
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving conversation: {e}")
            return False
    
    def save_feedback(self, question, answer, feedback_value, session_id=None):
        """
        Save user feedback to database
        
        Args:
            question: User's question
            answer: RAG system's answer
            feedback_value: +1 or -1
            session_id: Optional session identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        insert_query = """
        INSERT INTO feedback (id, question, answer, feedback, timestamp, session_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            feedback_id = str(uuid.uuid4())
            timestamp = datetime.now()
            
            cursor.execute(insert_query, (
                feedback_id,
                question,
                answer,
                feedback_value,
                timestamp,
                session_id
            ))
            
            conn.commit()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"Error saving feedback: {e}")
            return False
    
    def get_feedback_stats(self, session_id=None):
        """
        Get feedback statistics
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            dict: Statistics including total, positive, and negative feedback counts
        """
        if session_id:
            query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as negative
            FROM feedback
            WHERE session_id = %s
            """
            params = (session_id,)
        else:
            query = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN feedback = 1 THEN 1 ELSE 0 END) as positive,
                SUM(CASE WHEN feedback = -1 THEN 1 ELSE 0 END) as negative
            FROM feedback
            """
            params = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=DictCursor)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return {
                'total': result['total'] if result['total'] else 0,
                'positive': result['positive'] if result['positive'] else 0,
                'negative': result['negative'] if result['negative'] else 0
            }
        except Exception as e:
            print(f"Error getting feedback stats: {e}")
            return {'total': 0, 'positive': 0, 'negative': 0}
    
    def get_recent_feedback(self, limit=10):
        """
        Get recent feedback entries
        
        Args:
            limit: Number of entries to retrieve
            
        Returns:
            list: Recent feedback entries
        """
        query = """
        SELECT id, question, answer, feedback, timestamp, session_id
        FROM feedback
        ORDER BY timestamp DESC
        LIMIT %s
        """
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(query, (limit,))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            return [dict(row) for row in results]
        except Exception as e:
            print(f"Error getting recent feedback: {e}")
            return []
    
    def get_conversation_stats(self):
        """
        Get conversation statistics for monitoring
        
        Returns:
            dict: Various statistics about conversations
        """
        query = """
        SELECT 
            COUNT(*) as total_conversations,
            AVG(response_time) as avg_response_time,
            AVG(openai_cost) as avg_cost,
            SUM(openai_cost) as total_cost,
            COUNT(CASE WHEN relevance = 'RELEVANT' THEN 1 END) as relevant_count,
            COUNT(CASE WHEN relevance = 'PARTLY_RELEVANT' THEN 1 END) as partly_relevant_count,
            COUNT(CASE WHEN relevance = 'NON_RELEVANT' THEN 1 END) as non_relevant_count
        FROM conversations
        WHERE timestamp >= NOW() - INTERVAL '24 hours'
        """
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=DictCursor)
            cursor.execute(query)
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return dict(result) if result else {}
        except Exception as e:
            print(f"Error getting conversation stats: {e}")
            return {}