"""
SUMMARY:
This script builds the interactive web interface for the LLM Transpiler using Gradio.
It wires together the AST analyzer, the build pipeline, and the LLM streaming client.
The UI allows users to paste Python code, select a target language (C++ or Rust) and an AI model,
transpile the code with real-time streaming, and independently execute both scripts.
It also includes a benchmarking function to extract execution times and calculate speedup.

BUG FIX INCORPORATED:
- Replaced `lambda` functions in the `.click()` event chains with standard named functions 
  (`notify_py_running` and `notify_native_running`). Gradio's queuing system uses 
  serialization (pickling) in the background, which often fails silently when trying 
  to queue anonymous `lambda` functions, causing the buttons to do nothing when clicked.
"""
# =================================================================================================
import gradio as gr
import re
from styles import CSS
from transpiler.system_info import retrieve_system_info
from transpiler.analyzer import analyze_python_code
from transpiler.builder import get_build_pipeline, run_python_isolated, compile_and_execute
from transpiler.llm_client import stream_transpilation, extract_code_from_stream

# Pre-fetch system info once at startup so we don't query OS/hardware on every run
SYSTEM_INFO = retrieve_system_info()

# Ensure these match the actual model names expected by your API provider (e.g., gemini-1.5-flash)
MODELS = ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.5-flash"]

def port_code(model: str, python_code: str, language: str):
    """
    Handles AST safety checking and LLM streaming for the code transpilation process.
    Dynamically builds a fallback list of up to 3 models.
    """
    # 1. AST Safety Check to prevent malicious code generation
    ast_data = analyze_python_code(python_code)
    if not ast_data["is_safe"]:
        if ast_data["error"]:
            yield f"// AST Parse Error: {ast_data['error']}"
        else:
            yield f"// SECURITY BLOCK: Malicious commands detected: {', '.join(ast_data['dangerous_calls'])}"
        return

    # 2. Setup build pipeline context to get the specific compile commands for prompt injection
    _, compile_cmd, _ = get_build_pipeline(language)

    # 3. Prepare fallback queue: Primary (user selected) -> followed by the rest in the MODELS list
    # This provides high resilience if the primary model is rate-limited or times out.
    models_to_try = [model] + [m for m in MODELS if m != model]

    # 4. Stream from LLM, yielding parsed chunks for Gradio to update the UI progressively
    final_stream = ""
    for chunk in stream_transpilation(models_to_try, python_code, language, SYSTEM_INFO, ast_data, compile_cmd):
        final_stream = chunk
        yield extract_code_from_stream(final_stream)

def compare_performance(py_output: str, target_output: str, language: str) -> str:
    """
    Extracts benchmark data from both execution outputs using regex and calculates 
    the speedup multiplier.
    """
    # Check for valid outputs before attempting math
    if not py_output or not target_output or "error" in target_output.lower():
        return "⚠️ Run both scripts successfully to view speedup ratio."

    # Search for execution time logs
    py_match = re.search(r"Execution Time:\s*([\d.]+)", py_output)
    target_match = re.search(r"Execution Time:\s*([\d.]+)", target_output)

    if py_match and target_match:
        py_time = float(py_match.group(1))
        target_time = float(target_match.group(1))

        # Safeguard against division by zero for extremely fast execution
        if target_time <= 0.000001:
            return f"### ⚡ Analysis\n* **Python:** {py_time:.6f}s\n* **{language}:** ~0.000s\n🚀 {language} executed too fast for timer resolution!"
        
        speedup = py_time / target_time
        return f"### ⚡ Analysis\n* **Python Time:** {py_time:.6f}s\n* **{language} Time:** {target_time:.6f}s\n### 🚀 **{language} is {speedup:.2f}X faster!**"
    
    return "Ensure both programs print 'Execution Time: [seconds]' to calculate speedup."

def update_ui(lang: str):
    """Dynamically updates UI labels and component states based on the selected target language."""
    # FIX: Hardcode the syntax highlighter to "cpp" since "rust" throws a Gradio validation error.
    return (
        gr.update(label=f"{lang} Code", language="cpp"), 
        gr.update(value=f"Port to {lang}"), 
        gr.update(value=f"Run {lang}")
    )

# Helper functions for UI loading states (fixes Gradio lambda serialization bug)
def notify_py_running():
    """Returns the loading string for the Python execution UI update."""
    return "⏳ Executing Python script... Please wait."

def notify_native_running():
    """Returns the loading string for the Native execution UI update."""
    return "⏳ Compiling and executing native code... Please wait (up to 15s)."


# ==========================================
# Gradio UI Layout and Wiring
# ==========================================
with gr.Blocks(css=CSS, theme=gr.themes.Monochrome(), title="LLM Transpiler") as ui:
    # Top Control Row
    with gr.Row():
        model_dropdown = gr.Dropdown(choices=MODELS, value=MODELS[0], label="AI Engine")
        lang_selector = gr.Radio(choices=["C++", "Rust"], value="C++", label="Target")
    
    # Code Editors Row
    with gr.Row():
        py_editor = gr.Code(label="Python (original)", language="python", lines=20)
        target_editor = gr.Code(label="C++ Code", language="cpp", lines=20)

    # Action Buttons Row
    with gr.Row(elem_classes=["controls"]):
        btn_run_py = gr.Button("Run Python", elem_classes=["run-btn", "py"])
        btn_convert = gr.Button("Port to C++", elem_classes=["convert-btn"])
        btn_run_target = gr.Button("Run C++", elem_classes=["run-btn", "cpp"])

    # Output Terminals Row
    with gr.Row():
        py_out = gr.TextArea(label="Python Result", lines=5, elem_classes=["py-out"])
        target_out = gr.TextArea(label="Transpiled Result", lines=5, elem_classes=["cpp-out"])

    # Performance Benchmark Display
    speedup_display = gr.Markdown("### ⚡ Performance Comparison\nRun both scripts to view ratio.", elem_id="speedup-box")

    # ==========================================
    # Event Bindings
    # ==========================================
    
    # Update formatting when language target changes
    lang_selector.change(fn=update_ui, inputs=[lang_selector], outputs=[target_editor, btn_convert, btn_run_target])
    
    # Trigger transpilation stream
    btn_convert.click(fn=port_code, inputs=[model_dropdown, py_editor, lang_selector], outputs=[target_editor], queue=True)
    
    # 1. Update UI to show Python is running, THEN execute, THEN compare
    # Fixed: Replaced lambda functions with named functions to prevent Gradio queue serialization failures
    btn_run_py.click(
        fn=notify_py_running, 
        outputs=[py_out]
    ).then(
        fn=run_python_isolated, 
        inputs=[py_editor], 
        outputs=[py_out]
    ).then(
        fn=compare_performance, 
        inputs=[py_out, target_out, lang_selector], 
        outputs=[speedup_display]
    )

    # 2. Update UI to show Native code is compiling/running, THEN execute, THEN compare
    # Fixed: Replaced lambda functions with named functions to prevent Gradio queue serialization failures
    btn_run_target.click(
        fn=notify_native_running, 
        outputs=[target_out]
    ).then(
        fn=compile_and_execute, 
        inputs=[target_editor, lang_selector], 
        outputs=[target_out]
    ).then(
        fn=compare_performance, 
        inputs=[py_out, target_out, lang_selector], 
        outputs=[speedup_display]
    )

if __name__ == "__main__":
    ui.queue().launch(inbrowser=True)