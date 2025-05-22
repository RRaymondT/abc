# This module will be responsible for parsing the codebase and extracting relevant information.
#
# Pluggable Parser System Concept:
# The idea is to have a flexible system for adding new parsers for different file types.
# This could be achieved using:
# 1. A base `Parser` class with an `abstractmethod` `parse(file_path)` and specific
#    parsers inheriting from it (e.g., `PythonParser`, `BpmnParser`).
# 2. A dispatcher dictionary mapping file extensions (or more complex type checks)
#    to specific parsing functions.
# The `parse_file` function currently acts as a simple dispatcher based on file extension.

import ast
import xml.etree.ElementTree as ET
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_python_file(file_path: str) -> dict | None:
    """
    Parses a Python file to extract imports, class definitions (with methods),
    and function definitions (with parameters and calls).

    Args:
        file_path: The path to the Python file.

    Returns:
        A dictionary containing parsed information, or None if parsing fails.
        Structure:
        {
            "file_path": str,
            "imports": list[str],
            "classes": [
                {
                    "name": str,
                    "base_classes": list[str],
                    "methods": [
                        {
                            "name": str,
                            "parameters": list[str],
                            "calls": list[str]
                        }
                    ]
                }
            ],
            "functions": [
                {
                    "name": str,
                    "parameters": list[str],
                    "calls": list[str]
                }
            ]
        }
    """
    logging.info(f"Attempting to parse Python file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=file_path)
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except SyntaxError as e:
        logging.error(f"Syntax error in {file_path}: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to parse Python file {file_path}: {e}")
        return None

    imports = []
    classes = []
    functions = []

    for node in ast.walk(tree):
        # Extract imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module if node.module else "." * node.level
            for alias in node.names:
                imports.append(f"{module_name}.{alias.name}")

        # Extract classes
        elif isinstance(node, ast.ClassDef):
            base_classes = [ast.unparse(b) for b in node.bases]
            class_methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef): # Method
                    method_params = [arg.arg for arg in item.args.args]
                    method_calls = []
                    for sub_item in ast.walk(item):
                        if isinstance(sub_item, ast.Call):
                            call_name = ast.unparse(sub_item.func)
                            method_calls.append(call_name)
                    method_decorators = [ast.unparse(dec).strip() for dec in item.decorator_list]
                    class_methods.append({
                        "name": item.name,
                        "parameters": method_params,
                        "calls": list(set(method_calls)),
                        "decorators": method_decorators
                    })
            
            class_decorators = [ast.unparse(dec).strip() for dec in node.decorator_list]
            classes.append({
                "name": node.name,
                "base_classes": base_classes,
                "methods": class_methods,
                "decorators": class_decorators
            })

        # Extract top-level functions
        elif isinstance(node, ast.FunctionDef) and isinstance(node.parent, ast.Module) if hasattr(node, 'parent') else \
             any(node == direct_child for direct_child in tree.body if isinstance(direct_child, ast.FunctionDef)): # Simplified check for direct child of module
            # This check for parent helps differentiate methods from top-level functions.
            # A more robust way is to ensure the FunctionDef node is directly in tree.body.
            is_top_level = False
            for direct_child in tree.body: # tree is the Module node
                if direct_child == node:
                    is_top_level = True
                    break
            if is_top_level:
                func_params = [arg.arg for arg in node.args.args]
                func_calls = []
                for sub_item in ast.walk(node):
                    if isinstance(sub_item, ast.Call):
                        call_name = ast.unparse(sub_item.func)
                        func_calls.append(call_name)
                
                function_decorators = [ast.unparse(dec).strip() for dec in node.decorator_list]
                functions.append({
                    "name": node.name,
                    "parameters": func_params,
                    "calls": list(set(func_calls)),
                    "decorators": function_decorators
                })
                
    logging.info(f"Successfully parsed Python file: {file_path}")
    return {
        "file_path": file_path,
        "imports": list(set(imports)),
        "classes": classes,
        "functions": functions
    }

def identify_camunda_bpmn(file_path: str) -> dict | None:
    """
    Parses a Camunda BPMN file to extract process, service task, and user task details.

    Args:
        file_path: The path to the BPMN (.bpmn or .xml) file.

    Returns:
        A dictionary containing parsed BPMN information, or None if parsing fails
        or it's not a recognizable BPMN file.
        Structure:
        {
            "file_path": str,
            "processes": [{"id": str, "name": str | None}],
            "service_tasks": [{
                "id": str, "name": str | None,
                "camunda_class": str | None,
                "camunda_delegateExpression": str | None,
                "camunda_expression": str | None
            }],
            "user_tasks": [{"id": str, "name": str | None}]
        }
    """
    logging.info(f"Attempting to parse BPMN file: {file_path}")
    try:
        # Define namespaces
        namespaces = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'camunda': 'http://camunda.org/schema/1.0/bpmn'
        }

        tree = ET.parse(file_path)
        root = tree.getroot()

        # Quick check if it's a BPMN file
        if not root.tag.endswith('definitions'): # Basic check, can be more specific
            logging.info(f"File {file_path} does not appear to be a BPMN definitions file (root tag: {root.tag}). Skipping.")
            return None

        processes = []
        for process_node in root.findall('.//bpmn:process', namespaces):
            processes.append({
                "id": process_node.get('id'),
                "name": process_node.get('name')
            })

        service_tasks = []
        for task_node in root.findall('.//bpmn:serviceTask', namespaces):
            service_tasks.append({
                "id": task_node.get('id'),
                "name": task_node.get('name'),
                "camunda_class": task_node.get(f"{{{namespaces['camunda']}}}class"),
                "camunda_delegateExpression": task_node.get(f"{{{namespaces['camunda']}}}delegateExpression"),
                "camunda_expression": task_node.get(f"{{{namespaces['camunda']}}}expression")
            })

        user_tasks = []
        for task_node in root.findall('.//bpmn:userTask', namespaces):
            user_tasks.append({
                "id": task_node.get('id'),
                "name": task_node.get('name')
            })
        
        # If no BPMN elements were found, it might not be a Camunda BPMN file
        if not processes and not service_tasks and not user_tasks:
            # Check if the root tag itself suggests it's BPMN, but no elements found
            if 'bpmn' in namespaces and root.tag == f"{{{namespaces['bpmn']}}}definitions":
                 logging.warning(f"File {file_path} seems to be a BPMN file but no processes, service tasks, or user tasks were found.")
            else:
                logging.info(f"No Camunda BPMN elements found in {file_path}. It might not be a Camunda BPMN diagram.")
            # Depending on strictness, you might return None here if you expect at least one element
            # For now, returning what was found (even if empty lists)

        logging.info(f"Successfully parsed BPMN file: {file_path}")
        return {
            "file_path": file_path,
            "processes": processes,
            "service_tasks": service_tasks,
            "user_tasks": user_tasks
        }
    except ET.ParseError as e:
        logging.error(f"XML parsing error in {file_path}: {e}")
        return None
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Failed to parse BPMN file {file_path}: {e}")
        return None

# Placeholder for C# parser
# def parse_csharp_file(file_path: str) -> dict | None:
#     """
#     Parses a C# file. (Future Implementation)
#     Will need to handle .cs files and extract information like namespaces,
#     classes, methods, properties, using statements, and potentially attribute annotations.
#     Libraries like Roslyn (via pythonnet) or a custom regex/text-based approach could be used.
#     """
#     logging.info(f"C# parser called for {file_path} (not implemented).")
#     return None

# Placeholder for Vue component parser
# def parse_vue_component(file_path: str) -> dict | None:
#     """
#     Parses a Vue component file (.vue). (Future Implementation)
#     Will need to separate <template>, <script>, and <style> sections.
#     The <script> section can be parsed like JavaScript/TypeScript.
#     The <template> section can be parsed for component usage and props.
#     Libraries or custom regex-based approaches would be needed.
#     """
#     logging.info(f"Vue component parser called for {file_path} (not implemented).")
#     return None


# --- C# Parser Implementation ---

def _get_block_content(content: str, start_index: int) -> tuple[str | None, int | None]:
    """
    Extracts the content of a C# block enclosed by braces {} and its end index.

    Args:
        content: The string content to search within.
        start_index: The index of the opening brace '{'.

    Returns:
        A tuple containing:
        - The block content (string, exclusive of the outermost braces).
        - The index of the matching closing brace in the original content.
        Returns (None, None) if a matching brace is not found or if start_index is invalid.
    """
    if start_index < 0 or start_index >= len(content) or content[start_index] != '{':
        logging.error(f"_get_block_content: Invalid start_index or character at start_index is not '{{'. Got index {start_index} for content snippet: '{content[max(0,start_index-10):start_index+10]}'")
        return None, None

    brace_level = 0
    block_start_content_index = start_index + 1
    
    for i in range(start_index, len(content)):
        if content[i] == '{':
            brace_level += 1
        elif content[i] == '}':
            brace_level -= 1
            if brace_level == 0:
                # Found the matching closing brace
                block_end_content_index = i
                return content[block_start_content_index:block_end_content_index].strip(), block_end_content_index
    
    logging.warning(f"_get_block_content: No matching closing brace found for opening brace at index {start_index}.")
    return None, None # No matching brace found

def _extract_attributes_from_buffer(buffer_of_lines: list[str]) -> list[str]:
    """
    Extracts C# attribute names from a buffer of lines.
    Example: "[Route("api/[controller]")]" -> "Route"
             "[ApiController, Authorize]" -> ["ApiController", "Authorize"]
    """
    attributes = []
    # Regex to find attribute declarations. Captures the attribute name.
    # Handles attributes like [AttributeName], [AttributeName(arguments)], [Namespace.AttributeName]
    # It simplifies argument parsing, focusing on the attribute name itself.
    # (?:\((?:[^""]|"[^"]*")*\))? matches optional parentheses with arguments, attempting to handle strings within arguments.
    attribute_regex = re.compile(r"\[\s*([\w\.]+)(?:\((?:[^()\"']|\"[^\"]*\"|'[^']*')*\))?\s*\]")
    
    for line in buffer_of_lines:
        # Find all attributes in the line. An attribute line can have multiple: [Attr1, Attr2(args)]
        # Need to handle cases like [Attr1, Attr2("value")]
        # A simpler first pass: iterate for each potential attribute.
        
        # To handle multiple attributes on one line like [Attr1, Attr2], we can split by comma inside the brackets
        # but this is complex. Let's assume the regex can find them if they are distinct [Attr1] [Attr2]
        # or if the regex is applied iteratively after finding an initial '['.
        # For now, this regex is good for individual attributes per line or simple ones.
        
        # A better approach for multiple attributes in one `[]` block (e.g. `[One, Two(3)]`)
        # is to first get the content within `[]`, then parse that.
        
        raw_attr_block_match = re.search(r"\[(.*?)\]", line)
        if raw_attr_block_match:
            content_inside_brackets = raw_attr_block_match.group(1)
            # Split by comma, but be careful of commas inside parentheses for arguments
            # This is a simplified split, might fail for complex argument lists with commas
            potential_attrs = content_inside_brackets.split(',')
            for pa in potential_attrs:
                # Now match the attribute name from each part
                match = re.match(r"\s*([\w\.]+)(?:\((?:[^()\"']|\"[^\"]*\"|'[^']*')*\))?", pa.strip())
                if match:
                    attributes.append(match.group(1).split('.')[-1]) # Get the last part of FQN for name
        
    return list(set(attributes)) # Return unique attributes


def parse_csharp_file(file_path: str) -> dict | None:
    """
    Parses a C# file to extract namespaces, usings, classes, interfaces,
    methods, and properties using regular expressions.

    Args:
        file_path: The path to the C# file.

    Returns:
        A dictionary containing parsed information, or None if parsing fails.
    """
    logging.info(f"Attempting to parse C# file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Failed to read C# file {file_path}: {e}")
        return None

    parsed_info = {
        "file_path": file_path,
        "usings": [],
        "namespaces": [], # Store as list of dicts: {"name": "Namespace.Name", "classes": [], "interfaces": []}
        "classes": [],    # For classes outside any explicit namespace
        "interfaces": []  # For interfaces outside any explicit namespace
    }

    # Preprocessing: Remove comments
    # Single-line comments
    content = re.sub(r"//.*", "", content)
    # Multi-line comments (non-greedy)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)

    # Top-Level Usings (those not inside a namespace block, or before any namespace block)
    # We'll capture all usings first, then assign them if parsing namespaces hierarchically.
    # For a flatter structure, all usings can be top-level.
    # Let's assume usings are generally at the top or inside namespaces.
    
    # This regex finds all using statements.
    # We'll refine to only add to global usings if they are outside any namespace block later.
    global_usings = []
    # A simple way to find usings at the top: iterate lines before first namespace/class
    
    # More robust: find all usings, then later filter by position if needed.
    all_usings_matches = re.finditer(r"^\s*using\s+([\w\.]+)\s*;", content, re.MULTILINE)
    for match in all_usings_matches:
        # For now, add all found usings to a general list.
        # If we parse namespaces recursively, we'd pass the content for that namespace
        # and find its specific usings.
        if match.group(1) not in parsed_info["usings"]:
             parsed_info["usings"].append(match.group(1))


    # Regex patterns (simplified for clarity, will need to be combined or used sequentially)
    # Basic attribute pattern part (can be more complex)
    # ATTRIBUTE_GROUP = r"(?P<attributes>(?:\[\s*[\w\.]+(?:\((?:[^""]|""[^""]*"")*\))?\s*\]\s*)*)"
    # Simplified attribute placeholder for now, use _extract_attributes_from_buffer
    
    # Namespace: namespace Name { ... }
    # Class: [Attributes] public static class Name<T> : Base, IInterface { ... }
    # Interface: [Attributes] public interface IName : IBaseInterface { ... }
    # Method: [Attributes] public static ReturnType MethodName<T>(params Type[] args) where T : constraint { ... } / ;
    # Property: [Attributes] public Type PropName { get; set; } / => expression;
    
    # TODO: Implement the main parsing loop
    # This will involve iterating through the content with re.finditer,
    # identifying namespaces, classes, interfaces.
    # For each, use _get_block_content to get their body.
    # Then, parse the body for inner elements (methods, properties for classes/interfaces;
    # classes/interfaces for namespaces).
    # _extract_attributes_from_buffer will be used with lines preceding each element.

    # Main parsing loop (simplified)
    # This is a very basic and limited implementation. A proper C# parser would need a more robust approach.
    # This example will only attempt to find top-level classes and interfaces (not nested yet)
    # and their direct methods/properties. Namespaces are identified but not deeply parsed for nested elements.

    # Regex to find top-level class or interface declarations
    # Does not handle generics in name, complex inheritance, or attributes on the same line well.
    # Group 1: Attributes (as a whole string, to be processed by _extract_attributes_from_buffer)
    # Group 2: "class" or "interface"
    # Group 3: Name
    # Group 4: Base types (optional)
    # This regex is a starting point and has known limitations.
    entity_regex = re.compile(
        r"^\s*(?P<attributes>(?:\[.*?\]\s*)*)"  # Capture attributes block
        r"(?:public|internal|private|protected)?\s*" # Optional access modifiers
        r"(?:abstract|static|sealed|partial)?\s*" # Optional class modifiers
        r"(class|interface)\s+"
        r"(?P<name>[\w]+(?:<[\w\s,<>]+>)?)"  # Name, with basic generic support <T> or <T, U>
        r"\s*(?::\s*(?P<bases>[\w\.,\s<>]+))?"  # Optional base types
        r"\s*\{", re.MULTILINE # Match opening brace
    )

    # Regex for methods (simplified)
    # Group 1: Attributes
    # Group 2: Return type (can be complex, e.g., Task<IActionResult>)
    # Group 3: Method Name
    # Group 4: Parameters string
    method_regex = re.compile(
        r"^\s*(?P<attributes>(?:\[.*?\]\s*)*)"
        r"(?:public|private|protected|internal)?\s*(?:async|static|virtual|override|sealed|abstract)?\s*" # Modifiers
        r"(?P<return_type>[\w\.<>\[\]\?]+(?:\s*<[\w\s,\.<>\[\]\?]+>)?)\s+" # Return type with basic generics
        r"(?P<name>[\w]+(?:<[\w\s,<>]+>)?)" # Method name with basic generics
        r"\s*\((?P<params>[^\)]*)\)\s*(?:{|=>|;)", # Parameters and start of body or expression or abstract
        re.MULTILINE
    )
    
    # Regex for properties (simplified)
    # Group 1: Attributes
    # Group 2: Type
    # Group 3: Name
    property_regex = re.compile(
        r"^\s*(?P<attributes>(?:\[.*?\]\s*)*)"
        r"(?:public|private|protected|internal)?\s*(?:static|virtual|override|sealed|abstract)?\s*" # Modifiers
        r"(?P<type>[\w\.<>\[\]\?]+(?:\s*<[\w\s,\.<>\[\]\?]+>)?)\s+" # Type with basic generics
        r"(?P<name>[\w]+)" # Name
        r"\s*\{", # Must have a body for get/set
        re.MULTILINE
    )


    # Placeholder for current namespace context for simplicity (top-level entities only for now)
    # A full implementation would track entering/exiting namespace blocks.
    current_namespace_name = None 

    # Find namespaces first
    # This is a simplified approach; a full parser would handle nested structures.
    # The current _get_block_content and regexes are not designed for full recursion.
    namespace_matches = list(re.finditer(r"^\s*namespace\s+([\w\.]+)\s*\{", content, re.MULTILINE))
    
    content_sections_to_parse = [] # list of (content_str, namespace_name_str_or_None)

    if namespace_matches:
        last_ns_end = 0
        for ns_match in namespace_matches:
            ns_name = ns_match.group(1)
            ns_start_index = ns_match.end(0) -1 # Index of '{'

            # Add content before this namespace (if any) as global
            if ns_match.start(0) > last_ns_end:
                content_sections_to_parse.append( (content[last_ns_end:ns_match.start(0)], None) )

            ns_block_content, ns_block_end_index = _get_block_content(content, ns_start_index)
            if ns_block_content is not None:
                parsed_info["namespaces"].append({
                    "name": ns_name, 
                    "classes": [], 
                    "interfaces": [],
                    # "usings": [] # TODO: Parse usings specific to this namespace block
                })
                content_sections_to_parse.append( (ns_block_content, ns_name) )
                last_ns_end = ns_block_end_index + 1
            else:
                logging.warning(f"Could not parse block for namespace {ns_name} in {file_path}")
                # Skip to after where this namespace was declared to avoid issues
                last_ns_end = ns_match.end(0) 

        # Add content after the last namespace (if any) as global
        if last_ns_end < len(content):
            content_sections_to_parse.append( (content[last_ns_end:], None) )
    else:
        # No namespaces, parse the whole file content as global
        content_sections_to_parse.append( (content, None) )


    for section_content, current_namespace_name_for_section in content_sections_to_parse:
        # Find classes and interfaces within this section
        for entity_match in entity_regex.finditer(section_content):
            attributes_str = entity_match.group("attributes")
            entity_type = entity_match.group(2) # "class" or "interface"
            name = entity_match.group("name")
            bases_str = entity_match.group("bases")
            
            # Extract attributes from the captured attribute string block
            # Split attributes_str by lines for _extract_attributes_from_buffer
            attr_lines = attributes_str.strip().splitlines() if attributes_str else []
            attributes = _extract_attributes_from_buffer(attr_lines)

            entity_data = {
                "name": name,
                "type": entity_type,
                "namespace": current_namespace_name_for_section,
                "attributes": attributes,
                "base_types_str": bases_str.strip() if bases_str else None,
                "methods": [],
                "properties": []
            }

            entity_block_start_index = entity_match.end(0) -1 # Index of '{'
            entity_body_content, _ = _get_block_content(section_content, entity_block_start_index)

            if entity_body_content:
                # Parse methods
                for method_match in method_regex.finditer(entity_body_content):
                    method_attr_str = method_match.group("attributes")
                    method_attr_lines = method_attr_str.strip().splitlines() if method_attr_str else []
                    method_attributes = _extract_attributes_from_buffer(method_attr_lines)
                    
                    entity_data["methods"].append({
                        "name": method_match.group("name"),
                        "return_type": method_match.group("return_type").strip(),
                        "parameters_str": method_match.group("params").strip(),
                        "attributes": method_attributes
                        # Modifiers can be parsed similarly if regex captures them
                    })

                # Parse properties
                for prop_match in property_regex.finditer(entity_body_content):
                    prop_attr_str = prop_match.group("attributes")
                    prop_attr_lines = prop_attr_str.strip().splitlines() if prop_attr_str else []
                    prop_attributes = _extract_attributes_from_buffer(prop_attr_lines)

                    entity_data["properties"].append({
                        "name": prop_match.group("name"),
                        "type": prop_match.group("type").strip(),
                        "attributes": prop_attributes
                        # Could also try to get get/set content or if it's an expression body
                    })
            
            if current_namespace_name_for_section:
                # Find the namespace dict and append this class/interface
                for ns_dict in parsed_info["namespaces"]:
                    if ns_dict["name"] == current_namespace_name_for_section:
                        if entity_type == "class":
                            ns_dict["classes"].append(entity_data)
                        else:
                            ns_dict["interfaces"].append(entity_data)
                        break
            else: # Global scope
                if entity_type == "class":
                    parsed_info["classes"].append(entity_data)
                else:
                    parsed_info["interfaces"].append(entity_data)

    # logging.warning(f"C# parsing for {file_path} is partially implemented.")
    return parsed_info


# --- End C# Parser Implementation ---


# --- Vue.js SFC Parser Implementation ---

def parse_vue_component(file_path: str) -> dict | None:
    """
    Parses a Vue.js Single File Component (.vue) to extract information
    from its <template>, <script>, and <style> sections using regex.

    Args:
        file_path: The path to the .vue file.

    Returns:
        A dictionary containing parsed information, or None if parsing fails.
    """
    logging.info(f"Attempting to parse Vue SFC file: {file_path}")

    parsed_info = {
        "file_path": file_path,
        "component_name": None,
        "script_lang": None,
        "props": [],
        "data_properties": [],
        "methods": [],
        "computed_properties": [],
        "imports": [],
        "template_components_used": [],
        "template_event_bindings": [],
        "style_lang": None,
    }

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        logging.error(f"Vue SFC file not found: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Failed to read Vue SFC file {file_path}: {e}")
        return None

    # Regex for major sections
    TEMPLATE_REGEX = re.compile(r"<template>(.*?)</template>", re.DOTALL | re.IGNORECASE)
    SCRIPT_REGEX = re.compile(r"<script(?:\s+lang=['\"](\w+)['\"])?>(.*?)</script>", re.DOTALL | re.IGNORECASE)
    # For style, we primarily care about the lang, content is less critical for current scope
    STYLE_REGEX = re.compile(r"<style(?:\s+lang=['\"](\w+)['\"])?.*?>", re.DOTALL | re.IGNORECASE) # Removed content group for style

    template_match = TEMPLATE_REGEX.search(content)
    script_match = SCRIPT_REGEX.search(content)
    style_match = STYLE_REGEX.search(content) # Search for style tag to get lang

    template_content = None
    if template_match:
        template_content = template_match.group(1).strip()

    script_content = None
    if script_match:
        parsed_info["script_lang"] = script_match.group(1) if script_match.group(1) else 'javascript' # Default to js
        script_content = script_match.group(2).strip()
    
    if style_match:
        parsed_info["style_lang"] = style_match.group(1) if style_match.group(1) else 'css' # Default to css

    # --- Parse <script> content ---
    if script_content:
        # Component Name
        NAME_REGEX = re.compile(r"export default\s*\{\s*name:\s*['\"]([^'\"`]+)['\"`]") # Allow backticks for name
        name_match = NAME_REGEX.search(script_content)
        if name_match:
            parsed_info["component_name"] = name_match.group(1)
        else:
            parsed_info["component_name"] = os.path.splitext(os.path.basename(file_path))[0]

        # Imports
        IMPORT_REGEX = re.compile(r"import\s+(?:[\w\{\}\s,\*]+|\*\s+as\s+\w+)\s+from\s+['\"]([^'\"`]+)['\"`]", re.MULTILINE)
        imports_found = IMPORT_REGEX.findall(script_content)
        parsed_info["imports"] = list(set(imports_found)) # Unique import sources

        # Props (Object Syntax)
        PROPS_OBJ_REGEX = re.compile(r"props:\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", re.DOTALL)
        props_obj_match = PROPS_OBJ_REGEX.search(script_content)
        if props_obj_match:
            props_content = props_obj_match.group(1)
            PROP_ITEM_REGEX = re.compile(r"^\s*(\w+)\s*:", re.MULTILINE) # Simpler regex for prop names
            parsed_info["props"].extend(PROP_ITEM_REGEX.findall(props_content))
        
        # Props (Array Syntax) - appends to any found by object syntax
        PROPS_ARRAY_REGEX = re.compile(r"props:\s*\[\s*([^\]]*)\s*\]", re.DOTALL)
        props_array_match = PROPS_ARRAY_REGEX.search(script_content)
        if props_array_match:
            props_array_content = props_array_match.group(1)
            # Filter out empty strings that may result from split
            parsed_props_from_array = [p.strip().strip("'\"`") for p in props_array_content.split(',') if p.strip()]
            parsed_info["props"].extend(parsed_props_from_array)
        
        parsed_info["props"] = list(set(parsed_info["props"])) # Ensure uniqueness if both syntaxes used or duplicates

        # Data Properties
        DATA_BLOCK_REGEX = re.compile(r"data\s*\(\s*\)\s*\{\s*return\s*\{(.*?)\}\s*\}", re.DOTALL)
        data_block_match = DATA_BLOCK_REGEX.search(script_content)
        if data_block_match:
            data_content = data_block_match.group(1)
            DATA_ITEM_REGEX = re.compile(r"^\s*(\w+)\s*:", re.MULTILINE)
            parsed_info["data_properties"] = DATA_ITEM_REGEX.findall(data_content)

        # Methods
        METHODS_BLOCK_REGEX = re.compile(r"methods:\s*\{(.*?)\}(?:\s*,\s*(?:computed|watch|created|mounted|[\w]+)\s*:|\s*\})", re.DOTALL)
        methods_block_match = METHODS_BLOCK_REGEX.search(script_content)
        if methods_block_match:
            methods_content = methods_block_match.group(1)
            METHOD_ITEM_REGEX = re.compile(r"^\s*(\w+)\s*\([^)]*\)\s*\{", re.MULTILINE)
            parsed_info["methods"] = METHOD_ITEM_REGEX.findall(methods_content)

        # Computed Properties
        COMPUTED_BLOCK_REGEX = re.compile(r"computed:\s*\{(.*?)\}(?:\s*,\s*(?:watch|created|mounted|[\w]+)\s*:|\s*\})", re.DOTALL)
        computed_block_match = COMPUTED_BLOCK_REGEX.search(script_content)
        if computed_block_match:
            computed_content = computed_block_match.group(1)
            # Using same regex as methods, as structure is similar (name() { ... })
            COMPUTED_ITEM_REGEX = re.compile(r"^\s*(\w+)\s*\([^)]*\)\s*\{", re.MULTILINE)
            parsed_info["computed_properties"] = COMPUTED_ITEM_REGEX.findall(computed_content)

    # --- Parse <template> content ---
    if template_content:
        # Component Usage (PascalCase or kebab-case)
        # Adjusted to capture either group if one matches, ensuring simple tags like <div> are not captured
        COMPONENT_TAG_REGEX = re.compile(r"<([A-Z][\w\-]*[\w])|<([\w]+(?:-[\w]+)+)")
        component_matches = COMPONENT_TAG_REGEX.finditer(template_content)
        components_found = set()
        for match in component_matches:
            if match.group(1): # PascalCase component
                components_found.add(match.group(1))
            elif match.group(2): # kebab-case component
                components_found.add(match.group(2))
        parsed_info["template_components_used"] = list(components_found)

        # Event Bindings
        EVENT_BINDING_REGEX = re.compile(r"(?:v-on:|@)([\w\-.:]+)\s*=\s*['\"]([^'\"`]+)['\"`]") # Allow modifiers in event name e.g. @click.prevent
        event_matches = EVENT_BINDING_REGEX.finditer(template_content)
        for match in event_matches:
            parsed_info["template_event_bindings"].append({
                "event": match.group(1),
                "handler": match.group(2)
            })
            
    return parsed_info

# --- End Vue.js SFC Parser Implementation ---


def parse_file(file_path: str) -> dict | None:
    """
    Dispatches the file to the appropriate parser based on its extension.

    Args:
        file_path: The path to the file to parse.

    Returns:
        The parsed data as a dictionary, or None if no suitable parser is found
        or an error occurs.
    """
    if not os.path.exists(file_path):
        logging.error(f"File not found for parsing: {file_path}")
        return None
        
    _, extension = os.path.splitext(file_path)
    extension = extension.lower()

    logging.info(f"Dispatching parser for file: {file_path} (extension: {extension})")

    if extension == '.py':
        return parse_python_file(file_path)
    elif extension == '.bpmn' or extension == '.xml':
        # Attempt to parse as BPMN. identify_camunda_bpmn should handle non-BPMN XML gracefully.
        return identify_camunda_bpmn(file_path)
    elif extension == '.cs':
        return parse_csharp_file(file_path) 
    elif extension == '.vue':
        return parse_vue_component(file_path) 
    else:
        logging.info(f"No parser available for file extension: {extension} ({file_path})")
        return None


if __name__ == '__main__':
    import json # For C# test output
    # Create dummy files for testing
    DUMMY_FILES_DIR = "dummy_parser_test_files"
    if not os.path.exists(DUMMY_FILES_DIR):
        os.makedirs(DUMMY_FILES_DIR)

    # Dummy Python file
    dummy_py_file = os.path.join(DUMMY_FILES_DIR, "sample_script.py")
    with open(dummy_py_file, "w") as f:
        f.write("""
import os
import sys
from collections import Counter

@classmethod
@another_decorator(arg=1)
class MyDecoratedClass(object):
    def __init__(self, name):
        self.name = name
        self.helper()

    @staticmethod
    @some_method_decorator
    def helper(self): # Note: @staticmethod means 'self' is not special, but parser captures it
        print(f"Helper method called")
        local_call()

    def another_method(self, x, y):
        return x + y

@global_decorator
def top_level_function(param1):
    print(f"Top level function called with {param1}")
    res = MyDecoratedClass(param1).another_method(1,2) # Assuming MyDecoratedClass can be instantiated like this
    return res

def local_call():
    print("Local call executed")

if __name__ == "__main__":
    mc = MyDecoratedClass("test_instance")
    top_level_function("test_param")
""")

    # Dummy BPMN file
    dummy_bpmn_file = os.path.join(DUMMY_FILES_DIR, "sample_process.bpmn")
    with open(dummy_bpmn_file, "w") as f:
        f.write("""<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                  id="Definitions_1"
                  targetNamespace="http://bpmn.io/schema/bpmn">
  <bpmn:process id="Process_Order" name="Order Fulfillment Process" isExecutable="true">
    <bpmn:startEvent id="StartEvent_1" name="Order Received"/>
    <bpmn:sequenceFlow id="SequenceFlow_1" sourceRef="StartEvent_1" targetRef="Task_ProcessPayment"/>
    <bpmn:serviceTask id="Task_ProcessPayment" name="Process Payment" camunda:class="com.example.ProcessPaymentDelegate">
      <bpmn:incoming>SequenceFlow_1</bpmn:incoming>
      <bpmn:outgoing>SequenceFlow_2</bpmn:outgoing>
    </bpmn:serviceTask>
    <bpmn:sequenceFlow id="SequenceFlow_2" sourceRef="Task_ProcessPayment" targetRef="Task_ShipGoods"/>
    <bpmn:userTask id="Task_ShipGoods" name="Ship Goods">
      <bpmn:incoming>SequenceFlow_2</bpmn:incoming>
      <bpmn:outgoing>SequenceFlow_3</bpmn:outgoing>
    </bpmn:userTask>
    <bpmn:sequenceFlow id="SequenceFlow_3" sourceRef="Task_ShipGoods" targetRef="EndEvent_1"/>
    <bpmn:endEvent id="EndEvent_1" name="Order Completed"/>
  </bpmn:process>
</bpmn:definitions>
""")
    
    # Dummy non-BPMN XML file
    dummy_xml_file = os.path.join(DUMMY_FILES_DIR, "not_a_bpmn.xml")
    with open(dummy_xml_file, "w") as f:
        f.write("<root><item>Some XML data</item></root>")

    print(f"\n--- Testing Python Parser for {dummy_py_file} ---")
    parsed_py = parse_file(dummy_py_file)
    if parsed_py:
        print("Imports:", parsed_py.get("imports"))
        print("Classes:")
        for cls in parsed_py.get("classes", []):
            print(f"  - {cls.get('name')}({', '.join(cls.get('base_classes',[]))}), Decorators: {cls.get('decorators')}")
            for mth in cls.get("methods", []):
                print(f"    - Method: {mth.get('name')}({', '.join(mth.get('parameters',[]))}), Decorators: {mth.get('decorators')}, Calls: {mth.get('calls')}")
        print("Functions:")
        for func in parsed_py.get("functions", []):
            print(f"  - {func.get('name')}({', '.join(func.get('parameters',[]))}), Decorators: {func.get('decorators')}, Calls: {func.get('calls')}")
    else:
        print(f"Python parsing failed for {dummy_py_file} or returned None.")

    print(f"\n--- Testing BPMN Parser for {dummy_bpmn_file} ---")
    parsed_bpmn = parse_file(dummy_bpmn_file)
    if parsed_bpmn:
        print("Processes:", parsed_bpmn.get("processes"))
        print("Service Tasks:", parsed_bpmn.get("service_tasks"))
        print("User Tasks:", parsed_bpmn.get("user_tasks"))
    else:
        print(f"BPMN parsing failed for {dummy_bpmn_file} or returned None.")

    print(f"\n--- Testing BPMN Parser for non-BPMN XML {dummy_xml_file} ---")
    parsed_non_bpmn_xml = parse_file(dummy_xml_file)
    if parsed_non_bpmn_xml:
        print("Result (should be minimal or indicate non-BPMN):", parsed_non_bpmn_xml)
    else:
        print(f"Parsing correctly returned None or error for {dummy_xml_file} as it's not a BPMN file.")

    # Test non-existent file
    print(f"\n--- Testing non-existent file ---")
    non_existent_file = "non_existent_file.py"
    parsed_non_existent = parse_file(non_existent_file)
    if parsed_non_existent is None:
        print(f"Correctly handled non-existent file: {non_existent_file}")


    # --- C# Parser Test ---
    EXAMPLE_CSHARP_CODE = """
// Top-level comment
using System;
using System.Collections.Generic; // Another using

/* Multi-line
   comment here */
namespace MyWebApp.Models // Namespace declaration
{
    // Using inside namespace
    using System.ComponentModel.DataAnnotations;

    [Serializable]
    [Obsolete("This class is outdated.")]
    public class Product : BaseEntity, IAuditable<string>
    {
        public int ProductId { get; set; } // Auto-property

        [Required(ErrorMessage = "Name is required")]
        [StringLength(100)]
        public string Name { get; set; }

        private decimal _price;
        public decimal Price 
        { 
            get { return _price; } 
            set { _price = value > 0 ? value : 0; } // Basic logic in property
        }
        
        // Constructor
        public Product(int id, string name)
        {
            ProductId = id;
            Name = name;
            // Test comment removal inside method
        }

        /// <summary>
        /// Gets the product description.
        /// </summary>
        /// <returns>The product description.</returns>
        [HttpGet("details/{id}")]
        public string GetDescription(string Suffix)
        {
            return $"Product: {Name} - {Suffix}";
        }
    }

    public interface IAuditable<TUser>
    {
        DateTime CreatedAt { get; set; }
        TUser CreatedBy { get. set; } // Intentional space in get; for regex robustness test
    }
}

// Class outside namespace
public class Utility
{
    public static void HelperMethod() { /* ... */ }
}
"""
    dummy_cs_file = os.path.join(DUMMY_FILES_DIR, "sample_csharp.cs")
    with open(dummy_cs_file, "w", encoding='utf-8') as f:
        f.write(EXAMPLE_CSHARP_CODE)

    print(f"\n--- Testing C# Parser for {dummy_cs_file} ---")
    parsed_csharp = parse_file(dummy_cs_file) 
    if parsed_csharp:
        print(json.dumps(parsed_csharp, indent=2))
    else:
        print(f"C# parsing failed for {dummy_cs_file} or returned None.")

    # --- Vue SFC Parser Test ---
    EXAMPLE_VUE_CODE = """
<template>
  <div>
    <h1>{{ greeting }}</h1>
    <MyComponent :prop-value="dataValue" @custom-event="handleEvent" />
    <another-component @another-event="anotherHandler"></another-component>
    <button @click.prevent="submitForm">Submit</button>
  </div>
</template>

<script lang="ts">
import Helper from './utils/helper';
import { defineComponent, ref } from 'vue'; // Example of named imports

export default {
  name: 'MyVueComponent',
  components: {
    // MyComponent, anotherComponent would be registered here usually
  },
  props: {
    initialCounter: Number,
    message: String,
    config: {
      type: Object,
      default: () => ({})
    }
  },
  // props: ['initialCounter', 'message'], // Alternative array syntax
  data() {
    return {
      greeting: 'Hello, Vue!',
      dataValue: 100,
      internalCounter: this.initialCounter || 0
    };
  },
  methods: {
    handleEvent(payload) {
      console.log('Event handled:', payload);
      this.internalCounter++;
    },
    submitForm() {
      Helper.submit(this.dataValue);
    },
    anotherHandler() {
        // another handler
    }
  },
  computed: {
    displayMessage() {
      return this.message ? this.message.toUpperCase() : '';
    },
    doubledCounter() {
        return this.internalCounter * 2;
    }
  },
  mounted() {
    console.log('Component mounted');
  }
};
</script>

<style lang="scss" scoped>
  $primary-color: #42b983;
  h1 {
    color: $primary-color;
    font-weight: bold;
  }
</style>
"""
    dummy_vue_file = os.path.join(DUMMY_FILES_DIR, "SampleVueComponent.vue")
    with open(dummy_vue_file, "w", encoding='utf-8') as f:
        f.write(EXAMPLE_VUE_CODE)

    print(f"\n--- Testing Vue SFC Parser for {dummy_vue_file} ---")
    parsed_vue = parse_file(dummy_vue_file) # Use parse_file to test dispatcher
    if parsed_vue:
        print(json.dumps(parsed_vue, indent=2))
    else:
        print(f"Vue SFC parsing failed for {dummy_vue_file} or returned None.")


    # Clean up dummy files (optional)
    # import shutil
    # shutil.rmtree(DUMMY_FILES_DIR)
    # print(f"\nCleaned up dummy files in {DUMMY_FILES_DIR}")
