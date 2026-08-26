# """
# SUMMARY:
# This script acts as a lightweight static analysis tool for Python code. 
# It uses the built-in `ast` (Abstract Syntax Tree) module to parse a string of Python code 
# without actually executing it. The script traverses the AST to identify potentially 
# dangerous function calls (e.g., `eval`, `exec`, `os.system`), records all imported 
# modules, and extracts the names of all defined functions. It returns a dictionary 
# summarizing whether the code is deemed "safe" alongside the extracted metadata.
# """
# ============================================================================================
import ast

class SecurityVisitor(ast.NodeVisitor):
    """
    An AST visitor that traverses parsed Python code to extract metadata 
    (imports, function definitions) and flag potentially dangerous function calls.
    """
    def __init__(self):
        # Tracking lists for extracted information
        self.dangerous_calls = []
        self.functions = []
        self.imports = []
        
        # Sets of banned function/method names to look out for.
        # These typically relate to shell execution, file deletion, or arbitrary code execution.
        self.banned_attrs = {'system', 'popen', 'run', 'rmtree', 'remove', 'rmdir', 'call'}
        self.banned_names = {'exec', 'eval', 'open'}

    def visit_Import(self, node):
        """Extracts module names from standard 'import x, y' statements."""
        for alias in node.names:
            self.imports.append(alias.name)
        # Continue traversing down the tree in case there are nested nodes
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """Extracts the base module name from 'from x import y' statements."""
        # Note: node.module can be None for relative imports (e.g., 'from . import foo')
        self.imports.append(node.module)
        self.generic_visit(node)

    def visit_Call(self, node):
        """Analyzes all function calls to check against banned security lists."""
        # Handle method/attribute calls (e.g., os.system(), subprocess.run())
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in self.banned_attrs:
                self.dangerous_calls.append(node.func.attr)
        # Handle direct function calls (e.g., eval(), exec(), open())
        elif isinstance(node.func, ast.Name):
            if node.func.id in self.banned_names:
                self.dangerous_calls.append(node.func.id)
                
        # Call generic_visit to ensure we also inspect the arguments passed to these functions
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Records the names of all functions defined in the code."""
        self.functions.append(node.name)
        # Continue traversal to inspect the code inside the function's body
        self.generic_visit(node)

def analyze_python_code(code: str) -> dict:
    """Parses Python code into an AST to extract metadata and check for unsafe operations."""
    try:
        # Parse the raw source code string into an Abstract Syntax Tree (AST)
        tree = ast.parse(code)
        
        # Initialize our custom visitor and walk the AST
        visitor = SecurityVisitor()
        visitor.visit(tree)
        
        # If the dangerous_calls list is empty, consider the code "safe"
        is_safe = len(visitor.dangerous_calls) == 0
        
        # Return a structured dictionary of our findings
        return {
            "is_safe": is_safe,
            "dangerous_calls": visitor.dangerous_calls,
            "functions": visitor.functions,
            "imports": visitor.imports,
            "error": None
        }
    except SyntaxError as e:
        # Catch cases where the provided string is not valid Python syntax
        return {"is_safe": False, "error": f"Syntax Error during AST parsing: {str(e)}"}