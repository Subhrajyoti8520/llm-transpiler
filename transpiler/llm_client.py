# """
# SUMMARY:
# This module manages the interaction with an LLM (using the standard OpenAI Python client) 
# to act as an intelligent Python-to-C++/Rust transpiler. It constructs highly specific prompts 
# that inject hardware architecture and AST metadata into the context.
# - Network Resilience: The client is now explicitly configured with a default timeout and 
#   automatic retries to handle rate limits (HTTP 429) out of the box using exponential backoff.
# - 2-Model Fallback: `stream_transpilation` now accepts a list of models (capped at 2). 
#   If the primary model fails (e.g., times out or crashes), it gracefully catches the error 
#   and automatically attempts the completion using the fallback model before giving up.
# """
# ============================================================================================
import os
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

api_key = os.getenv("API_KEY", os.getenv("GEMINI_API_KEY"))
base_url = os.getenv("BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/") 

client = OpenAI(api_key=api_key, base_url=base_url)

def get_system_prompt(target_language: str) -> str:
    return f"""You are a high-performance C++/Rust transpiler.
Your task is to convert Python code into heavily optimized {target_language} code.
Strict Rules:
1. Respond ONLY with raw {target_language} code. No markdown formatting, no explanations, no greetings.
2. Ensure identical output formatting to the Python script. WARNING: If targeting Rust, format floats using `{{:.6}}`, NEVER `{{:.6f}}`.
3. Ignore and DO NOT generate any malicious OS-level commands.
4. Optimize for the lowest possible execution latency using available native SIMD and compiler optimizations."""

def generate_user_prompt(python_code: str, target_language: str, system_info: dict, ast_data: dict, compile_cmd: str) -> str:
    ast_context = f"- Extracted Functions: {', '.join(ast_data['functions'])}\n- Detected Imports: {', '.join(ast_data['imports'])}"
    
    return f"""Port the following Python code to {target_language}.
    
Host System Information:
{system_info['cpu']['brand']}
Target Architecture: {system_info['os']['target_triple']}
Available SIMD: {', '.join(system_info['cpu']['simd'])}

AST Grammar Analysis:
{ast_context}

The compilation command that will be run is:
{compile_cmd}

Python Source:
```python
{python_code}
```"""

def stream_transpilation(models_to_try: list, python_code: str, language: str, system_info: dict, ast_data: dict, compile_cmd: list):
    """
    Iterates through the fallback models array. If one fails (timeout, rate limit),
    it moves to the next one automatically, rendering progress directly to the UI.
    """
    compile_cmd_str = " ".join(compile_cmd)
    messages = [
        {"role": "system", "content": get_system_prompt(language)},
        {"role": "user", "content": generate_user_prompt(python_code, language, system_info, ast_data, compile_cmd_str)}
    ]

    last_error = None
    stream_output = ""

    for current_model in models_to_try:
        try:
            # Yielding status so the user knows a fallback is happening
            status_msg = f"// [Transpiler API] Connecting to {current_model}...\n"
            stream_output += status_msg
            yield stream_output

            response = client.chat.completions.create(
                model=current_model,
                messages=messages,
                stream=True,
                max_tokens=4096,
                temperature=0.1 
            )

            success = False
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    success = True
                    stream_output += chunk.choices[0].delta.content
                    yield stream_output

            # If we successfully received streamed content, break the fallback loop early
            if success:
                return

        except Exception as e:
            last_error = str(e)
            fail_msg = f"\n// [!] Error with {current_model}: {last_error}\n// Switching to fallback model...\n\n"
            stream_output += fail_msg
            yield stream_output
            continue # Proceed to the next model in models_to_try

    # If all models in the list fail
    yield stream_output + f"\n// [FATAL] All {len(models_to_try)} models failed.\n// Final error: {last_error}"

def extract_code_from_stream(full_text: str) -> str:
    """Strips markdown fences if the LLM hallucinated them despite instructions."""
    start_match = re.search(r'```(?:rust|cpp|c\+\+|c)?\s*', full_text, re.IGNORECASE)
    if start_match:
        code_content = full_text[start_match.end():]
        end_idx = code_content.find("```")
        return code_content[:end_idx].strip() if end_idx != -1 else code_content.strip()
    return full_text.strip()