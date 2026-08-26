# """
# SUMMARY:
# This script provides the execution engine for a code compilation and testing environment. 
# It defines the build pipelines (compiler commands and heavy optimization flags) for Rust 
# and C++, ensuring the resulting binaries are optimized for the host architecture. It includes 
# a utility to run Python code in an I/O-captured buffer, and a robust `compile_and_execute` 
# function that writes, compiles, and runs native code safely using subprocesses with timeouts 
# to prevent hanging on infinite loops.
# """
# ==============================================================================================

import os
import io
import sys
import traceback
import subprocess

def get_build_pipeline(lang: str):
    """
    Returns the target filename, the compilation command (with aggressive optimization flags), 
    and the execution command based on the selected language.
    """
    # Normalize language string to handle variants like "C++" vs "cpp"
    lang_clean = lang.lower().replace("+", "p")

    # Determine the executable name based on the operating system
    exe_name = "main.exe" if os.name == 'nt' else "./main"
    run_cmd = [exe_name]

    if "rust" in lang_clean:
        filename = "main.rs"
        # Rust compile command: heavily optimized for native CPU, maximum optimization level (3),
        # single codegen unit and fat LTO for maximum performance, and panics set to abort.
        compile_cmd = [
            "rustc", filename, "-C", "opt-level=3", "-C", "target-cpu=native",
            "-C", "codegen-units=1", "-C", "lto=fat", "-C", "panic=abort", "-o", exe_name
        ]
    elif "cpp" in lang_clean or "c++" in lang_clean:
        filename = "main.cpp"
        # C++ compile command: C++17 standard, -Ofast for aggressive optimizations, 
        # -march=native for host architecture tuning, Link-Time Optimization (-flto), 
        # and disabling debug assertions (-DNDEBUG).
        compile_cmd = [
            "g++", "-std=c++17", "-Ofast", "-march=native", "-flto", "-DNDEBUG", 
            filename, "-o", exe_name
        ]
    else:
        raise ValueError(f"Unsupported language: {lang}")
        
    return filename, compile_cmd, run_cmd

def run_python_isolated(code: str) -> str:
    """
    Executes Python code in a controlled IO buffer, capturing print statements 
    and standard output without writing to the actual console.
    """
    # FIX: Added "__name__": "__main__" so the if __name__ == "__main__" block executes
    globals_dict = {
        "__builtins__": __builtins__, 
        "io": io, 
        "sys": sys,
        "__name__": "__main__"
    }
    
    # Redirect standard output to a string buffer
    buffer = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buffer

    try:
        # Execute the code dynamically
        exec(code, globals_dict)
        return buffer.getvalue()
    except Exception:
        # Catch runtime errors and format the traceback for the user
        return f"Execution Error:\n{traceback.format_exc()}"
    finally:
        # Always restore the original standard output to avoid breaking the host app
        sys.stdout = old_stdout

def compile_and_execute(code: str, language: str) -> str:
    """
    Writes source code to disk, compiles it using the specified language's build pipeline, 
    and executes the resulting binary. Handles timeouts and compilation errors gracefully.
    """
    if not code.strip():
        return "Error: No code provided."

    filename, compile_cmd, run_cmd = get_build_pipeline(language)

    # Step 1: Write the generated source code to a file
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)
    except IOError as e:
        return f"File I/O Error: {str(e)}"

    # Step 2: Compile the code
    try:
        # Run compiler, capture output, and enforce a 15-second timeout
        comp_res = subprocess.run(compile_cmd, text=True, capture_output=True, timeout=15)
        if comp_res.returncode != 0:
            # Return compiler warnings/errors if the build failed
            return f"Compilation Error:\n{comp_res.stderr or comp_res.stdout}"
    except subprocess.TimeoutExpired:
        return "Compilation Error: Build timed out (15s)."
    
    # Step 3: Execute the compiled binary
    try:
        # Run binary, capture output, and enforce a 10-second timeout to prevent infinite loops
        run_res = subprocess.run(run_cmd, text=True, capture_output=True, timeout=10)
        output = run_res.stdout
        
        # Append standard error if the program crashed or wrote to stderr
        if run_res.stderr:
            output += f"\n[Stderr]:\n{run_res.stderr}"
            
        # Handle cases where the program failed but produced no output
        if run_res.returncode != 0 and not output:
            output = f"Execution failed (Exit Code {run_res.returncode})"
            
        return output
    except subprocess.TimeoutExpired:
        return "Runtime Error: Execution timed out (possible infinite loop)."