# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Vibenix is an AI-powered assistant for creating Nix packages. It takes a GitHub repository URL and automatically generates Nix package definitions by iteratively improving templates until the package builds successfully.

## Development Environment

This project uses Nix with direnv for development. To enter the development shell:
```bash
# Automatically loads the environment when you cd into the directory (requires direnv)
direnv allow

# Or manually:
nix develop
```

## Common Commands

### Running the Application
```bash
# Run the Textual UI (recommended)
nix develop -c python -m vibenix

# Or if already in nix develop shell:
python -m vibenix
```

### Running Tests
```bash
# Run all tests
nix develop -c pytest

# Run tests with verbose output
nix develop -c pytest -v

# Run a specific test file
nix develop -c pytest tests/test_function_calls.py

# Run a specific test
nix develop -c pytest tests/test_function_calls.py::test_specific_function
```

### Building the Package
```bash
# Build the Nix package
nix build

# Run the built package
./result/bin/vibenix
```

## Code Architecture

### Core Components

1. **Main Application Flow** (`src/vibenix/`)
   - `main.py`: Entry point and CLI argument handling
   - `packaging_flow/run.py`: Main packaging workflow orchestration
   - `config.py`: Configuration management

2. **AI Integration** (`src/vibenix/`)
   - `function_calls.py` & `function_calls_source.py`: Tool calling implementation for AI models
   - `packaging_flow/model_prompts.py`: System prompts for the AI
   - `parsing.py`: Response parsing and caching

3. **Nix Operations** (`src/vibenix/`)
   - `nix.py`: Nix command execution and build operations
   - `flake.py`: Flake.nix generation and management
   - `template/`: Language-specific Nix package templates

4. **User Interface** (`src/vibenix/ui/`)
   - `textual/`: Rich TUI using Textual framework
   - `raw_terminal/`: Fallback terminal interface
   - `conversation.py`: Manages the conversation flow between user and AI

### Key Design Patterns

1. **Template-Based Packaging**: The system starts with language-specific templates (`src/vibenix/template/*.nix`) and iteratively refines them based on build errors.

2. **Function Calling**: Uses structured function calls to let the AI model interact with the Nix build system, file system, and search capabilities.

3. **Error-Driven Improvement**: The AI analyzes build errors and modifies the Nix expression until it builds successfully or reaches iteration limits.

4. **Multi-Provider Support**: Supports multiple AI providers (Gemini, Anthropic, Ollama) through litellm, though currently only Gemini has full tool calling support.

## Important Notes

- **Model Support**: Currently, only Gemini models have working tool calling support. Recommended model: `gemini/gemini-2.5-pro`
- **API Keys**: Stored securely using keyring. The app will prompt for keys on first run.
- **Caching**: Uses diskcache for caching AI responses and search results
- **Evaluation**: The `scripts/` directory contains evaluation and analysis tools for measuring packaging success rates

## Configuration

The application stores configuration in `.vibenix/config.json` including:
- Selected model provider
- Model name
- API endpoints (for Ollama)

API keys are stored separately in the system keyring for security.

## Testing Against Dataset

To test package generation against the dataset:
```bash
# GitHub Actions workflow can be triggered manually
# See .github/workflows/run-with-dataset.yml for parameters
```

## Template Development

When modifying package templates:
1. Templates are in `src/vibenix/template/*.nix`
2. Each template has an associated `.notes` file with guidance
3. Templates use placeholders that are replaced during generation
4. Test template changes with known packages of that language type