#!/usr/bin/env python3
"""
LLM Code Review using local CodeLLaMA

- Compares current HEAD against origin/main
- Reads a list of changed files from changed_files.txt
- Filters out EF Core migration files (Migrations/ and *ModelSnapshot.cs)
- Calls a local CodeLLaMA HTTP endpoint to perform a code review
- Writes a markdown report to the specified output file

Usage:
    llm_review.py <changed_files.txt> <output.md>
"""

import os
import sys
import subprocess
import textwrap
import json
from typing import List

import requests


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default endpoint for your local CodeLLaMA instance
# Override via environment variable LLM_ENDPOINT if needed.
LLM_ENDPOINT = os.environ.get(
    "LLM_ENDPOINT",
    "http://code.llama.local:8000/v1/chat/completions"
)

# Name/alias of the model exposed by your local LLaMA server
LLM_MODEL = os.environ.get("LLM_MODEL", "codellama-13b")

# If your local service needs a token, set LLM_API_KEY in Jenkins
# and uncomment the Authorization header in call_llm().
USE_AUTH_HEADER = False  # set True if you require a Bearer token


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def read_changed_files(path: str) -> List[str]:
    """Read list of changed files from a text file, one path per line."""
    if not os.path.exists(path):
        return []

    with open(path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines


def filter_out_migrations(files: List[str]) -> List[str]:
    """
    Filter out EF Core migration files, such as:

      - */Migrations/<anything>.cs
      - *ModelSnapshot.cs
    """
    result: List[str] = []
    for p in files:
        norm = p.replace("\\", "/")
        if "/Migrations/" in norm:
            # Skip EF migrations directory
            continue
        if norm.endswith("ModelSnapshot.cs"):
            # Skip EF model snapshot
            continue
        result.append(p)
    return result


def get_diff_for_files(file_list: List[str]) -> str:
    """
    Build a combined diff text for the specified files, comparing
    origin/main...HEAD. Each file is grouped under a markdown heading.
    """
    diff_texts = []
    for path in file_list:
        if not path:
            continue
        try:
            diff = subprocess.check_output(
                ["git", "diff", "origin/main...HEAD", "--", path],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            # If diff fails, skip this file
            continue

        if diff.strip():
            diff_texts.append(f"### File: {path}\n```diff\n{diff}\n```")

    return "\n\n".join(diff_texts)


def call_llm(prompt: str) -> str:
    """
    Call the local CodeLLaMA endpoint using an OpenAI-style chat completion API.
    Adjust this function if your server uses a different schema.
    """
    headers = {
        "Content-Type": "application/json",
    }

    if USE_AUTH_HEADER:
        api_key = os.environ.get("LLM_API_KEY", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior C# ASP.NET Core and DevOps code reviewer.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.2,
    }

    resp = requests.post(
        LLM_ENDPOINT,
        headers=headers,
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    # OpenAI-style response: choices[0].message.content
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        # Fallback: dump raw JSON for debugging purposes
        return (
            "LLM returned an unexpected response structure:\n\n"
            "```json\n" + json.dumps(data, indent=2) + "\n```"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: llm_review.py <changed_files.txt> <output.md>")
        sys.exit(1)

    changed_files_path = sys.argv[1]
    output_path = sys.argv[2]

    # 1. Read changed files
    all_files = read_changed_files(changed_files_path)

    # 2. Filter out EF Core migrations
    files = filter_out_migrations(all_files)

    if not files:
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(
                "No non-migration files to review. "
                "EF Core migration files were intentionally ignored.\n"
            )
        return

    # 3. Build a diff block for the LLM
    diff_block = get_diff_for_files(files)

    if not diff_block.strip():
        with open(output_path, "w", encoding="utf-8") as out:
            out.write("No diffs to review for the filtered file set.\n")
        return

    # 4. Build the review prompt
    prompt = textwrap.dedent(
        f"""
        You are performing a code review for a C# ASP.NET Core API project
        and its CI/CD pipeline configuration.

        Focus your review on:
        - Correctness and potential bugs
        - Security and input validation
        - Performance, async, and resource usage
        - Testability and maintainability
        - CI/CD and Dockerfile/Jenkinsfile best practices

        IMPORTANT:
        - Ignore EF Core migration files; they were filtered out already.
        - If the code looks reasonable overall, still highlight any potential risks or improvements.

        For each issue, use this exact format:

        - [SEVERITY: LOW|MEDIUM|HIGH] Short descriptive title
          - File: <file-path>
          - Description: <what is wrong and why it matters>
          - Suggestion: <specific improvement or code change>

        If there are no significant issues worth mentioning, write:
        "No major issues found in the reviewed changes."

        Review the following diffs between origin/main and the current branch:

        {diff_block}
        """
    )

    # 5. Call local CodeLLaMA
    try:
        review_text = call_llm(prompt)
    except Exception as ex:
        review_text = (
            f"Error calling local CodeLLaMA at {LLM_ENDPOINT}:\n\n"
            f"{type(ex).__name__}: {ex}\n"
        )

    # 6. Write markdown report
    with open(output_path, "w", encoding="utf-8") as out:
        out.write("# LLM Code Review (CodeLLaMA)\n\n")
        out.write(review_text)
        out.write("\n")


if __name__ == "__main__":
    main()
