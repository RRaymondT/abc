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
import re # Added for C# and Vue parsing

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_python_file(file_path: str) -> dict | None:
    """
    Parses a Python file to extract imports, class definitions (with methods & decorators),
    and function definitions (with parameters, calls & decorators).
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
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module if node.module else "." * node.level
            for alias in node.names:
                imports.append(f"{module_name}.{alias.name}")
        elif isinstance(node, ast.ClassDef):
            base_classes = [ast.unparse(b) for b in node.bases]
            class_decorators = [ast.unparse(dec).strip() for dec in node.decorator_list]
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
                    
                    # Data flow analysis for methods
                    variable_origins = {}
                    data_flow_links = []
                    for stmt in item.body: # item is ast.FunctionDef (method)
                        current_call_node_for_args = None
                        if isinstance(stmt, ast.Assign):
                            if isinstance(stmt.value, ast.Call):
                                call_node = stmt.value
                                called_func_name_str = ast.unparse(call_node.func).strip()
                                for target in stmt.targets:
                                    if isinstance(target, ast.Name):
                                        var_name = target.id
                                        variable_origins[var_name] = {'source_func_name': called_func_name_str, 'source_call_node': call_node}
                                current_call_node_for_args = call_node # Check args of this call too
                        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                            current_call_node_for_args = stmt.value

                        if current_call_node_for_args:
                            consuming_func_name_str = ast.unparse(current_call_node_for_args.func).strip()
                            for idx, arg_node in enumerate(current_call_node_for_args.args):
                                if isinstance(arg_node, ast.Name):
                                    passed_var_name = arg_node.id
                                    if passed_var_name in variable_origins:
                                        origin_info = variable_origins[passed_var_name]
                                        data_flow_links.append({
                                            "source_function": origin_info['source_func_name'],
                                            "intermediate_variable": passed_var_name,
                                            "target_function": consuming_func_name_str,
                                            "arg_index": idx
                                        })
                            for kw_arg_node in current_call_node_for_args.keywords:
                                 if isinstance(kw_arg_node.value, ast.Name):
                                    passed_var_name = kw_arg_node.value.id
                                    if passed_var_name in variable_origins:
                                        origin_info = variable_origins[passed_var_name]
                                        data_flow_links.append({
                                            "source_function": origin_info['source_func_name'],
                                            "intermediate_variable": passed_var_name,
                                            "target_function": consuming_func_name_str,
                                            "keyword_arg_name": kw_arg_node.arg
                                        })
                    class_methods.append({
                        "name": item.name, "parameters": method_params,
                        "calls": list(set(method_calls)), "decorators": method_decorators,
                        "data_flow_links": data_flow_links
                    })
            classes.append({
                "name": node.name, "base_classes": base_classes,
                "methods": class_methods, "decorators": class_decorators
            })
        elif isinstance(node, ast.FunctionDef) and isinstance(node.parent, ast.Module) if hasattr(node, 'parent') else \
             any(node == direct_child for direct_child in tree.body if isinstance(direct_child, ast.FunctionDef)):
            is_top_level = any(direct_child == node for direct_child in tree.body)
            if is_top_level:
                func_params = [arg.arg for arg in node.args.args]
                func_calls = [] # This collects all calls, not just for data flow
                for sub_item in ast.walk(node): # sub_item here is any node in the function body
                    if isinstance(sub_item, ast.Call): # This is for the general 'calls' list
                        func_calls.append(ast.unparse(sub_item.func))
                
                function_decorators = [ast.unparse(dec).strip() for dec in node.decorator_list]
                
                # Data flow analysis for top-level functions
                variable_origins = {}
                data_flow_links = []
                for stmt in node.body: # node is ast.FunctionDef (top-level function)
                    current_call_node_for_args = None
                    if isinstance(stmt, ast.Assign):
                        if isinstance(stmt.value, ast.Call):
                            call_node = stmt.value
                            called_func_name_str = ast.unparse(call_node.func).strip()
                            for target in stmt.targets:
                                if isinstance(target, ast.Name):
                                    var_name = target.id
                                    variable_origins[var_name] = {'source_func_name': called_func_name_str, 'source_call_node': call_node}
                            current_call_node_for_args = call_node # Check args of this call too
                    elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                        current_call_node_for_args = stmt.value

                    if current_call_node_for_args:
                        consuming_func_name_str = ast.unparse(current_call_node_for_args.func).strip()
                        for idx, arg_node in enumerate(current_call_node_for_args.args):
                            if isinstance(arg_node, ast.Name):
                                passed_var_name = arg_node.id
                                if passed_var_name in variable_origins:
                                    origin_info = variable_origins[passed_var_name]
                                    data_flow_links.append({
                                        "source_function": origin_info['source_func_name'],
                                        "intermediate_variable": passed_var_name,
                                        "target_function": consuming_func_name_str,
                                        "arg_index": idx
                                    })
                        for kw_arg_node in current_call_node_for_args.keywords:
                             if isinstance(kw_arg_node.value, ast.Name):
                                passed_var_name = kw_arg_node.value.id
                                if passed_var_name in variable_origins:
                                    origin_info = variable_origins[passed_var_name]
                                    data_flow_links.append({
                                        "source_function": origin_info['source_func_name'],
                                        "intermediate_variable": passed_var_name,
                                        "target_function": consuming_func_name_str,
                                        "keyword_arg_name": kw_arg_node.arg
                                    })
                functions.append({
                    "name": node.name, "parameters": func_params,
                    "calls": list(set(func_calls)), "decorators": function_decorators,
                    "data_flow_links": data_flow_links
                })
                
    logging.info(f"Successfully parsed Python file: {file_path}")
    return {
        "file_path": file_path, "imports": list(set(imports)),
        "classes": classes, "functions": functions
    }

def identify_camunda_bpmn(file_path: str) -> dict | None:
    logging.info(f"Attempting to parse BPMN file: {file_path}")
    try:
        namespaces = {'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL', 'camunda': 'http://camunda.org/schema/1.0/bpmn'}
        tree = ET.parse(file_path)
        root = tree.getroot()
        if not root.tag.endswith('definitions'):
            logging.info(f"File {file_path} does not appear to be a BPMN definitions file. Skipping.")
            return None
        processes = [{"id": p.get('id'), "name": p.get('name')} for p in root.findall('.//bpmn:process', namespaces)]
        service_tasks = [{
            "id": t.get('id'), "name": t.get('name'),
            "camunda_class": t.get(f"{{{namespaces['camunda']}}}class"),
            "camunda_delegateExpression": t.get(f"{{{namespaces['camunda']}}}delegateExpression"),
            "camunda_expression": t.get(f"{{{namespaces['camunda']}}}expression")
        } for t in root.findall('.//bpmn:serviceTask', namespaces)]
        user_tasks = [{"id": t.get('id'), "name": t.get('name')} for t in root.findall('.//bpmn:userTask', namespaces)]
        if not processes and not service_tasks and not user_tasks:
            logging.info(f"No Camunda BPMN elements found in {file_path}.")
        return {"file_path": file_path, "processes": processes, "service_tasks": service_tasks, "user_tasks": user_tasks}
    except Exception as e:
        logging.error(f"Failed to parse BPMN file {file_path}: {e}")
        return None

# --- C# Parser Implementation ---

def _get_block_content(content: str, start_index: int) -> tuple[str | None, int | None]:
    if start_index < 0 or start_index >= len(content) or content[start_index] != '{':
        return None, None
    brace_level = 0
    block_start_content_index = start_index + 1
    for i in range(start_index, len(content)):
        if content[i] == '{': brace_level += 1
        elif content[i] == '}':
            brace_level -= 1
            if brace_level == 0: return content[block_start_content_index:i].strip(), i
    return None, None

def _extract_attributes_from_buffer(buffer_of_lines: list[str]) -> list[str]:
    attributes = set()
    for line in buffer_of_lines:
        raw_attr_block_match = re.search(r"\[(.*?)\]", line)
        if raw_attr_block_match:
            content_inside_brackets = raw_attr_block_match.group(1)
            potential_attrs = content_inside_brackets.split(',')
            for pa in potential_attrs:
                match = re.match(r"\s*([\w\.]+)(?:\((?:[^()\"']|\"[^\"]*\"|'[^']*')*\))?", pa.strip())
                if match: attributes.add(match.group(1).split('.')[-1])
    return list(attributes)

def _parse_ef_onmodelcreating_body(body_content: str) -> list:
    configs = []
    logging.debug(f"Parsing OnModelCreating body (length: {len(body_content)}).")
    # Split content into statements more carefully, considering {} blocks for lambdas
    statements = []
    current_pos = 0
    brace_depth = 0
    stmt_start = 0
    for i, char in enumerate(body_content):
        if char == '{': brace_depth += 1
        elif char == '}': brace_depth -= 1
        elif char == ';' and brace_depth == 0:
            statements.append(body_content[stmt_start:i+1].strip())
            stmt_start = i + 1
    if stmt_start < len(body_content): # Add remaining part if no trailing semicolon
        statements.append(body_content[stmt_start:].strip())
    
    current_entity_type = None
    for stmt_block in statements:
        entity_match = re.search(r"modelBuilder\.Entity<([\w\.]+)>\(?\w*\)?", stmt_block)
        if entity_match: current_entity_type = entity_match.group(1)
        if not current_entity_type: continue

        # HasKey
        haskey_match = re.search(r"\.HasKey\(\s*(?:[\w\.]+\s*=>\s*)?([\w\.\(\)\s,=>\{\}]+)\s*\)", stmt_block)
        if haskey_match:
            key_expr = haskey_match.group(1).strip()
            simple_keys = re.findall(r"e\.([\w]+)", key_expr)
            configs.append({"entity_configured": current_entity_type, "call_type": "HasKey", "details": {"key_expression": key_expr, "keys_found": simple_keys}})

        # Property
        prop_config_match = re.search(r"\.Property\(\s*\w+\s*=>\s*\w+\.([\w]+)\s*\)((?:\s*\.(?:IsRequired|HasMaxLength|HasColumnName|HasColumnType|IsConcurrencyToken)\s*(?:\([^)]*\))?)*)", stmt_block)
        if prop_config_match:
            prop_name, chained_calls = prop_config_match.groups()
            details = {"property_name": prop_name}
            if ".IsRequired()" in chained_calls: details["is_required"] = True
            max_len_match = re.search(r"\.HasMaxLength\(\s*(\d+)\s*\)", chained_calls)
            if max_len_match: details["max_length"] = int(max_len_match.group(1))
            col_name_match = re.search(r'\.HasColumnName\(\s*"([^"]+)"\s*\)', chained_calls)
            if col_name_match: details["column_name"] = col_name_match.group(1)
            configs.append({"entity_configured": current_entity_type, "call_type": "Property", "details": details})

        # Relationships (simplified)
        rel_hm_wo = re.search(r"\.HasMany(?:<([\w\.]+)>)?\s*\([^)]*\)\s*\.WithOne(?:<([\w\.]+)>)?\s*\((?:[^)]*=>\s*[\w\.]+)?\s*([\w\.]+)?\s*\)", stmt_block)
        if rel_hm_wo: configs.append({"entity_configured": current_entity_type, "call_type": "HasMany_WithOne", "details": {"many_arg": rel_hm_wo.group(1), "one_arg": rel_hm_wo.group(2), "nav_prop": rel_hm_wo.group(3)}})
        
        rel_ho_wm = re.search(r"\.HasOne(?:<([\w\.]+)>)?\s*\([^)]*\)\s*\.WithMany(?:<([\w\.]+)>)?\s*\((?:[^)]*=>\s*[\w\.]+)?\s*([\w\.]+)?\s*\)", stmt_block)
        if rel_ho_wm: configs.append({"entity_configured": current_entity_type, "call_type": "HasOne_WithMany", "details": {"one_arg": rel_ho_wm.group(1), "many_arg": rel_ho_wm.group(2), "nav_prop": rel_ho_wm.group(3)}})
        
        rel_ho_wo = re.search(r"\.HasOne(?:<([\w\.]+)>)?\((?:[^)]*=>\s*[\w\.]+)?\s*([\w\.]+)?\s*\)\s*\.WithOne(?:<([\w\.]+)>)?\((?:[^)]*=>\s*[\w\.]+)?\s*([\w\.]+)?\s*\)", stmt_block)
        if rel_ho_wo: configs.append({"entity_configured": current_entity_type, "call_type": "HasOne_WithOne", "details": {"one_arg1": rel_ho_wo.group(1), "nav_prop1": rel_ho_wo.group(2), "one_arg2": rel_ho_wo.group(3), "nav_prop2": rel_ho_wo.group(4)}})

        if not stmt_block.strip().endswith("."): current_entity_type = None # Heuristic to reset context
    if not configs: logging.info(f"No specific EF configurations extracted by parser in {current_entity_type or 'unknown context'}.")
    return configs

def parse_csharp_file(file_path: str) -> dict | None:
    logging.info(f"Attempting to parse C# file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
    except Exception as e: logging.error(f"Failed to read C# file {file_path}: {e}"); return None

    parsed_info = {"file_path": file_path, "usings": [], "namespaces": [], "classes": [], "interfaces": []}
    content = re.sub(r"//.*", "", content)
    content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
    parsed_info["usings"] = list(set(re.findall(r"^\s*using\s+([\w\.]+)\s*;", content, re.MULTILINE)))

    entity_regex = re.compile(r"^\s*(?P<attributes>(?:\[.*?\]\s*)*)(?:public|internal|private|protected)?\s*(?:abstract|static|sealed|partial)?\s*(class|interface)\s+(?P<name>[\w]+(?:<[\w\s,<>]+>)?)\s*(?::\s*(?P<bases>[\w\.,\s<>]+))?\s*\{", re.MULTILINE)
    method_regex = re.compile(r"^\s*(?P<attributes>(?:\[.*?\]\s*)*)(?:public|private|protected|internal)?\s*(?:async|static|virtual|override|sealed|abstract)?\s*(?P<return_type>[\w\.<>\[\]\?]+(?:\s*<[\w\s,\.<>\[\]\?]+>)?)\s+(?P<name>[\w]+(?:<[\w\s,<>]+>)?)\s*\((?P<params>[^\)]*)\)\s*(?:{|=>|;)", re.MULTILINE)
    property_regex = re.compile(r"^\s*(?P<attributes>(?:\[.*?\]\s*)*)(?:public|private|protected|internal)?\s*(?:static|virtual|override|sealed|abstract)?\s*(?P<type>[\w\.<>\[\]\?]+(?:\s*<[\w\s,\.<>\[\]\?]+>)?)\s+(?P<name>[\w]+)\s*\{", re.MULTILINE)
    DBSET_REGEX = re.compile(r"(?:public|internal)\s+(?:virtual\s+)?DbSet<([\w\.]+)>([\w]+)\s*\{\s*get;\s*set;\s*\}")

    namespace_matches = list(re.finditer(r"^\s*namespace\s+([\w\.]+)\s*\{", content, re.MULTILINE))
    content_sections = []
    last_ns_end = 0
    if namespace_matches:
        for ns_match in namespace_matches:
            if ns_match.start(0) > last_ns_end: content_sections.append((content[last_ns_end:ns_match.start(0)], None))
            ns_name = ns_match.group(1)
            ns_block_content, ns_block_end_idx = _get_block_content(content, ns_match.end(0) - 1)
            if ns_block_content is not None:
                parsed_info["namespaces"].append({"name": ns_name, "classes": [], "interfaces": []})
                content_sections.append((ns_block_content, ns_name))
                last_ns_end = ns_block_end_idx + 1
            else: last_ns_end = ns_match.end(0)
        if last_ns_end < len(content): content_sections.append((content[last_ns_end:], None))
    else: content_sections.append((content, None))

    for section_content, current_ns_name in content_sections:
        for entity_match in entity_regex.finditer(section_content):
            attr_lines = entity_match.group("attributes").strip().splitlines()
            entity_data = {
                "name": entity_match.group("name"), "type": entity_match.group(2),
                "namespace": current_ns_name, "attributes": _extract_attributes_from_buffer(attr_lines),
                "base_types_str": entity_match.group("bases").strip() if entity_match.group("bases") else None,
                "methods": [], "properties": [], "is_dbcontext": False, "db_sets": [], "ef_configurations": []
            }
            if entity_data["type"] == "class" and entity_data["base_types_str"] and "DbContext" in entity_data["base_types_str"]:
                entity_data["is_dbcontext"] = True
            
            entity_body_content, _ = _get_block_content(section_content, entity_match.end(0) - 1)
            if entity_body_content:
                for method_match in method_regex.finditer(entity_body_content):
                    m_attr_lines = method_match.group("attributes").strip().splitlines()
                    method_detail = {"name": method_match.group("name"), "return_type": method_match.group("return_type").strip(),
                                     "parameters_str": method_match.group("params").strip(), "attributes": _extract_attributes_from_buffer(m_attr_lines)}
                    entity_data["methods"].append(method_detail)
                    if entity_data["is_dbcontext"] and method_detail["name"] == "OnModelCreating" and "ModelBuilder" in method_detail["parameters_str"]:
                        # This is a simplified method body extraction for OnModelCreating
                        method_body_start_idx = entity_body_content.find('{', method_match.end() - len(entity_body_content) -1 ) # Relative search
                        if method_body_start_idx != -1:
                           omc_body, _ = _get_block_content(entity_body_content, method_body_start_idx)
                           if omc_body: entity_data["ef_configurations"] = _parse_ef_onmodelcreating_body(omc_body)
                
                # Property parsing logic
                # First, DbSets if it's a DbContext
                if entity_data["is_dbcontext"]:
                    for dbset_match in DBSET_REGEX.finditer(entity_body_content):
                        entity_data["db_sets"].append({"entity_name": dbset_match.group(1), "property_name": dbset_match.group(2)})
                
                # Then general properties (could be improved to avoid double-parsing if DbSet is also a general prop)
                # This simplified approach might list DbSets also as general properties if not careful,
                # but the specific `db_sets` list is primary for EF info.
                for prop_match in property_regex.finditer(entity_body_content):
                    # Avoid re-adding if it was already captured as a DbSet (by name comparison)
                    prop_name = prop_match.group("name")
                    if entity_data["is_dbcontext"] and any(ds["property_name"] == prop_name for ds in entity_data["db_sets"]):
                        continue # Skip if already captured as DbSet

                    p_attr_lines = prop_match.group("attributes").strip().splitlines()
                    entity_data["properties"].append({"name": prop_name, "type": prop_match.group("type").strip(), "attributes": _extract_attributes_from_buffer(p_attr_lines)})

            target_list = None
            if current_ns_name:
                for ns_dict in parsed_info["namespaces"]:
                    if ns_dict["name"] == current_ns_name:
                        target_list = ns_dict["classes"] if entity_data["type"] == "class" else ns_dict["interfaces"]
                        break
            else: target_list = parsed_info["classes"] if entity_data["type"] == "class" else parsed_info["interfaces"]
            if target_list is not None: target_list.append(entity_data)
    return parsed_info

# --- End C# Parser Implementation ---

# --- Vue.js SFC Parser Implementation ---
def parse_vue_component(file_path: str) -> dict | None:
    logging.info(f"Attempting to parse Vue SFC file: {file_path}")
    parsed_info = {"file_path": file_path, "component_name": None, "script_lang": None, "props": [], "data_properties": [], "methods": [], "computed_properties": [], "imports": [], "template_components_used": [], "template_event_bindings": [], "style_lang": None}
    try:
        with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
    except Exception as e: logging.error(f"Failed to read Vue SFC file {file_path}: {e}"); return None

    template_match = re.search(r"<template>(.*?)</template>", content, re.DOTALL | re.IGNORECASE)
    script_match = re.search(r"<script(?:\s+lang=['\"](\w+)['\"])?>(.*?)</script>", content, re.DOTALL | re.IGNORECASE)
    style_match = re.search(r"<style(?:\s+lang=['\"](\w+)['\"])?.*?>", content, re.DOTALL | re.IGNORECASE)
    
    template_content = template_match.group(1).strip() if template_match else None
    script_content = None
    if script_match:
        parsed_info["script_lang"] = script_match.group(1) or 'javascript'
        script_content = script_match.group(2).strip()
    if style_match: parsed_info["style_lang"] = style_match.group(1) or 'css'

    if script_content:
        name_match = re.search(r"export default\s*\{\s*name:\s*['\"]([^'\"`]+)['\"`]", script_content)
        parsed_info["component_name"] = name_match.group(1) if name_match else os.path.splitext(os.path.basename(file_path))[0]
        parsed_info["imports"] = list(set(re.findall(r"import\s+(?:[\w\{\}\s,\*]+|\*\s+as\s+\w+)\s+from\s+['\"]([^'\"`]+)['\"`]", script_content, re.MULTILINE)))
        
        props_obj_match = re.search(r"props:\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", script_content, re.DOTALL)
        if props_obj_match: parsed_info["props"].extend(re.findall(r"^\s*(\w+)\s*:", props_obj_match.group(1), re.MULTILINE))
        props_array_match = re.search(r"props:\s*\[\s*([^\]]*)\s*\]", script_content, re.DOTALL)
        if props_array_match: parsed_info["props"].extend([p.strip().strip("'\"`") for p in props_array_match.group(1).split(',') if p.strip()])
        parsed_info["props"] = list(set(parsed_info["props"]))

        data_block_match = re.search(r"data\s*\(\s*\)\s*\{\s*return\s*\{(.*?)\}\s*\}", script_content, re.DOTALL)
        if data_block_match: parsed_info["data_properties"] = re.findall(r"^\s*(\w+)\s*:", data_block_match.group(1), re.MULTILINE)
        
        methods_block_match = re.search(r"methods:\s*\{(.*?)\}(?:\s*,\s*(?:computed|watch|created|mounted|[\w]+)\s*:|\s*\})", script_content, re.DOTALL)
        if methods_block_match: parsed_info["methods"] = re.findall(r"^\s*(\w+)\s*\([^)]*\)\s*\{", methods_block_match.group(1), re.MULTILINE)
        
        computed_block_match = re.search(r"computed:\s*\{(.*?)\}(?:\s*,\s*(?:watch|created|mounted|[\w]+)\s*:|\s*\})", script_content, re.DOTALL)
        if computed_block_match: parsed_info["computed_properties"] = re.findall(r"^\s*(\w+)\s*\([^)]*\)\s*\{", computed_block_match.group(1), re.MULTILINE)

    if template_content:
        components_found = set()
        for match in re.finditer(r"<([A-Z][\w\-]*[\w])|<([\w]+(?:-[\w]+)+)", template_content):
            if match.group(1): components_found.add(match.group(1))
            elif match.group(2): components_found.add(match.group(2))
        parsed_info["template_components_used"] = list(components_found)
        for match in re.finditer(r"(?:v-on:|@)([\w\-.:]+)\s*=\s*['\"]([^'\"`]+)['\"`]", template_content):
            parsed_info["template_event_bindings"].append({"event": match.group(1), "handler": match.group(2)})
    return parsed_info
# --- End Vue.js SFC Parser Implementation ---

def parse_file(file_path: str) -> dict | None:
    if not os.path.exists(file_path): logging.error(f"File not found for parsing: {file_path}"); return None
    _, extension = os.path.splitext(file_path); extension = extension.lower()
    logging.info(f"Dispatching parser for file: {file_path} (extension: {extension})")
    if extension == '.py': return parse_python_file(file_path)
    elif extension == '.bpmn' or extension == '.xml': return identify_camunda_bpmn(file_path)
    elif extension == '.cs': return parse_csharp_file(file_path) 
    elif extension == '.vue': return parse_vue_component(file_path) 
    else: logging.info(f"No parser available for file extension: {extension} ({file_path})"); return None

if __name__ == '__main__':
    import json 
    DUMMY_FILES_DIR = "dummy_parser_test_files"
    if not os.path.exists(DUMMY_FILES_DIR): os.makedirs(DUMMY_FILES_DIR)

    # Python example (unchanged from previous, includes decorators)
    dummy_py_file = os.path.join(DUMMY_FILES_DIR, "sample_script.py")
    # ... (Python example code needs to be updated for data flow) ...
    PYTHON_CODE_EXAMPLE_FOR_DATAFLOW = """
import os

def source_function_for_flow():
    return "raw_data"

def process_data_for_flow(input_data, other_param=None):
    processed = input_data.upper()
    if other_param:
        print(f"Other param: {other_param}")
    return processed

def another_source():
    return "another_piece_of_data"

def final_sink(data1, data2):
    print(f"Sink received: {data1} and {data2}")

def data_flow_test():
    # Direct flow
    data_from_source = source_function_for_flow() 
    # 'data_from_source' (from 'source_function_for_flow') flows into 'process_data_for_flow' as 'input_data'
    result1 = process_data_for_flow(input_data=data_from_source, other_param=123) 
    
    # Second variable from a different source
    other_data = another_source()
    
    # 'result1' (from 'process_data_for_flow') flows into 'final_sink' as 'data1'
    # 'other_data' (from 'another_source') flows into 'final_sink' as 'data2'
    final_sink(result1, data2=other_data)

class MyClassWithFlow:
    def method_flow(self):
        m_data = self.source_method()
        self.sink_method(m_data)

    def source_method(self):
        return "method_data"
    
    def sink_method(self, data_param):
        print(data_param)

"""
    with open(dummy_py_file, "w") as f:
        f.write(PYTHON_CODE_EXAMPLE_FOR_DATAFLOW)

    # C# example with DbContext
    EXAMPLE_CSHARP_CODE = """
using System;
using Microsoft.EntityFrameworkCore;

namespace MyWebApp.Models
{
    public class Product { public int ProductId { get; set; } public string Name { get; set; } public Category Category { get; set; } public int CategoryId {get;set;} }
    public class Category { public int CategoryId { get; set; } public string CategoryName { get; set; } public List<Product> Products { get; set; } }

    public class MyDbContext : DbContext
    {
        public DbSet<Product> Products { get; set; }
        public DbSet<Category> Categories { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            base.OnModelCreating(modelBuilder); // Example of other call

            modelBuilder.Entity<Product>()
                .HasKey(p => p.ProductId); // Single key
            
            modelBuilder.Entity<Product>()
                .Property(p => p.Name)
                .IsRequired()
                .HasMaxLength(100);

            modelBuilder.Entity<Category>()
                .Property(c => c.CategoryName).HasColumnName("CategoryTitle");

            // Relationship: Category has many Products
            modelBuilder.Entity<Category>()
                .HasMany(c => c.Products)
                .WithOne(p => p.Category)
                .HasForeignKey(p => p.CategoryId);
        }
    }
}"""
    dummy_cs_file = os.path.join(DUMMY_FILES_DIR, "sample_csharp_ef.cs")
    with open(dummy_cs_file, "w", encoding='utf-8') as f: f.write(EXAMPLE_CSHARP_CODE)

    # Vue example (unchanged from previous)
    EXAMPLE_VUE_CODE = """
<template><div><MyComponent @event="handler"/></div></template>
<script lang="ts">
export default { name: 'TestVue', props: ['id'], methods: { handler() {} } }
</script>"""
    dummy_vue_file = os.path.join(DUMMY_FILES_DIR, "SampleVueComponent.vue")
    with open(dummy_vue_file, "w", encoding='utf-8') as f: f.write(EXAMPLE_VUE_CODE)
    
    print(f"\n--- Testing Python Parser for {dummy_py_file} (with Data Flow) ---")
    parsed_py = parse_file(dummy_py_file)
    if parsed_py:
        print(json.dumps(parsed_py, indent=2))
        # Specifically print data flow for data_flow_test
        for func_info in parsed_py.get('functions', []):
            if func_info.get('name') == 'data_flow_test':
                print("\nData Flow Links for 'data_flow_test':")
                print(json.dumps(func_info.get('data_flow_links', []), indent=2))
        for class_info in parsed_py.get('classes', []):
            if class_info.get('name') == 'MyClassWithFlow':
                 for method_info in class_info.get('methods', []):
                    if method_info.get('name') == 'method_flow':
                        print("\nData Flow Links for 'MyClassWithFlow.method_flow':")
                        print(json.dumps(method_info.get('data_flow_links', []), indent=2))

    else: print(f"Python parsing failed for {dummy_py_file}")

    print(f"\n--- Testing C# Parser for {dummy_cs_file} ---")
    parsed_csharp = parse_file(dummy_cs_file)
    if parsed_csharp: print(json.dumps(parsed_csharp, indent=2))
    else: print(f"C# parsing failed for {dummy_cs_file}")

    print(f"\n--- Testing Vue SFC Parser for {dummy_vue_file} ---")
    parsed_vue = parse_file(dummy_vue_file)
    if parsed_vue: print(json.dumps(parsed_vue, indent=2))
    else: print(f"Vue SFC parsing failed for {dummy_vue_file}")

    # import shutil; shutil.rmtree(DUMMY_FILES_DIR) # Optional cleanup
