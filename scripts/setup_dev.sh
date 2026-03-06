#!/bin/bash

# Development Environment Setup Script for Noesium Workspace
# This script sets up a complete development environment for all three subprojects

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Setting up Noesium development environment...${NC}"
echo ""

# Check Python version
echo -e "${BLUE}📌 Checking Python version...${NC}"
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
REQUIRED_VERSION="3.11.0"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
    echo -e "${GREEN}✅ Python $PYTHON_VERSION found${NC}"
else
    echo -e "${RED}❌ Python >= 3.11 required. Found: $PYTHON_VERSION${NC}"
    exit 1
fi

# Install uv if not present
echo -e "${BLUE}📦 Checking for uv package manager...${NC}"
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}uv not found. Installing...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo -e "${GREEN}✅ uv installed${NC}"

    # Add uv to PATH for current session
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo -e "${GREEN}✅ uv already installed: $(uv --version)${NC}"
fi

# Sync workspace dependencies
echo -e "${BLUE}📚 Syncing workspace dependencies...${NC}"
uv sync --all-packages --extra dev --extra all
echo -e "${GREEN}✅ Dependencies synced${NC}"

# Setup pre-commit hooks if available
echo -e "${BLUE}🔧 Setting up pre-commit hooks...${NC}"
if [ -f ".pre-commit-config.yaml" ]; then
    uv run pre-commit install
    echo -e "${GREEN}✅ Pre-commit hooks installed${NC}"
else
    echo -e "${YELLOW}⚠️  No .pre-commit-config.yaml found, skipping${NC}"
fi

# Create necessary directories
echo -e "${BLUE}📁 Creating necessary directories...${NC}"
mkdir -p .local/logs
mkdir -p .local/data
mkdir -p workspace
echo -e "${GREEN}✅ Directories created${NC}"

# Create .env.example if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo -e "${BLUE}📝 Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${GREEN}✅ .env created${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env with your API keys${NC}"
    else
        echo -e "${YELLOW}⚠️  No .env.example found, creating basic .env...${NC}"
        cat > .env << EOF
# LLM Provider Configuration
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here

# Alternative providers
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# Local models
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=llama3

# Shared Services
WEAVIATE_URL=http://localhost:8080
POSTGRES_URL=postgresql://user:password@localhost:5432/vectordb

# Voyager Configuration
VOYAGER_SECRET_KEY=your-secret-key-here
VOYAGER_DATABASE_URL=sqlite:///./voyager.db
EOF
        echo -e "${GREEN}✅ Basic .env created${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env with your configuration${NC}"
    fi
fi

# Install frontend dependencies for Voyager
echo -e "${BLUE}📦 Checking Voyager frontend dependencies...${NC}"
if [ -d "voyager/frontend" ]; then
    if command -v npm &> /dev/null; then
        echo -e "${BLUE}Installing Node.js dependencies...${NC}"
        cd voyager/frontend
        npm install
        cd ../..
        echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
    else
        echo -e "${YELLOW}⚠️  npm not found, skipping frontend setup${NC}"
        echo -e "${YELLOW}   Install Node.js to work with Voyager frontend${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Voyager frontend not found${NC}"
fi

# Print summary
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Development environment setup complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Edit ${YELLOW}.env${NC} with your API keys"
echo -e "  2. Run ${YELLOW}make test-all${NC} to verify installation"
echo -e "  3. Start developing!"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo -e "  ${YELLOW}make install-workspace${NC}    - Install all packages"
echo -e "  ${YELLOW}make test-all${NC}            - Run all tests"
echo -e "  ${YELLOW}make build-all${NC}           - Build all packages"
echo -e "  ${YELLOW}make quality${NC}             - Run code quality checks"
echo ""
echo -e "${BLUE}Subprojects:${NC}"
echo -e "  • ${GREEN}noesium${NC}    - Core framework (${YELLOW}cd noesium && uv run python${NC})"
echo -e "  • ${GREEN}noeagent${NC}   - CLI/TUI app (${YELLOW}cd noeagent && uv run noeagent${NC})"
echo -e "  • ${GREEN}voyager${NC}    - Web app (${YELLOW}cd voyager/backend && uv run voyager${NC})"
echo ""