#!/bin/bash

# =============================================================================
# CI Validation Script for Noesium
# =============================================================================
# This script runs all validation steps used in GitHub Actions CI workflow.
# It ensures code quality, runs tests, and verifies builds for all packages.
#
# Usage:
#   ./scripts/validate_ci.sh [OPTIONS]
#
# Options:
#   --skip-tests      Skip running tests
#   --skip-build      Skip building packages
#   --skip-format     Skip formatting checks
#   --skip-lint       Skip linting
#   --quick           Run quick validation (format + lint only)
#   -h, --help        Show this help message
#
# Exit codes:
#   0 - All validations passed
#   1 - Validation failed
# =============================================================================

set -e          # Exit on error
set -o pipefail # Catch errors in pipes

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default options
SKIP_TESTS=false
SKIP_BUILD=false
SKIP_FORMAT=false
SKIP_LINT=false
QUICK_MODE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
  --skip-tests)
    SKIP_TESTS=true
    shift
    ;;
  --skip-build)
    SKIP_BUILD=true
    shift
    ;;
  --skip-format)
    SKIP_FORMAT=true
    shift
    ;;
  --skip-lint)
    SKIP_LINT=true
    shift
    ;;
  --quick)
    QUICK_MODE=true
    shift
    ;;
  -h | --help)
    echo "CI Validation Script for Noesium"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --skip-tests      Skip running tests"
    echo "  --skip-build      Skip building packages"
    echo "  --skip-format     Skip formatting checks"
    echo "  --skip-lint       Skip linting"
    echo "  --quick           Run quick validation (format + lint only)"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Exit codes:"
    echo "  0 - All validations passed"
    echo "  1 - Validation failed"
    exit 0
    ;;
  *)
    echo -e "${RED}Error: Unknown option: $1${NC}"
    echo "Run '$0 --help' for usage information"
    exit 1
    ;;
  esac
done

# If quick mode, skip tests and build
if [ "$QUICK_MODE" = true ]; then
  SKIP_TESTS=true
  SKIP_BUILD=true
fi

# Track overall status
OVERALL_STATUS=0

# Helper function to print section headers
print_header() {
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${BLUE}  $1${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

# Helper function to print success message
print_success() {
  echo -e "${GREEN}✅ $1${NC}"
}

# Helper function to print error message
print_error() {
  echo -e "${RED}❌ $1${NC}"
  OVERALL_STATUS=1
}

# Helper function to print warning message
print_warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check if we're in the project root
if [ ! -f "pyproject.toml" ] || [ ! -d "noesium" ] || [ ! -d "noeagent" ]; then
  print_error "This script must be run from the project root directory"
  echo "Expected to find: pyproject.toml, noesium/, noeagent/"
  exit 1
fi

# Check if uv is installed
if ! command -v uv &>/dev/null; then
  print_error "uv is not installed"
  echo "Please install uv: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi

print_header "CI Validation Script Started"
echo "Configuration:"
echo "  - Skip tests: $SKIP_TESTS"
echo "  - Skip build: $SKIP_BUILD"
echo "  - Skip format: $SKIP_FORMAT"
echo "  - Skip lint: $SKIP_LINT"
echo "  - Quick mode: $QUICK_MODE"

# =============================================================================
# STEP 1: Install Dependencies
# =============================================================================
print_header "Step 1: Installing Dependencies"

echo "Installing workspace dependencies..."
if uv sync --all-packages --extra dev --extra all; then
  print_success "Dependencies installed successfully"
else
  print_error "Failed to install dependencies"
  exit 1
fi

# =============================================================================
# STEP 2: Code Formatting Check
# =============================================================================
if [ "$SKIP_FORMAT" = false ]; then
  print_header "Step 2: Code Formatting Check"

  echo "Checking code formatting with Black..."
  if uv run black --check noesium/src noesium/tests noeagent/src noeagent/tests --line-length 120; then
    print_success "Black formatting check passed"
  else
    print_error "Black formatting check failed"
    print_warning "Run 'make format' to fix formatting issues"
  fi

  echo ""
  echo "Checking import sorting with isort..."
  if uv run isort --check-only noesium/src noesium/tests noeagent/src noeagent/tests --line-length 120; then
    print_success "isort check passed"
  else
    print_error "isort check failed"
    print_warning "Run 'make format' to fix import sorting issues"
  fi
else
  print_header "Step 2: Code Formatting Check (SKIPPED)"
fi

# =============================================================================
# STEP 3: Linting
# =============================================================================
if [ "$SKIP_LINT" = false ]; then
  print_header "Step 3: Linting"

  echo "Running ruff linter..."
  if uv run ruff check noesium/src noesium/tests noeagent/src noeagent/tests --line-length 120; then
    print_success "Ruff linting passed"
  else
    print_error "Ruff linting failed"
    print_warning "Fix linting issues or run 'make lint-fix' for auto-fixes"
  fi

  echo ""
  echo "Running flake8 linter..."
  if uv run flake8 --max-line-length=120 --extend-ignore=E203,W503,E402,E501,W291,W293,E101,W191,F811 noesium/src noesium/tests noeagent/src noeagent/tests; then
    print_success "Flake8 linting passed"
  else
    print_error "Flake8 linting failed"
    print_warning "Fix linting issues manually"
  fi
else
  print_header "Step 3: Linting (SKIPPED)"
fi

# =============================================================================
# STEP 4: Run Tests
# =============================================================================
if [ "$SKIP_TESTS" = false ]; then
  print_header "Step 4: Running Tests"

  echo "Running noesium tests..."
  if uv run pytest noesium/tests/ -v; then
    print_success "Noesium tests passed"
  else
    print_error "Noesium tests failed"
  fi

  echo ""
  echo "Running noeagent tests (excluding LLM tests)..."
  if uv run pytest noeagent/tests/ -v -m "not llm"; then
    print_success "Noeagent tests passed"
  else
    print_error "Noeagent tests failed"
  fi
else
  print_header "Step 4: Running Tests (SKIPPED)"
fi

# =============================================================================
# STEP 5: Build Packages
# =============================================================================
if [ "$SKIP_BUILD" = false ]; then
  print_header "Step 5: Building Packages"

  echo "Building noesium package..."
  if cd noesium && uv build; then
    cd ..
    print_success "Noesium package built successfully"
  else
    cd ..
    print_error "Failed to build noesium package"
  fi

  echo ""
  echo "Building noeagent package..."
  if cd noeagent && uv build; then
    cd ..
    print_success "Noeagent package built successfully"
  else
    cd ..
    print_error "Failed to build noeagent package"
  fi
else
  print_header "Step 5: Building Packages (SKIPPED)"
fi

# =============================================================================
# Final Summary
# =============================================================================
print_header "Validation Summary"

if [ $OVERALL_STATUS -eq 0 ]; then
  echo -e "${GREEN}"
  echo "  ╔════════════════════════════════════════════════════════════╗"
  echo "  ║                  ALL VALIDATIONS PASSED!                   ║"
  echo "  ╚════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
else
  echo -e "${RED}"
  echo "  ╔════════════════════════════════════════════════════════════╗"
  echo "  ║                  SOME VALIDATIONS FAILED                   ║"
  echo "  ╚════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  echo ""
  print_warning "Please fix the issues above and run the script again"
fi

exit $OVERALL_STATUS

