#!/usr/bin/env python3
import os
import sys
import subprocess
import textwrap
import json
import requests

# Adjust to your actual CodeLLaMA endpoint
LLM_ENDPOINT = os.environ.get("LLM_ENDPOINT", "http://code.llama.local:8000/v1/chat/completions")
LLM_MODEL = os.environ.get("LLM_MODEL", "codellama-13b")  # or whatever you named it

def get_diff_for_files(file_list):
    diff_texts = []
    for path in file_list:
        if not path:
            continue
        try:
            diff = subprocess.check_output(
                ["git", "diff", "origin/main...HEAD", "--", path],
                text=True
            )
            if diff.strip():
                diff_texts.append(f"### File: {path}\n```diff\n{diff}\n```")
        except subprocess.CalledProcessError:
            # If diff fails for some reason, skip this file
            continue
    return "\n\n".join(diff_texts)

def call_llm(prompt: str) -> str:
    """
    Call local CodeLLaMA HTTP endpoint with an OpenAI-style chat completion request.
    Adjust this if your server expects a different schema.
    """
    headers = {
        "Content-Type": "application/json",
        # If your local server uses a token, uncomment and set LLM_API_KEY in Jenkins:
        # "Authorization": f"Bearer {os.environ.get('LLM_API_KEY', '')}"
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a senior C# and DevOps code reviewer."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2
    }

    resp = requests.post(LLM_ENDPOINT, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()

    # OpenAI-like response shape: choices[0].message.content
    # Adjust if your server returns something different.
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        # Fallback – dump raw JSON for debugging
        return f"LLM returned unexpected response:\n\n```json\n{json.dumps(data, indent=2)}\n```"

def main():
    if len(sys.argv) != 3:
        print("Usage: llm_review.py <changed_files.txt> <output.md>")
        sys.exit(1)

    changed_files_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(changed_files_path):
        with open(output_path, "w") as out:
            out.write("No changed_files.txt found; skipping LLM review.\n")
        return

    with open(changed_files_path) as f:
        files = [line.strip() for line in f if line.strip()]

    if not files:
        with open(output_path, "w") as out:
            out.write("No changed files to review.\n")
        return

    diff_block = get_diff_for_files(files)
    if not diff_block.strip():
        with open(output_path, "w") as out:
            out.write("No diffs to review.\n")
        return

    prompt = textwrap.dedent(f"""
    You are performing a code review for a C# ASP.NET Core API and its CI/CD pipeline.

    Focus on:
    - Correctness and potential bugs
    - Security and input validation
    - Async, resource usage, and performance
    - Testability and maintainability
    - CI/CD and Dockerfile best practices

    For each issue, use this format exactly:

    - [SEVERITY: LOW|MEDIUM|HIGH] Short descriptive title
      - File: <file-path>
      - Description: <what is wrong and why it matters>
      - Suggestion: <specific improvement or code change>

    If there are no significant issues, say:
    "No major issues found in the reviewed changes."

    Review the following diffs:

    {diff_block}
    """)

    try:
        review_text = call_llm(prompt)
    except Exception as ex:
        review_text = f"Error calling local CodeLLaMA at {LLM_ENDPOINT}:\n\n{ex}"

    with open(output_path, "w") as out:
        out.write("# LLM Code Review (CodeLLaMA)\n\n")
        out.write(review_text)
        out.write("\n")

if __name__ == "__main__":
    main()
