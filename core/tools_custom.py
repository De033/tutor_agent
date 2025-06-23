import os
import json
from typing import Dict, Any, List
from pydantic import Field

from camel.toolkits import FunctionTool, BaseToolkit

KNOWLEDGE_BASE_DIR = "knowledge_bases"

def save_knowledge_base(
    topic: str = Field(..., description="The main topic of the knowledge base, which will be used as the filename."),
    concepts: Dict[str, Any] = Field(..., description="A dictionary of Pydantic 'Concept' models.")
) -> str:
    """
    Saves a complete knowledge base to a JSON file. If a file for the
    topic already exists, the new concepts will be merged into it.
    """
    os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
    filename = "".join(c for c in topic if c.isalnum() or c in (' ', '_')).rstrip()
    filepath = os.path.join(KNOWLEDGE_BASE_DIR, f"{filename}.json")

    # The 'concepts' object is a dict of Pydantic models, so we need to dump it to a dict
    # before processing.
    new_concepts_dict = {name: data.model_dump() for name, data in concepts.items()}

    # Check if the file already exists to merge data
    existing_concepts = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                # Handle both formats: {"concepts": {...}} and legacy {...}
                existing_data = json.load(f)
                if isinstance(existing_data, dict) and "concepts" in existing_data:
                    existing_concepts = existing_data["concepts"]
                elif isinstance(existing_data, dict): # Legacy format
                    existing_concepts = existing_data
            except (json.JSONDecodeError, AttributeError):
                # If file is empty or corrupt, we'll just overwrite it.
                pass
    
    # Merge new concepts into existing ones. New concepts will overwrite old ones if names clash.
    existing_concepts.update(new_concepts_dict)

    # Always save in the new, consistent format
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({"concepts": existing_concepts}, f, ensure_ascii=False, indent=4)
    
    return f"Knowledge base '{topic}' was successfully saved/updated to {filepath}."

def add_concept_to_kb(
    topic: str = Field(..., description="The main topic of the knowledge base, which corresponds to the filename (e.g., 'dsa', '复变函数')."),
    concept_name: str = Field(..., description="The name of the new sub-topic or concept to be added."),
    definition: str = Field(..., description="A clear and concise definition of the new concept."),
    example: str = Field(..., description="A simple and illustrative example of the new concept."),
    socratic_prompts: List[str] = Field(..., min_length=2, description="A list of at least two Socratic questions to guide the user's thinking about the concept."),
    difficulty: int = Field(..., ge=1, le=5, description="The difficulty of the concept, rated from 1 (easiest) to 5 (hardest).")
) -> str:
    """
    Adds a new concept to an existing knowledge base JSON file.
    If the file does not exist, it will be created.
    """
    os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
    filename = "".join(c for c in topic if c.isalnum() or c in (' ', '_')).rstrip()
    filepath = os.path.join(KNOWLEDGE_BASE_DIR, f"{filename}.json")

    concepts_data = {}
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                # Handle both formats: {"concepts": {...}} and legacy {...}
                existing_data = json.load(f)
                if isinstance(existing_data, dict) and "concepts" in existing_data:
                    concepts_data = existing_data["concepts"]
                elif isinstance(existing_data, dict): # Legacy format
                    concepts_data = existing_data
            except (json.JSONDecodeError, AttributeError):
                # If the file is empty or corrupted, start fresh
                concepts_data = {}

    # Create the new concept structure
    new_concept = {
        "definition": definition,
        "example": example,
        "socratic_prompts": socratic_prompts,
        "difficulty": difficulty,
    }

    # Add or update the concept in the knowledge base
    concepts_data[concept_name] = new_concept

    # Write the updated data back to the file in the consistent format
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({"concepts": concepts_data}, f, ensure_ascii=False, indent=4)
        
    return f"Successfully added concept '{concept_name}' to knowledge base '{topic}'."

def save_knowledge_base_from_concepts(
    topic: str,
    concepts: dict,
    KNOWLEDGE_BASE_DIR: str = KNOWLEDGE_BASE_DIR
) -> str:
    """
    Saves a complete knowledge base to a JSON file in the specified directory.
    This is typically used when creating a new KB from scratch.
    """
    os.makedirs(KNOWLEDGE_BASE_DIR, exist_ok=True)
    # Sanitize the topic to create a valid filename
    filename = "".join(c for c in topic if c.isalnum() or c in (' ', '_')).rstrip()
    filepath = os.path.join(KNOWLEDGE_BASE_DIR, f"{filename}.json")

    # The 'concepts' object is a Pydantic model, so we need to dump it to a dict
    # before writing to JSON.
    concepts_dict = {name: data.model_dump() for name, data in concepts.items()}

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump({"concepts": concepts_dict}, f, ensure_ascii=False, indent=4)
    
    return f"Knowledge base '{topic}' saved successfully to {filepath}."

class CustomToolkit(BaseToolkit):
    """A toolkit that includes custom functions for the tutor agent."""
    # ... existing code ... 