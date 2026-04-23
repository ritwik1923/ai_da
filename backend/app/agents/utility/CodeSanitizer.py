import re

class CodeSanitizer:
    """Responsible solely for cleaning and formatting LLM-generated code."""
    
    @staticmethod
    def sanitize(raw_code: str) -> str:
        code = re.sub(r"```python\n?", "", raw_code)
        code = re.sub(r"```\n?", "", code)
        code = re.sub(r"^print\s*\(.*\)$", "", code, flags=re.MULTILINE)
        code = re.sub(r",\s*pd\.Grouper\([^)]*\)", "", code)
        code = re.sub(r"pd\.Grouper\([^)]*\)", "'Index'", code)
        lines = code.split('\n')
        cleaned_lines = [
            line for line in lines 
            if not (line.strip().startswith('import ') or line.strip().startswith('from '))
        ]
        
        code = '\n'.join(cleaned_lines)
        code = code.split("Note:")[0].split("This code")[0].split("In this example")[0].strip()
        return code