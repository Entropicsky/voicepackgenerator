import logging
import os

def _get_elevenlabs_rules(filepath: str) -> str | None:
    """Reads the ElevenLabs rules from a specified markdown file.

    Args:
        filepath: The absolute path to the markdown file.

    Returns:
        The extracted rules section as a string, or None if not found or error.
    """
    rules_section = None
    try:
        logging.debug(f"Reading ElevenLabs rules from: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            prompt_guidelines = f.read()
        
        # Define markers based on current scripthelp.md structure
        guidelines_start_marker = "### ElevenLabs Prompt-Writing Rules:"
        # Use end of file as implicit end marker for now, can be refined if needed
        # guidelines_end_marker = "### Example Agent Prompt:"
        
        start_index = prompt_guidelines.find(guidelines_start_marker)
        # end_index = prompt_guidelines.find(guidelines_end_marker)
        
        if start_index != -1:
            # Extract from start marker to the end of the file, removing the marker itself
            rules_section = prompt_guidelines[start_index + len(guidelines_start_marker):].strip()
            # Remove the Example Agent Prompt section if it exists right after
            example_marker = "### Example Agent Prompt:"
            example_index = rules_section.find(example_marker)
            if example_index != -1:
                rules_section = rules_section[:example_index].strip()
            
            logging.debug(f"Successfully extracted ElevenLabs rules (length: {len(rules_section)}). Start: {rules_section[:50]}...")
        else:
             logging.warning(f"Could not find start marker '{guidelines_start_marker}' in {filepath}. Cannot extract rules.")

    except FileNotFoundError:
        logging.error(f"ElevenLabs rules file not found at: {filepath}")
    except Exception as e:
        logging.exception(f"Error reading or processing ElevenLabs rules file {filepath}: {e}")
        
    return rules_section

# Example Usage (for testing or direct calls)
# if __name__ == '__main__':
#     script_dir = os.path.dirname(os.path.abspath(__file__))
#     rules_path = os.path.join(script_dir, 'prompts', 'scripthelp.md')
#     rules = _get_elevenlabs_rules(rules_path)
#     if rules:
#         print("--- RULES ---")
#         print(rules)
#     else:
#         print("--- FAILED TO GET RULES ---") 