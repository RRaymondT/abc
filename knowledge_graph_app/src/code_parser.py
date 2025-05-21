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
                    class_methods.append({
                        "name": item.name,
                        "parameters": method_params,
                        "calls": list(set(method_calls))
                    })
            classes.append({
                "name": node.name,
                "base_classes": base_classes,
                "methods": class_methods
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
                functions.append({
                    "name": node.name,
                    "parameters": func_params,
                    "calls": list(set(func_calls))
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
    # elif extension == '.cs':
    #     return parse_csharp_file(file_path) # Future
    # elif extension == '.vue':
    #     return parse_vue_component(file_path) # Future
    else:
        logging.info(f"No parser available for file extension: {extension} ({file_path})")
        return None


if __name__ == '__main__':
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

class MyClass(object):
    def __init__(self, value):
        self.value = value
        self.helper()

    def helper(self):
        print(f"Helper method called with {self.value}")
        local_call()

    def another_method(self, x, y):
        return x + y

def top_level_function(param1):
    print(f"Top level function called with {param1}")
    res = MyClass(param1).another_method(1,2)
    return res

def local_call():
    print("Local call executed")

if __name__ == "__main__":
    mc = MyClass(10)
    top_level_function("test")
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
            print(f"  - {cls.get('name')}({', '.join(cls.get('base_classes',[]))})")
            for mth in cls.get("methods", []):
                print(f"    - Method: {mth.get('name')}({', '.join(mth.get('parameters',[]))}), Calls: {mth.get('calls')}")
        print("Functions:")
        for func in parsed_py.get("functions", []):
            print(f"  - {func.get('name')}({', '.join(func.get('parameters',[]))}), Calls: {func.get('calls')}")
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

    # Clean up dummy files (optional)
    # import shutil
    # shutil.rmtree(DUMMY_FILES_DIR)
    # print(f"\nCleaned up dummy files in {DUMMY_FILES_DIR}")
