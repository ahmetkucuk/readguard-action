# ReadGuard Action

Proprietary "Proof-of-Reading" GitHub Action.
Ensures developers have actually read their code changes by answering a generated question about the diff.

## ZERO-TRUST ARCHITECTURE
- **BYOK (Bring Your Own Key)**: Uses your own API Key (OpenAI or Gemini).
- **Stateless**: No external database. Verification logic is stored in the PR comment metadata (hashed).
- **Secure**: Code never leaves the GitHub Runner + LLM pipeline.

## Usage

Create `.github/workflows/readguard.yml`:

```yaml
name: ReadGuard

on:
  pull_request:
    types: [opened, synchronize]
  issue_comment:
    types: [created]

jobs:
  # Job 1: Generate the Question (Runs on new code)
  generate_challenge:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      checks: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - name: Generate Quiz
        uses: ./ # Points to this action in the root
        env:
          INPUT_API_KEY: ${{ secrets.OPENAI_API_KEY }} # Or GEMINI_API_KEY
          INPUT_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          INPUT_MODE: "generate"
          INPUT_PROVIDER: "openai" # or "gemini"

  # Job 2: Verify the Answer (Runs on comment)
  verify_answer:
    if: github.event_name == 'issue_comment' && contains(github.event.comment.body, '/answer')
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
      checks: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - name: Verify Answer
        uses: ./
        env:
          INPUT_GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          INPUT_MODE: "verify"
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `api_key` | Your Provider (OpenAI/Gemini) API Key. | **Yes** (Generate) | - |
| `github_token` | `secrets.GITHUB_TOKEN` | **Yes** | - |
| `provider` | `openai` or `gemini` | No | `openai` |
| `model` | Specific Model (e.g., `gpt-4o`, `gemini-2.5-flash`) | No | `gpt-4o`/`gemini-2.5-flash` |
| `mode` | `generate` or `verify` | **Yes** | `generate` |
| `difficulty` | `easy`\|`medium`\|`hard` | No | `medium` |
| `custom_instructions` | Add rules (e.g., "Check for SQLi") | No | - |
| `system_prompt` | Override default prompt | No | - |

## Development

```bash
# Build Docker
docker build -t readguard-action .
```
