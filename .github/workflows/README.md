# GitHub Actions Setup

## Training Dataset Workflow

The `train-on-dataset.yml` workflow processes each entry in the training dataset through paketerix.

### Required Secrets

You need to configure the following secret in your GitHub repository:

1. **ANTHROPIC_API_KEY** - Your Anthropic API key for Claude models

To add this secret:
1. Go to your repository on GitHub
2. Click on Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Add the secret with name ANTHROPIC_API_KEY and your API key as the value

### Optional Variables

- **OLLAMA_BASE_URL** - Base URL for Ollama API (defaults to `http://localhost:11434`)

### Workflow Features

- **Matrix Build**: Processes each training data entry in parallel (max 5 concurrent)
- **Artifact Storage**: Stores output JSON and error logs for 30 days
- **Summary Reports**: Creates job summaries with processing status
- **Combined Results**: Aggregates all results into a single artifact (90 days retention)

### Manual Trigger

You can manually trigger the workflow from the Actions tab using the "Run workflow" button.

### Automatic Triggers

The workflow runs automatically when:
- Changes are pushed to the main branch in:
  - Training dataset CSV
  - Source code
  - Workflow file itself