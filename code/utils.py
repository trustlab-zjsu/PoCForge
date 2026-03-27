import re
import logging

logger = logging.getLogger(__name__)

def strip_solidity_comments(source_code: str) -> str:
    """
    Remove single-line, multi-line (NatSpec) comments, and excessive whitespace
    from Solidity source code to reduce LLM context window pressure.
    """
    logger.debug("Stripping comments and whitespace from source code")
    
    # 1. Remove multi-line comments /* ... */
    # Non-greedy match across newlines
    source_code = re.compile(r'/\*.*?\*/', re.DOTALL).sub('', source_code)
    
    # 2. Remove single-line comments // ...
    # But preserve URLs usually found in imports or spdx
    lines = []
    for line in source_code.splitlines():
        # Keep SPDX identifier
        if line.strip().startswith("// SPDX-License-Identifier"):
            lines.append(line.strip())
            continue
            
        # Remove anything after // unless it looks like a URL
        if '//' in line and not re.search(r'https?://', line):
            line = line.split('//')[0]
            
        line = line.strip()
        if line:  # Skip empty lines
            lines.append(line)
            
    return '\n'.join(lines)


def get_contract_snippet(source_code: str, target_contract: str) -> str:
    """
    Experimental: Extract only a specific contract module from a large multi-file
    bundle if the specific target_contract name is known.
    """
    # Simply stripping comments is often enough to halve the context.
    # Advanced AST extraction could go here in the future.
    return strip_solidity_comments(source_code)
