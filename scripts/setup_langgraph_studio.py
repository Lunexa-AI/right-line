#!/usr/bin/env python3
"""
Setup script for LangGraph Studio integration.

This script prepares the RightLine Legal Assistant for development
with LangGraph Studio, providing full observability and debugging.

Usage:
    python scripts/setup_langgraph_studio.py
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import structlog

logger = structlog.get_logger(__name__)


def check_dependencies():
    """Check if required dependencies are installed."""
    
    required_packages = [
        "langgraph",
        "langchain",
        "langchain-openai",
        "langsmith"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(
            "Missing required packages for LangGraph Studio",
            missing_packages=missing_packages
        )
        print("\nTo install missing packages, run:")
        print(f"pip install {' '.join(missing_packages)}")
        return False
    
    logger.info("All required packages are installed")
    return True


def setup_environment():
    """Set up environment variables for LangGraph Studio."""
    
    env_file = project_root / ".env.local"
    
    if not env_file.exists():
        logger.warning(
            "Environment file not found, creating from example",
            path=str(env_file)
        )
        
        # Copy from example
        example_env = project_root / "configs" / "example.env"
        if example_env.exists():
            import shutil
            shutil.copy(example_env, env_file)
        else:
            # Create minimal .env.local
            with open(env_file, 'w') as f:
                f.write("""# LangGraph Studio Configuration
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=rightline-legal-assistant
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com

# LangGraph Studio
LANGGRAPH_STUDIO_ENABLED=true
LANGGRAPH_CHECKPOINTER_TYPE=sqlite

# OpenAI (required for the legal assistant)
OPENAI_API_KEY=your_openai_api_key_here

# Milvus (for document retrieval)
MILVUS_ENDPOINT=your_milvus_endpoint
MILVUS_TOKEN=your_milvus_token
MILVUS_COLLECTION_NAME=legal_chunks_v3

# Cloudflare R2 (for document storage)
CLOUDFLARE_R2_S3_ENDPOINT=your_r2_endpoint
CLOUDFLARE_R2_ACCESS_KEY_ID=your_r2_access_key
CLOUDFLARE_R2_SECRET_ACCESS_KEY=your_r2_secret_key
CLOUDFLARE_R2_BUCKET_NAME=your_r2_bucket
""")
    
    logger.info("Environment file ready", path=str(env_file))
    
    # Check if LangSmith API key is set
    if not os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGCHAIN_API_KEY") == "your_langsmith_api_key_here":
        logger.warning(
            "LangSmith API key not configured",
            message="Set LANGCHAIN_API_KEY in .env.local for full tracing"
        )
        return False
    
    return True


def verify_langgraph_config():
    """Verify LangGraph configuration file."""
    
    config_file = project_root / "langgraph.json"
    
    if not config_file.exists():
        logger.error(
            "LangGraph configuration not found",
            path=str(config_file),
            message="Run this script from the project root"
        )
        return False
    
    # Verify the configuration
    import json
    try:
        with open(config_file) as f:
            config = json.load(f)
        
        required_keys = ["dependencies", "graphs", "env"]
        for key in required_keys:
            if key not in config:
                logger.error(f"Missing required key in langgraph.json: {key}")
                return False
        
        logger.info("LangGraph configuration verified", config=config)
        return True
        
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in langgraph.json", error=str(e))
        return False


def test_orchestrator():
    """Test the query orchestrator to ensure it works."""
    
    try:
        from api.agents.query_orchestrator import get_orchestrator
        
        orchestrator = get_orchestrator()
        logger.info(
            "Query orchestrator initialized successfully",
            workflow_nodes=list(orchestrator.workflow.nodes.keys()) if hasattr(orchestrator.workflow, 'nodes') else "unknown"
        )
        return True
        
    except Exception as e:
        logger.error(
            "Failed to initialize query orchestrator",
            error=str(e),
            exc_info=True
        )
        return False


def print_studio_instructions():
    """Print instructions for using LangGraph Studio."""
    
    print("\n" + "="*60)
    print("🚀 LangGraph Studio Setup Complete!")
    print("="*60)
    
    print("\n📋 Next Steps:")
    print("1. Install LangGraph Studio (if not already installed):")
    print("   pip install langgraph-studio")
    
    print("\n2. Start LangGraph Studio:")
    print("   langgraph studio")
    
    print("\n3. Open your browser to: http://localhost:8123")
    
    print("\n4. In LangGraph Studio, you can:")
    print("   • Visualize the complete agentic workflow")
    print("   • Step through each node execution")
    print("   • Inspect agent state at every step")
    print("   • Debug query processing in real-time")
    print("   • Optimize prompts and logic")
    
    print("\n🔍 Observability Features:")
    print("   • Full LangSmith tracing integration")
    print("   • Node-by-node execution timing")
    print("   • State inspection and debugging")
    print("   • Quality gate monitoring")
    print("   • Performance metrics tracking")
    
    print("\n📊 Test Queries to Try:")
    print("   • 'What are the requirements for art unions?'")
    print("   • 'What are the duties of company directors?'")
    print("   • 'How does property acquisition work?'")
    
    print("\n⚙️  Configuration:")
    print(f"   • Project: {os.getenv('LANGCHAIN_PROJECT', 'rightline-legal-assistant')}")
    print(f"   • Environment: {project_root / '.env.local'}")
    print(f"   • LangGraph Config: {project_root / 'langgraph.json'}")
    
    print("\n" + "="*60)


def main():
    """Main setup function."""
    
    logger.info("Starting LangGraph Studio setup")
    
    # Check dependencies
    if not check_dependencies():
        return False
    
    # Set up environment
    if not setup_environment():
        logger.warning("Environment setup incomplete - some features may not work")
    
    # Verify LangGraph configuration
    if not verify_langgraph_config():
        return False
    
    # Test orchestrator
    if not test_orchestrator():
        return False
    
    # Print instructions
    print_studio_instructions()
    
    logger.info("LangGraph Studio setup completed successfully")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
