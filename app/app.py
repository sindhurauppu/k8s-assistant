from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

import streamlit as st
import uuid
from rag import RAGSystem
from db import FeedbackDatabase


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'rag_system' not in st.session_state:
        st.session_state.rag_system = RAGSystem()
    
    if 'feedback_db' not in st.session_state:
        st.session_state.feedback_db = FeedbackDatabase()
        
    if 'db_initialized' not in st.session_state:
        # Try to initialize database
        success, message = st.session_state.feedback_db.init_table()
        st.session_state.db_initialized = success
        st.session_state.db_error_message = message if not success else None
    
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    
    if 'feedback_given' not in st.session_state:
        st.session_state.feedback_given = {}


def display_feedback_buttons(idx, question, answer):
    """
    Display +1/-1 feedback buttons for a specific Q&A pair
    
    Args:
        idx: Index of the conversation in history
        question: User's question
        answer: RAG system's answer
    """
    col1, col2, col3 = st.columns([1, 1, 8])
    
    feedback_key = f"feedback_{idx}"
    
    with col1:
        if st.button("👍 +1", key=f"plus_{idx}", disabled=feedback_key in st.session_state.feedback_given or not st.session_state.db_initialized):
            if st.session_state.feedback_db.save_feedback(
                question, 
                answer, 
                1, 
                st.session_state.session_id
            ):
                st.session_state.feedback_given[feedback_key] = 1
                st.success("Thanks for your feedback!")
                st.rerun()
    
    with col2:
        if st.button("👎 -1", key=f"minus_{idx}", disabled=feedback_key in st.session_state.feedback_given or not st.session_state.db_initialized):
            if st.session_state.feedback_db.save_feedback(
                question, 
                answer, 
                -1, 
                st.session_state.session_id
            ):
                st.session_state.feedback_given[feedback_key] = -1
                st.warning("Thanks for your feedback!")
                st.rerun()
    
    with col3:
        if feedback_key in st.session_state.feedback_given:
            feedback_val = st.session_state.feedback_given[feedback_key]
            emoji = "👍" if feedback_val == 1 else "👎"
            st.caption(f"Feedback recorded: {emoji}")


def main():
    st.set_page_config(
        page_title="KubeQuery RAG",
        page_icon="☸️",
        layout="wide"
    )
    
    st.title("☸️ KubeQuery RAG Application")
    st.markdown("Ask questions about Kubernetes and get AI-powered answers!")
    
    # Initialize session state
    initialize_session_state()
    
    # Show database warning if not initialized
    if not st.session_state.db_initialized:
        st.warning(
            f"⚠️ Database connection failed. Feedback features are disabled.\n\n"
            f"Error: {st.session_state.db_error_message}\n\n"
            f"The app will still work for Q&A, but feedback won't be saved."
        )
    
    # Check if Elasticsearch index exists
    if not st.session_state.rag_system.index_exists:
        st.error(
            f"❌ Elasticsearch index '{st.session_state.rag_system.index_name}' not found!\n\n"
            f"Please run the indexing script first:\n\n"
            f"```bash\npython index_documents.py\n```"
        )
        st.stop()
    
    # Sidebar with info
    with st.sidebar:
        st.header("About")
        st.info(
            "This application uses Retrieval-Augmented Generation (RAG) "
            "to answer Kubernetes questions using:\n"
            "- Elasticsearch for hybrid search\n"
            "- OpenAI GPT-4 for answers\n"
            "- Sentence Transformers for embeddings"
        )
        
        st.header("Session Info")
        st.caption(f"Session ID: {st.session_state.session_id[:8]}...")
        st.caption(f"Questions asked: {len(st.session_state.conversation_history)}")
        
        # Display feedback stats
        if st.session_state.db_initialized:
            try:
                stats = st.session_state.feedback_db.get_feedback_stats(st.session_state.session_id)
                st.header("Feedback Stats")
                st.metric("Total Feedback", stats['total'])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("👍 Positive", stats['positive'])
                with col2:
                    st.metric("👎 Negative", stats['negative'])
            except Exception as e:
                st.caption("Feedback stats unavailable")
        else:
            st.caption("💾 Database offline - feedback disabled")
    
    # Main input area
    user_input = st.text_input("Enter your Kubernetes question:", placeholder="e.g., How do I deploy a pod?")
    
    if st.button("Ask", type="primary"):
        if user_input.strip():
            with st.spinner('🔍 Searching knowledge base and generating answer...'):
                try:
                    result = st.session_state.rag_system.query(user_input)
                    
                    # Save conversation to database for monitoring
                    if st.session_state.db_initialized:
                        conversation_id = str(uuid.uuid4())
                        st.session_state.feedback_db.save_conversation(
                            conversation_id=conversation_id,
                            question=user_input,
                            answer=result['answer'],
                            relevance=result['relevance'],
                            relevance_explanation=result['relevance_explanation'],
                            prompt_tokens=result['prompt_tokens'],
                            completion_tokens=result['completion_tokens'],
                            total_tokens=result['total_tokens'],
                            eval_prompt_tokens=result['eval_prompt_tokens'],
                            eval_completion_tokens=result['eval_completion_tokens'],
                            eval_total_tokens=result['eval_total_tokens'],
                            openai_cost=result['openai_cost'],
                            response_time=result['response_time'],
                            session_id=st.session_state.session_id
                        )
                    
                    # Add to conversation history
                    st.session_state.conversation_history.append({
                        'question': user_input,
                        'answer': result['answer'],
                        'search_results': result['search_results'],
                        'relevance': result['relevance'],
                        'response_time': result['response_time'],
                        'openai_cost': result['openai_cost']
                    })
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
        else:
            st.warning("Please enter a question!")
    
    # Display conversation history
    if st.session_state.conversation_history:
        st.markdown("---")
        st.header("Conversation History")
        
        for idx, item in enumerate(reversed(st.session_state.conversation_history)):
            with st.container():
                st.markdown(f"**Q: {item['question']}**")
                st.markdown(item['answer'])
                
                # Show feedback buttons
                display_feedback_buttons(
                    len(st.session_state.conversation_history) - idx - 1,
                    item['question'],
                    item['answer']
                )
                
                # Optional: Show sources
                with st.expander("📚 View sources"):
                    for i, doc in enumerate(item['search_results'], 1):
                        st.markdown(f"**Source {i}:** {doc.get('title', 'N/A')}")
                        st.caption(f"File: {doc.get('source_file', 'N/A')}")
                
                st.markdown("---")


if __name__ == "__main__":
    main()