"""
Script to add session_id parameter to all Asana MCP tool input schemas.

This makes session_id a valid parameter that Claude Code can pass to tools.
"""

import re
from pathlib import Path

def add_session_id_to_schema(file_path: Path) -> bool:
    """Add session_id field to all Pydantic BaseModel classes in a file"""
    content = file_path.read_text(encoding='utf-8')
    original_content = content

    # Pattern to find BaseModel class definitions
    # Matches: class SomeInput(BaseModel):
    class_pattern = r'(class \w+Input\(BaseModel\):)\n(\s+"""[^"]+""")\n'

    def add_session_field(match):
        class_def = match.group(1)
        docstring = match.group(2)

        # Check if session_id already exists
        if 'session_id' in match.group(0):
            return match.group(0)  # Already has it

        # Add session_id as optional first parameter
        return f'''{class_def}
{docstring}
    session_id: Optional[str] = Field(
        None,
        description="Session ID for authentication (required for Railway MCP)"
    )
'''

    # Apply the replacement
    content = re.sub(class_pattern, add_session_field, content)

    if content != original_content:
        file_path.write_text(content, encoding='utf-8')
        print(f"[OK] Updated: {file_path.name}")
        return True
    else:
        print(f"[SKIP] Skipped: {file_path.name} (no changes needed)")
        return False

def main():
    tools_dir = Path(__file__).parent / "src" / "tools"

    if not tools_dir.exists():
        print(f"❌ Tools directory not found: {tools_dir}")
        return

    print(f"Scanning {tools_dir} for tool definition files...")
    print()

    updated_files = []
    for file_path in tools_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        if add_session_id_to_schema(file_path):
            updated_files.append(file_path.name)

    print()
    print("="*60)
    if updated_files:
        print(f"[OK] Updated {len(updated_files)} file(s):")
        for name in updated_files:
            print(f"   - {name}")
        print()
        print("Next steps:")
        print("1. Review the changes: git diff")
        print("2. Test locally: python -m src.server_http")
        print("3. Deploy to Railway: git push")
    else:
        print("[OK] All schemas already have session_id parameter")

if __name__ == "__main__":
    main()
