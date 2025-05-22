# This module will be responsible for building the knowledge graph.

import networkx
import logging
import os # For path operations in example
import re # For _extract_property_names_from_lambda

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KnowledgeGraph:
    def __init__(self):
        """
        Initializes the KnowledgeGraph with an empty directed graph
        and a set to track node IDs.
        """
        self.graph = networkx.DiGraph()
        self.nodes = set() # To keep track of added node IDs
        logging.info("KnowledgeGraph initialized.")

    def _extract_property_names_from_lambda(self, lambda_str: str) -> list[str]:
        """
        Extracts property names from a C# lambda string like "e => e.Id" or "e => new { e.Key1, e.Key2 }".
        """
        if not isinstance(lambda_str, str): # Guard against non-string input
            logging.warning(f"Invalid input to _extract_property_names_from_lambda: expected string, got {type(lambda_str)}")
            return []
            
        # Regex to find property names after "e." (or any variable name before dot)
        # It looks for patterns like 'x.Property'
        PROP_FROM_LAMBDA_REGEX = re.compile(r"\w+\.([\w]+)")
        matches = PROP_FROM_LAMBDA_REGEX.findall(lambda_str)
        return list(set(matches)) # Return unique property names

    def _find_or_create_callable_node(self, file_path_context: str, callable_name_str: str) -> str:
        """
        Finds an existing node representing the callable, or creates a placeholder.
        This is a simplified heuristic.
        """
        # Attempt to find function/method in the same file
        # This requires knowing the structure of IDs (e.g., "function::filepath::func_name" or "method::filepath::class::method_name")
        # We'll try common patterns.
        
        # Case 1: Simple function name in the same file context
        # Assuming callable_name_str does not contain "::" or class context like "MyClass.method"
        # This simple check might not be enough if callable_name_str is complex e.g. "module.func"
        
        # Simplified check: if it's a simple name, assume it's a function in the current file.
        # This won't find methods or imported functions correctly without more context/parsing.
        
        # Let's try to find a function node
        # (e.g., function::/path/to/file.py::my_func)
        # or a method node (e.g., method::/path/to/file.py::ClassName::my_method)
        # or a class constructor (e.g., class::/path/to/file.py::ClassName)
        
        # For a simple callable_name_str like "my_func", try to match it to a function in file_path_context
        potential_func_node_id = self._generate_node_id("function", file_path_context, callable_name_str)
        if potential_func_node_id in self.nodes:
            return potential_func_node_id

        # If callable_name_str is like "ClassName.method_name" or "self.method_name", it's more complex.
        # This simplified version will mostly create placeholders for such calls.
        # A more robust implementation would:
        # - require class_name_context if "self." is used
        # - parse "module.func" and look for module nodes then func nodes.
        # - check for class constructor calls.

        # If not found through simple heuristics, create a placeholder
        node_id = self._generate_node_id(f"callable_external_or_unresolved::{callable_name_str}")
        self.add_node(node_id, node_type="external_or_unresolved_callable", name=callable_name_str)
        logging.debug(f"Created placeholder callable node: {node_id} for '{callable_name_str}' in context of {file_path_context}")
        return node_id


    def _generate_node_id(self, *parts: str) -> str:
        """
        Generates a consistent, unique node ID from multiple parts.
        Filters out None or empty parts before joining.

        Args:
            *parts: Variable length argument list of strings to form the ID.

        Returns:
            A string ID.
        """
        valid_parts = [str(part) for part in parts if part is not None and str(part).strip() != ""]
        if not valid_parts:
            # This case should ideally be handled by the caller by providing valid parts
            logging.warning("Attempted to generate node ID from empty or None parts.")
            return "error_node_empty_parts" 
        return "::".join(valid_parts)

    def add_node(self, node_id: str, node_type: str = "unknown", **attrs):
        """
        Adds a node to the graph if it doesn't already exist.
        If the node exists, it updates its attributes with any new non-None attributes provided.

        Args:
            node_id: The unique ID for the node.
            node_type: The type of the node (e.g., 'file', 'class', 'method').
            **attrs: Additional attributes for the node.
        """
        if not node_id:
            logging.warning(f"Attempted to add a node with an empty or None ID. Type: {node_type}, Attrs: {attrs}")
            return

        if node_id not in self.nodes:
            self.graph.add_node(node_id, type=node_type, **attrs)
            self.nodes.add(node_id)
            logging.debug(f"Node added: {node_id} (Type: {node_type}, Attrs: {attrs})")
        else:
            # Update existing node's attributes if new values are provided
            # and are different from existing ones.
            # Only update if the new attribute value is not None.
            # This prevents accidentally overwriting existing attributes with None.
            updated_attrs = {}
            for key, value in attrs.items():
                if value is not None:
                    if key not in self.graph.nodes[node_id] or self.graph.nodes[node_id][key] != value:
                        self.graph.nodes[node_id][key] = value
                        updated_attrs[key] = value
            if updated_attrs:
                 logging.debug(f"Node updated: {node_id} (Updated Attrs: {updated_attrs})")
            # Ensure 'type' is also updated if a more specific type is provided later
            if 'type' not in self.graph.nodes[node_id] or self.graph.nodes[node_id]['type'] == "unknown" or self.graph.nodes[node_id]['type'] == "inferred_entity":
                if node_type not in ["unknown", "inferred_entity"]: # Don't overwrite a specific type with a generic one
                    self.graph.nodes[node_id]['type'] = node_type
                    logging.debug(f"Node type updated for {node_id} to {node_type}")


    def add_edge(self, source_node_id: str, target_node_id: str, relationship_type: str, **attrs):
        """
        Adds a directed edge to the graph.
        If source or target nodes do not exist, they are added with type 'inferred_entity'.

        Args:
            source_node_id: The ID of the source node.
            target_node_id: The ID of the target node.
            relationship_type: The type of relationship (e.g., 'calls', 'imports').
            **attrs: Additional attributes for the edge.
        """
        if not source_node_id or not target_node_id:
            logging.warning(f"Attempted to add an edge with empty or None source/target ID. "
                            f"Source: '{source_node_id}', Target: '{target_node_id}', Rel: {relationship_type}")
            return

        # Ensure source and target nodes exist before adding an edge
        if source_node_id not in self.nodes:
            logging.info(f"Source node '{source_node_id}' not found. Adding as 'inferred_entity'.")
            self.add_node(source_node_id, node_type="inferred_entity", name=source_node_id.split("::")[-1])
        if target_node_id not in self.nodes:
            logging.info(f"Target node '{target_node_id}' not found. Adding as 'inferred_entity'.")
            self.add_node(target_node_id, node_type="inferred_entity", name=target_node_id.split("::")[-1])

        self.graph.add_edge(source_node_id, target_node_id, type=relationship_type, **attrs)
        logging.debug(f"Edge added: {source_node_id} -> {target_node_id} (Type: {relationship_type}, Attrs: {attrs})")

    def get_graph(self):
        """Returns the underlying NetworkX graph."""
        return self.graph

    def process_python_parsed_data(self, parsed_data: dict, file_path: str):
        """
        Processes parsed Python data and adds corresponding nodes and edges to the graph.
        Ensures 'decorators' attribute is added if present in parsed_data.

        Args:
            parsed_data: The dictionary from parse_python_file.
            file_path: The path of the parsed Python file.
        """
        if not parsed_data:
            logging.warning(f"No parsed data provided for Python file: {file_path}")
            return

        file_node_id = self._generate_node_id("file", file_path)
        self.add_node(file_node_id, node_type="python_file", path=file_path, name=os.path.basename(file_path))
        logging.debug(f"Processing Python file node: {file_node_id}")

        # Process imports
        for mod_name in parsed_data.get('imports', []):
            clean_mod_name = mod_name.lstrip('.') 
            mod_node_id = self._generate_node_id("module", clean_mod_name)
            self.add_node(mod_node_id, node_type="python_module", name=clean_mod_name)
            self.add_edge(file_node_id, mod_node_id, relationship_type="imports")

        # Process classes
        for cls_data in parsed_data.get('classes', []):
            class_name = cls_data['name']
            class_node_id = self._generate_node_id("class", file_path, class_name)
            node_attrs = {
                "name": class_name,
                "base_classes": cls_data.get('base_classes', []),
                "file_path": file_path
            }
            if cls_data.get('decorators'):
                node_attrs['decorators'] = cls_data['decorators']
            self.add_node(class_node_id, node_type="class", **node_attrs)
            self.add_edge(file_node_id, class_node_id, relationship_type="defines_class")

            # Process methods
            for m_data in cls_data.get('methods', []):
                method_name = m_data['name']
                method_node_id = self._generate_node_id("method", file_path, class_name, method_name)
                method_attrs = {
                    "name": method_name,
                    "parameters": m_data.get('parameters', []),
                    "class_name": class_name,
                    "file_path": file_path
                }
                if m_data.get('decorators'):
                    method_attrs['decorators'] = m_data['decorators']
                self.add_node(method_node_id, node_type="method", **method_attrs)
                self.add_edge(class_node_id, method_node_id, relationship_type="defines_method")

                # Process general calls (already present)
                for call_target_str in m_data.get('calls', []):
                    target_node_id = self._generate_node_id("callable", call_target_str) # Simplified, might need _find_or_create_callable_node logic
                    self.add_node(target_node_id, node_type="callable_entity", name=call_target_str, inferred=True)
                    self.add_edge(method_node_id, target_node_id, relationship_type="calls")
                
                # Process data flow links for methods
                if m_data.get('data_flow_links'):
                    for flow_link in m_data['data_flow_links']:
                        source_func_str = flow_link['source_function']
                        target_func_str = flow_link['target_function']
                        intermediate_var = flow_link['intermediate_variable']
                        
                        # Use file_path as context for resolving these callable names
                        source_callable_node_id = self._find_or_create_callable_node(file_path, source_func_str)
                        target_callable_node_id = self._find_or_create_callable_node(file_path, target_func_str)
                        
                        edge_attrs = {
                            "flow_through_function_name": method_name, # Name of the method containing this flow
                            "flow_through_function_id": method_node_id,
                            "intermediate_variable": intermediate_var,
                            "arg_index": flow_link.get("arg_index"),
                            "keyword_arg_name": flow_link.get("keyword_arg_name")
                        }
                        edge_attrs = {k: v for k, v in edge_attrs.items() if v is not None} # Clean None values
                        self.add_edge(source_callable_node_id, target_callable_node_id, 
                                      relationship_type="potential_data_flow", **edge_attrs)

        # Process functions
        for func_data in parsed_data.get('functions', []):
            func_name = func_data['name']
            func_node_id = self._generate_node_id("function", file_path, func_name)
            func_attrs = {
                "name": func_name,
                "parameters": func_data.get('parameters', []),
                "file_path": file_path
            }
            if func_data.get('decorators'):
                func_attrs['decorators'] = func_data['decorators']
            self.add_node(func_node_id, node_type="function", **func_attrs)
            self.add_edge(file_node_id, func_node_id, relationship_type="defines_function")

            # Process general calls (already present)
            for call_target_str in func_data.get('calls', []):
                target_node_id = self._generate_node_id("callable", call_target_str) # Simplified
                self.add_node(target_node_id, node_type="callable_entity", name=call_target_str, inferred=True)
                self.add_edge(func_node_id, target_node_id, relationship_type="calls")

            # Process data flow links for functions
            if func_data.get('data_flow_links'):
                for flow_link in func_data['data_flow_links']:
                    source_func_str = flow_link['source_function']
                    target_func_str = flow_link['target_function']
                    intermediate_var = flow_link['intermediate_variable']

                    source_callable_node_id = self._find_or_create_callable_node(file_path, source_func_str)
                    target_callable_node_id = self._find_or_create_callable_node(file_path, target_func_str)

                    edge_attrs = {
                        "flow_through_function_name": func_name, # Name of the function containing this flow
                        "flow_through_function_id": func_node_id,
                        "intermediate_variable": intermediate_var,
                        "arg_index": flow_link.get("arg_index"),
                        "keyword_arg_name": flow_link.get("keyword_arg_name")
                    }
                    edge_attrs = {k: v for k, v in edge_attrs.items() if v is not None}
                    self.add_edge(source_callable_node_id, target_callable_node_id, 
                                  relationship_type="potential_data_flow", **edge_attrs)

    def process_bpmn_parsed_data(self, parsed_data: dict, file_path: str):
        """
        Processes parsed BPMN data and adds corresponding nodes and edges to the graph.

        Args:
            parsed_data: The dictionary from identify_camunda_bpmn.
            file_path: The path of the parsed BPMN file.
        """
        if not parsed_data:
            logging.warning(f"No parsed data provided for BPMN file: {file_path}")
            return

        file_node_id = self._generate_node_id("file", file_path)
        self.add_node(file_node_id, node_type="bpmn_file", path=file_path, name=os.path.basename(file_path))
        logging.debug(f"Processing BPMN file node: {file_node_id}")

        for p_data in parsed_data.get('processes', []):
            process_identifier = p_data.get('id') or p_data.get('name')
            if not process_identifier:
                logging.warning(f"BPMN process in {file_path} missing both id and name, skipping.")
                continue
            process_node_id = self._generate_node_id("bpmn_process", file_path, process_identifier)
            # Pass all attributes from p_data directly to the node
            self.add_node(process_node_id, node_type="bpmn_process", file_path=file_path, **p_data)
            self.add_edge(file_node_id, process_node_id, relationship_type="defines_process")

            # Process Service Tasks within this process
            for t_data in parsed_data.get('service_tasks', []):
                # Assuming tasks are uniquely identified by their ID within the file context
                # If tasks belong to a specific process, the parser should reflect that hierarchy
                # For now, linking tasks to file, and if process context is available, can link to process_node_id
                task_id = t_data.get('id')
                if not task_id:
                    logging.warning(f"Service task in {file_path} for process {process_identifier} is missing an ID, skipping.")
                    continue
                
                # If BPMN parser nests tasks under processes, this ID generation would be different
                # current parser extracts all service tasks at file level.
                # We need to ensure tasks are associated with *their* process if there are multiple.
                # For now, if parser doesn't give process context *per task*, we link globally in file.
                # A better parser would nest tasks under their respective process.
                # Let's assume for now the parsed_data structure is flat for tasks,
                # and we create a general task_node_id from file_path and task_id.
                # If the task is specific to a process, the `p_data` loop needs to filter tasks.
                # The current `identify_camunda_bpmn` provides flat lists of tasks.
                # So, we iterate all service tasks for *each* process, which is not ideal.
                # This logic needs a more hierarchical parsed_data or a way to map tasks to processes.

                # Let's refine: Assume tasks are defined globally in the file as per current parser,
                # but we can create an edge from process to task IF the task logically belongs to it.
                # This requires the BPMN model to define this (e.g., task is a child of process in XML).
                # For now, we'll create task nodes and link them from the file.
                # Linking from process to task implies the task is PART of the process.

                task_node_id = self._generate_node_id("bpmn_service_task", file_path, task_id)
                # Pass all attributes from t_data directly to the node
                self.add_node(task_node_id, node_type="bpmn_service_task", file_path=file_path, **t_data)
                # Link task to the file it's defined in
                self.add_edge(file_node_id, task_node_id, relationship_type="defines_task")
                # Link task to its parent process
                self.add_edge(process_node_id, task_node_id, relationship_type="contains_task")


                implementation = t_data.get('camunda_class') or \
                                 t_data.get('camunda_delegateExpression') or \
                                 t_data.get('camunda_expression') # or camunda_expression
                
                if implementation:
                    # Normalize potential Java class names or Spring bean names
                    impl_name = implementation.replace("#{", "").replace("}", "").strip()
                    # Assuming Java class if 'class' attribute is used, could be other things for expressions
                    impl_node_type = "java_class" if t_data.get('camunda_class') else "expression_or_delegate"
                    
                    impl_node_id = self._generate_node_id(impl_node_type, impl_name)
                    self.add_node(impl_node_id, node_type=impl_node_type, name=impl_name)
                    self.add_edge(task_node_id, impl_node_id, relationship_type="implemented_by")

            # Process User Tasks (similar to Service Tasks)
            for ut_data in parsed_data.get('user_tasks', []):
                user_task_id = ut_data.get('id')
                if not user_task_id:
                    logging.warning(f"User task in {file_path} for process {process_identifier} is missing an ID, skipping.")
                    continue
                
                user_task_node_id = self._generate_node_id("bpmn_user_task", file_path, user_task_id)
                self.add_node(user_task_node_id, node_type="bpmn_user_task", file_path=file_path, **ut_data)
                self.add_edge(file_node_id, user_task_node_id, relationship_type="defines_task")
                self.add_edge(process_node_id, user_task_node_id, relationship_type="contains_task")
                # User tasks typically don't have 'implementation' like service tasks, but may have assignees, forms etc.
                # These can be added as attributes to the node if parsed.

    def process_parsed_file_data(self, file_analysis_result: dict | None):
        """
        Processes the result from code_parser.parse_file and populates the graph.

        Args:
            file_analysis_result: The dictionary output from code_parser.parse_file.
        """
        if not file_analysis_result:
            logging.warning("Received empty file_analysis_result. Skipping.")
            return

        file_path = file_analysis_result.get("file_path")
        if not file_path: # Should not happen if parser is consistent
            logging.error("file_analysis_result is missing 'file_path'. Critical error. Skipping.")
            return

        logging.info(f"Processing parsed data for file: {file_path}")

        # Determine parser type based on more specific keys
        if 'imports' in file_analysis_result and ('classes' in file_analysis_result or 'functions' in file_analysis_result) and 'decorators' not in file_analysis_result.get('classes', [{}])[0] and 'decorators' not in file_analysis_result.get('functions', [{}])[0]:
             # This check is to ensure we are not misidentifying other types as python due to common keys.
             # The 'decorators' check is a bit of a heuristic from the previous task.
             # A better way might be for the parser to explicitly state the language/type.
             # For now, assuming this heuristic or that decorators will be empty list if not present.
            self.process_python_parsed_data(file_analysis_result, file_path)
        elif 'namespaces' in file_analysis_result and 'usings' in file_analysis_result: # Heuristic for C#
            self.process_csharp_parsed_data(file_analysis_result, file_path)
        elif 'component_name' in file_analysis_result and 'template_components_used' in file_analysis_result: # Heuristic for Vue
            self.process_vue_parsed_data(file_analysis_result, file_path)
        elif 'processes' in file_analysis_result or 'service_tasks' in file_analysis_result: # BPMN specific keys
            # This should be checked before Python if there's any ambiguity, but BPMN keys are quite distinct
            self.process_bpmn_parsed_data(file_analysis_result, file_path)
        elif 'classes' in file_analysis_result or 'functions' in file_analysis_result: # Python specific keys (fallback if not caught above)
             self.process_python_parsed_data(file_analysis_result, file_path)
        else:
            logging.warning(f"Unknown parsed data structure for {file_path}. No specific processor found. Keys: {list(file_analysis_result.keys())}")

    def process_csharp_parsed_data(self, parsed_data: dict, file_path: str):
        """
        Processes parsed C# data and adds corresponding nodes and edges to the graph.
        """
        if not parsed_data:
            logging.warning(f"No parsed data provided for C# file: {file_path}")
            return

        file_node_id = self._generate_node_id("file", file_path)
        self.add_node(file_node_id, node_type="csharp_file", path=file_path, name=os.path.basename(file_path))
        logging.debug(f"Processing C# file node: {file_node_id}")

        # Usings
        for using_directive in parsed_data.get('usings', []):
            using_node_id = self._generate_node_id("csharp_using_directive", using_directive)
            self.add_node(using_node_id, node_type="csharp_using_directive", name=using_directive)
            self.add_edge(file_node_id, using_node_id, relationship_type="imports") # 'imports' is generic

        # Namespaces
        for ns_data in parsed_data.get('namespaces', []):
            ns_name = ns_data['name']
            ns_node_id = self._generate_node_id("csharp_namespace", ns_name)
            self.add_node(ns_node_id, node_type="csharp_namespace", name=ns_name)
            self.add_edge(file_node_id, ns_node_id, relationship_type="defines_namespace")

            # Process entities within this namespace
            self._process_csharp_entities(ns_data.get('classes', []), file_node_id, file_path, ns_node_id, ns_name)
            self._process_csharp_entities(ns_data.get('interfaces', []), file_node_id, file_path, ns_node_id, ns_name, is_interface=True)

        # Process top-level classes and interfaces (outside any explicit namespace)
        # These are entities from parsed_data['classes'] or parsed_data['interfaces'] that *don't* have a 'namespace' attribute
        # or whose 'namespace' attribute was None.
        # The _process_csharp_entities method itself filters by matching entity_data.get('namespace') with the passed ns_name.
        # So, for global entities, we pass ns_name=None.
        self._process_csharp_entities(parsed_data.get('classes', []), file_node_id, file_path, None, None)
        self._process_csharp_entities(parsed_data.get('interfaces', []), file_node_id, file_path, None, None, is_interface=True)


    def _process_csharp_entities(self, entities_data: list, file_node_id: str, file_path_for_id_gen: str, ns_node_id: str | None, ns_name: str | None, is_interface=False):
        """Helper to process lists of C# classes or interfaces."""
        # file_path_for_id_gen is the original file_path string, used for consistent ID generation
        # file_node_id is the ID of the file node in the graph.
        entity_type_prefix = "csharp_interface" if is_interface else "csharp_class"
        
        for entity_data in entities_data:
            entity_name = entity_data['name']
            # Ensure entities parsed within a namespace block in parser are correctly scoped here
            # The parser puts all entities (namespaced or not) into top-level 'classes'/'interfaces' lists,
            # but includes a 'namespace' attribute on them if they were in one.
            # So, we check entity_data['namespace'] to link to the correct ns_node_id.
            # This method is called for entities within a specific ns_data, AND for global entities.
            # If ns_node_id is passed, it means we are currently processing entities for that namespace.
            # If entity_data['namespace'] matches current ns_name, good.
            # If entity_data['namespace'] is None and ns_node_id is None, it's a global entity.
            
            # Filter: only process entities that belong to the current namespace context
            # (or global if ns_node_id is None)
            if ns_name != entity_data.get('namespace'):
                continue

            # ID generation uses the original file_path string for consistency, not the file_node_id
            entity_node_id = self._generate_node_id(entity_type_prefix, file_path_for_id_gen, entity_name) 
            
            attrs_to_add = {
                "name": entity_name,
                "attributes": entity_data.get('attributes', []),
                "base_types_str": entity_data.get('base_types_str'), 
                "namespace": entity_data.get('namespace'), 
                "file_path": file_path_for_id_gen # Store actual file path for reference
            }
            attrs_to_add = {k: v for k, v in attrs_to_add.items() if v is not None}

            self.add_node(entity_node_id, node_type=entity_type_prefix, **attrs_to_add)
            self.add_edge(file_node_id, entity_node_id, relationship_type=f"defines_{'interface' if is_interface else 'class'}")

            if ns_node_id and entity_data.get('namespace'): 
                 self.add_edge(ns_node_id, entity_node_id, relationship_type="contains_entity")

            if entity_data.get('base_types_str'):
                base_types = [b.strip() for b in entity_data['base_types_str'].split(',')]
                for base_type_name in base_types:
                    base_type_node_id = self._generate_node_id("csharp_external_type", base_type_name)
                    self.add_node(base_type_node_id, node_type="csharp_external_type", name=base_type_name, inferred=True)
                    self.add_edge(entity_node_id, base_type_node_id, relationship_type="inherits_or_implements_from")
            
            for method_data in entity_data.get('methods', []):
                method_name = method_data['name']
                method_node_id = self._generate_node_id("csharp_method", file_path_for_id_gen, entity_name, method_name)
                method_attrs = {
                    "name": method_name,
                    "return_type": method_data.get('return_type'),
                    "parameters_str": method_data.get('parameters_str'),
                    "attributes": method_data.get('attributes', []),
                    "parent_entity_name": entity_name,
                    "file_path": file_path_for_id_gen
                }
                method_attrs = {k:v for k,v in method_attrs.items() if v is not None}
                self.add_node(method_node_id, node_type="csharp_method", **method_attrs)
                self.add_edge(entity_node_id, method_node_id, relationship_type="defines_method")

            for prop_data in entity_data.get('properties', []):
                prop_name = prop_data['name']
                prop_node_id = self._generate_node_id("csharp_property", file_path_for_id_gen, entity_name, prop_name)
                method_attrs = {k:v for k,v in method_attrs.items() if v is not None} # Ensure this line was present for methods
                self.add_node(method_node_id, node_type="csharp_method", **method_attrs)
                self.add_edge(entity_node_id, method_node_id, relationship_type="defines_method")

            for prop_data in entity_data.get('properties', []):
                prop_name = prop_data['name']
                prop_node_id = self._generate_node_id("csharp_property", file_path_for_id_gen, entity_name, prop_name)
                prop_attrs = {
                    "name": prop_name,
                    "csharp_type": prop_data.get('type'), # Changed 'type' to 'csharp_type'
                    "attributes": prop_data.get('attributes', []),
                    "parent_entity_name": entity_name,
                    "file_path": file_path_for_id_gen
                }
                prop_attrs = {k:v for k,v in prop_attrs.items() if v is not None}
                self.add_node(prop_node_id, node_type="csharp_property", **prop_attrs)
                self.add_edge(entity_node_id, prop_node_id, relationship_type="defines_property")
            
            # After processing the class/interface and its members, check if it's a DbContext
            if not is_interface and entity_data.get('is_dbcontext'):
                self.process_ef_dbcontext_data(entity_data, file_path_for_id_gen)


    def process_ef_dbcontext_data(self, ef_class_data: dict, file_path_for_id_gen: str):
        """
        Processes Entity Framework DbContext specific data (DbSets, OnModelCreating configurations)
        for a given C# class.

        Args:
            ef_class_data: The dictionary for the C# class identified as a DbContext.
                           This data comes from the C# parser.
            file_path_for_id_gen: The original file path string for consistent ID generation.
        """
        dbcontext_name = ef_class_data['name']
        # The DbContext node itself (csharp_class) is already created by _process_csharp_entities.
        # We need its ID to link DbSets and configurations.
        # The ID for the DbContext class node was: self._generate_node_id("csharp_class", file_path_for_id_gen, dbcontext_name)
        dbcontext_node_id = self._generate_node_id("csharp_class", file_path_for_id_gen, dbcontext_name)

        logging.info(f"Processing EF DbContext data for: {dbcontext_name} (Node ID: {dbcontext_node_id})")

        # Process DbSet<T> properties
        for db_set in ef_class_data.get('db_sets', []):
            entity_name = db_set.get('entity_name')
            if not entity_name:
                logging.warning(f"DbSet in {dbcontext_name} missing entity_name: {db_set}")
                continue
            
            # Node ID for the DB entity type (e.g., "Customer", "Order")
            # Prefix with "db_entity::" to distinguish from potential C# class nodes with same name
            entity_node_id = self._generate_node_id(f"db_entity::{entity_name}")
            
            self.add_node(entity_node_id, node_type="db_entity", name=entity_name, 
                          defined_in_dbcontext=dbcontext_name,
                          source_file=file_path_for_id_gen)
            self.add_edge(dbcontext_node_id, entity_node_id, 
                          relationship_type="defines_db_entity_set", 
                          set_name=db_set.get('property_name', 'UnknownSet'))
            logging.debug(f"Added DbSet '{db_set.get('property_name')}' for entity '{entity_name}' in {dbcontext_name}")

        # Process ef_configurations from OnModelCreating
        for config in ef_class_data.get('ef_configurations', []):
            configured_entity_name = config.get('entity_configured')
            if not configured_entity_name:
                logging.warning(f"EF configuration in {dbcontext_name} missing 'entity_configured': {config}")
                continue

            # Ensure the db_entity node exists (it might have been created from a DbSet or another config)
            entity_node_id = self._generate_node_id(f"db_entity::{configured_entity_name}")
            self.add_node(entity_node_id, node_type="db_entity", name=configured_entity_name,
                          defined_in_dbcontext=dbcontext_name,
                          source_file=file_path_for_id_gen) # Add or update node

            call_type = config.get('call_type')
            details = config.get('details', {})

            if call_type == 'HasKey':
                # Details for HasKey directly contains the lambda string or parsed keys
                key_lambda_str = details.get('key_expression', '') # From parser
                prop_names = details.get('keys_found', []) # From parser
                
                if not prop_names and key_lambda_str: # Fallback if parser only gave expression
                    prop_names = self._extract_property_names_from_lambda(key_lambda_str)

                for prop_name in prop_names:
                    # ID for the property of the DB entity
                    prop_node_id = self._generate_node_id(entity_node_id, "property", prop_name)
                    self.add_node(prop_node_id, node_type="db_property", name=prop_name, 
                                  is_primary_key=True, entity_name=configured_entity_name)
                    self.add_edge(entity_node_id, prop_node_id, relationship_type="has_primary_key_property")
                    logging.debug(f"Configured PK: {configured_entity_name}.{prop_name}")

            elif call_type == 'Property':
                prop_name = details.get('property_name')
                if not prop_name:
                    logging.warning(f"EF 'Property' config in {dbcontext_name} for entity {configured_entity_name} missing 'property_name': {details}")
                    continue
                
                prop_node_id = self._generate_node_id(entity_node_id, "property", prop_name)
                prop_attrs = {k:v for k,v in details.items()} # Copy all details from parser
                prop_attrs['name'] = prop_name # Ensure name is set
                prop_attrs['entity_name'] = configured_entity_name
                self.add_node(prop_node_id, node_type="db_property", **prop_attrs)
                self.add_edge(entity_node_id, prop_node_id, relationship_type="has_property_configured")
                logging.debug(f"Configured Property: {configured_entity_name}.{prop_name} with details {details}")

            elif call_type in ["HasMany_WithOne", "HasOne_WithMany", "HasOne_WithOne"]:
                # Details for relationships should contain target entity and navigation properties
                # The parser provides 'many_arg', 'one_arg', 'nav_prop' etc.
                # We need to determine the 'target_entity' based on these.
                # For HasMany_WithOne: current_entity_type (source) HasMany target_entity_type_arg (target)
                #                      target_navigation is on the target_entity_type_arg side.
                # For HasOne_WithMany: current_entity_type (source) HasOne target_entity_type_arg (target)
                #                      target_navigation is on the target_entity_type_arg side.
                # For HasOne_WithOne:  current_entity_type (source) HasOne target_entity_type_arg (target)
                
                # Simplified: determine target entity from 'details' if parser provides a clear key like 'target_entity_type_arg' or similar
                # The C# parser's _parse_ef_onmodelcreating_body provides 'many_arg', 'one_arg', 'nav_prop1', 'nav_prop2'
                # 'many_arg' or 'one_arg' (or 'one_arg1'/'one_arg2') can be the type of the target entity.
                # 'nav_propX' are names of navigation properties.
                
                target_entity_name = None
                if call_type == "HasMany_WithOne" and details.get("one_arg"): target_entity_name = details.get("one_arg")
                elif call_type == "HasOne_WithMany" and details.get("many_arg"): target_entity_name = details.get("many_arg")
                elif call_type == "HasOne_WithOne" and details.get("one_arg2"): # Assuming one_arg2 is the target type in HasOne().WithOne(target => target.Nav)
                    target_entity_name = details.get("one_arg2") 
                elif details.get("target_entity"): # Generic fallback if parser uses this key
                    target_entity_name = details.get("target_entity")


                if not target_entity_name:
                    logging.warning(f"EF '{call_type}' config in {dbcontext_name} for {configured_entity_name} "
                                    f"could not determine target_entity from details: {details}")
                    continue
                
                target_entity_node_id = self._generate_node_id(f"db_entity::{target_entity_name}")
                self.add_node(target_entity_node_id, node_type="db_entity", name=target_entity_name,
                              defined_in_dbcontext=dbcontext_name, # May or may not be true, but context is this DbContext
                              source_file=file_path_for_id_gen, inferred=True) # Inferred as it might not be a DbSet itself

                edge_attrs = {k:v for k,v in details.items() if k not in ['target_entity', 'many_arg', 'one_arg', 'one_arg1', 'one_arg2']} # Exclude args used to find target
                edge_attrs['description'] = details.get('description', call_type) # Use specific description if parser provided it
                
                self.add_edge(entity_node_id, target_entity_node_id, 
                              relationship_type=call_type.lower().replace("_", "_to_"), # e.g. hasmany_to_withone
                              **edge_attrs)
                logging.debug(f"Configured Relationship: {configured_entity_name} {call_type} {target_entity_name}")
            else:
                logging.warning(f"Unknown EF configuration call_type '{call_type}' in {dbcontext_name} for entity {configured_entity_name}.")


    def process_vue_parsed_data(self, parsed_data: dict, file_path: str):
        """
        Processes parsed Vue.js SFC data and adds corresponding nodes and edges to the graph.
        """
        if not parsed_data:
            logging.warning(f"No parsed data provided for Vue SFC file: {file_path}")
            return

        file_node_id = self._generate_node_id("file", file_path) # Represents the .vue file itself
        self.add_node(file_node_id, node_type="vue_component_file", path=file_path, name=os.path.basename(file_path))
        logging.debug(f"Processing Vue SFC file node: {file_node_id}")

        comp_name = parsed_data.get('component_name', os.path.splitext(os.path.basename(file_path))[0])
        # Primary component node ID includes file_path to ensure uniqueness if multiple components have same name
        comp_node_id = self._generate_node_id("vue_component", file_path, comp_name)
        
        comp_attrs = {"name": comp_name, "file_path": file_path}
        if parsed_data.get('script_lang'):
            comp_attrs['script_lang'] = parsed_data['script_lang']
        if parsed_data.get('style_lang'):
            comp_attrs['style_lang'] = parsed_data['style_lang']
        self.add_node(comp_node_id, node_type="vue_component", **comp_attrs)
        self.add_edge(file_node_id, comp_node_id, relationship_type="defines_component")

        # Imports from <script>
        for import_source in parsed_data.get('imports', []):
            # Assuming imports are typically JS modules or other .vue components
            # For simplicity, using a generic 'javascript_module' type.
            # Could try to resolve if it's another .vue file in the project later.
            import_node_id = self._generate_node_id("javascript_module", import_source) 
            self.add_node(import_node_id, node_type="javascript_module", name=import_source, inferred=True)
            self.add_edge(comp_node_id, import_node_id, relationship_type="imports_js_module")

        # Props
        for prop_name in parsed_data.get('props', []):
            prop_node_id = self._generate_node_id("vue_prop", file_path, comp_name, prop_name)
            self.add_node(prop_node_id, node_type="vue_prop", name=prop_name, component_name=comp_name, file_path=file_path)
            self.add_edge(comp_node_id, prop_node_id, relationship_type="has_prop")

        # Data Properties
        for data_prop_name in parsed_data.get('data_properties', []):
            data_node_id = self._generate_node_id("vue_data_property", file_path, comp_name, data_prop_name)
            self.add_node(data_node_id, node_type="vue_data_property", name=data_prop_name, component_name=comp_name, file_path=file_path)
            self.add_edge(comp_node_id, data_node_id, relationship_type="has_data")

        # Methods
        for method_name in parsed_data.get('methods', []):
            method_node_id = self._generate_node_id("vue_method", file_path, comp_name, method_name)
            self.add_node(method_node_id, node_type="vue_method", name=method_name, component_name=comp_name, file_path=file_path)
            self.add_edge(comp_node_id, method_node_id, relationship_type="has_method")

        # Computed Properties
        for computed_name in parsed_data.get('computed_properties', []):
            computed_node_id = self._generate_node_id("vue_computed_property", file_path, comp_name, computed_name)
            self.add_node(computed_node_id, node_type="vue_computed_property", name=computed_name, component_name=comp_name, file_path=file_path)
            self.add_edge(comp_node_id, computed_node_id, relationship_type="has_computed")

        # Template Component Usage
        for used_comp_tag_name in parsed_data.get('template_components_used', []):
            # Node ID for used components: if they are local/imported, their file_path might be resolvable.
            # For now, treat them as potentially external or globally unique by name.
            # A more sophisticated approach would try to match used_comp_tag_name with imported component names.
            used_comp_node_id = self._generate_node_id("vue_component", used_comp_tag_name) # Simpler ID for used component
            self.add_node(used_comp_node_id, node_type="vue_component", name=used_comp_tag_name, inferred=True)
            self.add_edge(comp_node_id, used_comp_node_id, relationship_type="uses_component_in_template")

        # Template Event Bindings
        for binding in parsed_data.get('template_event_bindings', []):
            event_name = binding.get('event')
            handler_name = binding.get('handler')
            if event_name and handler_name:
                # Attempt to link to an existing method node of the component
                # Clean handler_name if it includes arguments, e.g., "myMethod(arg)" -> "myMethod"
                handler_method_name_clean = handler_name.split('(')[0].strip()
                
                target_method_node_id = self._generate_node_id("vue_method", file_path, comp_name, handler_method_name_clean)
                
                # Check if this method node actually exists (was parsed from <script>)
                if target_method_node_id in self.nodes:
                    self.add_edge(comp_node_id, target_method_node_id, 
                                  relationship_type=f"on_{event_name.replace('.', '_')}_calls_method", 
                                  handler_expression=handler_name)
                else:
                    # Handler might be an inline expression or refer to something not parsed as a distinct method
                    # Create an "inferred_handler" node or add attribute to component?
                    # For now, log it and potentially create an inferred callable node.
                    inferred_handler_id = self._generate_node_id("vue_event_handler_expression", file_path, comp_name, event_name, handler_name)
                    self.add_node(inferred_handler_id, node_type="vue_event_handler_expression", name=handler_name, event_name=event_name, component_name=comp_name, file_path=file_path)
                    self.add_edge(comp_node_id, inferred_handler_id, relationship_type=f"handles_event_{event_name.replace('.', '_')}")
                    logging.debug(f"Vue component {comp_name} event '{event_name}' handler '{handler_name}' does not directly map to a parsed method. Created expression node.")

    def process_k8s_yaml_data(self, k8s_resource_list: list, file_path: str):
        """
        Processes parsed Kubernetes YAML data and adds corresponding nodes and edges to the graph.

        Args:
            k8s_resource_list: A list of dictionaries, where each dictionary represents a parsed K8s resource.
            file_path: The path of the original K8s YAML file.
        """
        if not k8s_resource_list:
            logging.info(f"No Kubernetes resources provided for file: {file_path}")
            return

        yaml_file_node_id = self._generate_node_id("k8s_yaml_file", file_path) # Use specific prefix for k8s file nodes
        self.add_node(yaml_file_node_id, node_type="k8s_yaml_file", path=file_path, name=os.path.basename(file_path))
        logging.debug(f"Processing K8s YAML file node: {yaml_file_node_id}")

        for resource_data in k8s_resource_list:
            kind = resource_data.get('kind', 'UnknownKind')
            name = resource_data.get('name', 'Unnamed')
            namespace = resource_data.get('namespace', 'default') # K8s default namespace

            # Node ID for K8s resource: file_path + kind + namespace + name
            # This aims to make it unique for resources defined in different files or with same name in different namespaces.
            # For multi-doc YAMLs where file_path, kind, ns, name might still collide (e.g. multiple unnamed resources of same kind),
            # the parser should ideally provide a unique identifier or index from the document.
            # For now, this is a reasonable approach.
            resource_node_id = self._generate_node_id("k8s_resource", file_path, kind, namespace, name)

            # Prepare attributes for the node, excluding 'file_path' as it's on the file node.
            node_attrs = {k: v for k, v in resource_data.items() if k != 'file_path'}
            node_attrs['name'] = name # Ensure 'name' is set for display consistency.
            
            # Use a standardized k8s_ type prefix for graph consistency
            node_type_str = f"k8s_{kind.lower().replace('-', '_')}"
            self.add_node(resource_node_id, node_type=node_type_str, **node_attrs)
            self.add_edge(yaml_file_node_id, resource_node_id, relationship_type="defines_k8s_resource")
            logging.debug(f"Added K8s resource node: {resource_node_id} (Type: {node_type_str})")

            # Process Containers if present
            if 'containers' in resource_data and resource_data['containers'] is not None:
                for container in resource_data['containers']:
                    if not isinstance(container, dict): # Ensure container is a dict
                        logging.warning(f"Skipping malformed container data for K8s resource {resource_node_id}: {container}")
                        continue

                    image_name = container.get('image')
                    if image_name:
                        # Global ID for images to ensure they are the same node if used by multiple deployments
                        image_node_id = self._generate_node_id(f"docker_image::{image_name}")
                        
                        image_tag = 'latest' # Default tag
                        if ':' in image_name and not image_name.endswith(':'):
                            try_tag = image_name.split(':')[-1]
                            # Basic check: avoid parts of path like 'myregistry.com/path' being mistaken for tag
                            if '/' not in try_tag: 
                                image_tag = try_tag
                        
                        self.add_node(image_node_id, node_type="docker_image", name=image_name, image_tag=image_tag)
                        self.add_edge(resource_node_id, image_node_id, 
                                      relationship_type="uses_image", 
                                      container_name=container.get('name', 'UnnamedContainer'))
                        logging.debug(f"K8s resource {resource_node_id} uses image {image_name} (Tag: {image_tag})")
            
            # Service Selector processing (placeholder for future enhancement)
            if 'selector' in resource_data and resource_data['selector'] is not None:
                # The selector (a dict) is already stored as an attribute on the service node by **node_attrs.
                # Future: self.link_k8s_service_selector(resource_node_id, resource_data['selector'], namespace)
                logging.debug(f"K8s service {resource_node_id} has selector: {resource_data['selector']}")


    def process_tech_scan_data(self, tech_scan_results: dict, codebase_path: str):
        """
        Processes technology scan results and adds corresponding nodes and edges.

        Args:
            tech_scan_results: The dictionary from tech_scanner.detect_technologies.
            codebase_path: The root path of the codebase.
        """
        if not tech_scan_results:
            logging.warning("No tech scan results provided.")
            return

        codebase_node_id = self._generate_node_id("codebase", codebase_path)
        self.add_node(codebase_node_id, node_type="codebase", path=codebase_path, name=os.path.basename(codebase_path) or codebase_path)
        logging.debug(f"Processing codebase node: {codebase_node_id}")

        # Process project files
        project_files_data = tech_scan_results.get('project_files', {})
        for tech_name, files in project_files_data.items():
            tech_node_id = self._generate_node_id("tech", tech_name.lower().replace(" ", "_").replace(".", "_"))
            self.add_node(tech_node_id, node_type="build_system_or_framework", name=tech_name)
            for pf_path in files:
                pf_node_id = self._generate_node_id("file", pf_path) # Use 'file' prefix for consistency
                # Use os.path.basename for name attribute
                self.add_node(pf_node_id, node_type="project_file", path=pf_path, name=os.path.basename(pf_path))
                self.add_edge(codebase_node_id, pf_node_id, relationship_type="contains_project_file")
                self.add_edge(pf_node_id, tech_node_id, relationship_type="uses_technology_stack")

        # Process keyword scan results
        keyword_scan_data = tech_scan_results.get('keyword_scan', {})
        for tech_name, files in keyword_scan_data.items():
            keyword_tech_node_id = self._generate_node_id("tech_reference", tech_name.lower().replace(" ", "_").replace(".", "_"))
            self.add_node(keyword_tech_node_id, node_type="technology_reference", name=tech_name)
            for file_path in files:
                file_node_id = self._generate_node_id("file", file_path)
                # Add node if it doesn't exist (e.g. if file wasn't parsed but keywords were found)
                self.add_node(file_node_id, node_type="file", path=file_path, name=os.path.basename(file_path))
                self.add_edge(file_node_id, keyword_tech_node_id, relationship_type="mentions_technology")

    def load_graph_from_directory(self, codebase_path: str, tech_scan_data: dict, all_parsed_data: dict):
        """
        Orchestrates the graph building process from tech scan and parsed file data.

        Args:
            codebase_path: The root path of the codebase.
            tech_scan_data: Output from tech_scanner.detect_technologies.
            all_parsed_data: A dictionary where keys are file paths and values are
                             the outputs of code_parser.parse_file for those paths.
        """
        logging.info(f"Loading graph from directory: {codebase_path}")

        # Process technology scan data first to establish codebase and tech nodes
        if tech_scan_data:
            self.process_tech_scan_data(tech_scan_data, codebase_path)
        else:
            logging.warning("No technology scan data provided to load_graph_from_directory.")

        # Process individual file parsing results
        if all_parsed_data:
            for file_path_key, parsed_data_for_file_value in all_parsed_data.items():
                if parsed_data_for_file_value: # Ensure there's data to process
                     # Pass the actual file_path from the parsed data if available, else use key
                    actual_file_path = parsed_data_for_file_value.get("file_path", file_path_key)
                    self.process_parsed_file_data(parsed_data_for_file_value) # process_parsed_file_data gets path from result
                else:
                    logging.debug(f"No parsed data for {file_path_key}, ensuring basic file node exists.")
                    file_node_id = self._generate_node_id("file", file_path_key) # Use key if value is None
                    self.add_node(file_node_id, node_type="file", path=file_path_key, name=os.path.basename(file_path_key))
        else:
            logging.warning("No parsed file data provided to load_graph_from_directory.")
        
        logging.info("Graph loading complete.")


if __name__ == '__main__':
    # --- Setup Dummy Data ---
    # This simulates the kind of data structure we'd get from the other modules.
    
    # 1. Mock Tech Scan Data (from tech_scanner.py)
    mock_codebase_path = "/app/dummy_project_root" # A plausible path in the execution environment
    
    # Create dummy directories and files for a more realistic test
    # Ensure these paths match what's used in mock_tech_scan and mock_parsed_data
    os.makedirs(os.path.join(mock_codebase_path, "src", "main", "java", "com", "example"), exist_ok=True)
    os.makedirs(os.path.join(mock_codebase_path, "src", "main", "resources", "bpmn"), exist_ok=True)
    os.makedirs(os.path.join(mock_codebase_path, "app", "services"), exist_ok=True)

    # Dummy pom.xml
    dummy_pom_path = os.path.join(mock_codebase_path, "pom.xml")
    with open(dummy_pom_path, "w") as f:
        f.write("<project><dependencies><dependency><groupId>org.camunda.bpm</groupId></dependency></dependencies></project>")

    # Dummy Python file
    dummy_py_path = os.path.join(mock_codebase_path, "app", "services", "user_service.py")
    with open(dummy_py_path, "w") as f:
        f.write("import flask\nclass UserService:\n  def get_user(self, id):\n    flask.jsonify({'id': id})\ndef process_data():\n  print('processing')")

    # Dummy BPMN file
    dummy_bpmn_path = os.path.join(mock_codebase_path, "src", "main", "resources", "bpmn", "order_process.bpmn")
    with open(dummy_bpmn_path, "w") as f:
        f.write("""<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:camunda="http://camunda.org/schema/1.0/bpmn">
    <bpmn:process id="OrderProcess" name="Order Fulfillment">
        <bpmn:serviceTask id="Task_EmailCustomer" name="Email Customer" camunda:class="com.example.EmailDelegate" />
    </bpmn:process>
</bpmn:definitions>""")

    mock_tech_scan_results = {
        "project_files": {
            "Maven": [dummy_pom_path]
        },
        "keyword_scan": {
            "Camunda": [dummy_pom_path, dummy_bpmn_path],
            "Python": [dummy_py_path],
            "Flask": [dummy_py_path] # Assuming 'flask' keyword was found
        }
    }

    # 2. Mock Parsed File Data (from code_parser.py)
    # For Python file (user_service.py) - with decorators
    mock_python_parsed = {
        "file_path": dummy_py_path,
        "imports": ["flask"],
        "classes": [{
            "name": "UserService", "base_classes": [], "decorators": ["@app.route('/users')"],
            "methods": [{
                "name": "get_user", "parameters": ["self", "id"], "calls": ["flask.jsonify"], 
                "decorators": ["@app.route('/<id>')"],
                "data_flow_links": [] # Assume no specific data flow for this simple method for now
            }]
        }],
        "functions": [{
            "name": "process_data", "parameters": [], "calls": ["print"], "decorators": ["@background_task"],
            "data_flow_links": [] 
            },
            { # Adding functions for data flow example
            "name": "source_data_func", "parameters": [], "calls": [], "decorators": [],
            "data_flow_links": []
            },
            {
            "name": "process_data_func", "parameters": ["input_arg"], "calls": ["final_sink_func"], "decorators": [],
            "data_flow_links": [{ # Data flows from 'another_intermediate_func' into 'process_data_func'
                "source_function": "another_intermediate_func",
                "intermediate_variable": "temp_var_for_process",
                "target_function": "process_data_func", # Self, if data is processed within
                "arg_index": 0 
            }]
            },
            { # A function that is called by process_data_func
            "name": "final_sink_func", "parameters": ["final_data"], "calls": [], "decorators": [],
            "data_flow_links": []
            },
            { # Another function that acts as a source in a data flow link
            "name": "another_intermediate_func", "parameters": [], "calls": [], "decorators": [],
            "data_flow_links": []
            },
             { # Top-level function that orchestrates a data flow
            "name": "orchestrator_func", "parameters": [], "calls": ["source_data_func", "process_data_func"], "decorators": [],
            "data_flow_links": [{
                "source_function": "source_data_func",
                "intermediate_variable": "temp_data",
                "target_function": "process_data_func",
                "arg_index": 0 # temp_data is passed as first argument to process_data_func
            }]
            }
        ]
    }

    # For BPMN file (order_process.bpmn)
    mock_bpmn_parsed = {
        "file_path": dummy_bpmn_path, "processes": [{"id": "OrderProcess", "name": "Order Fulfillment"}],
        "service_tasks": [{"id": "Task_EmailCustomer", "name": "Email Customer", "camunda_class": "com.example.EmailDelegate"}],
        "user_tasks": []
    }

    # Mock C# Parsed Data
    dummy_cs_path = os.path.join(mock_codebase_path, "services", "ProductService.cs")
    os.makedirs(os.path.join(mock_codebase_path, "services"), exist_ok=True)
    # with open(dummy_cs_path, "w") as f: f.write("// C# Product Service") # Dummy content
    # Use the EF example code for mock_csharp_parsed
    EXAMPLE_CSHARP_EF_CODE = """
using System;
using Microsoft.EntityFrameworkCore;

namespace MyWebApp.Data
{
    public class Product { public int ProductId { get; set; } public string Name { get; set; } public int CategoryId {get;set;} public Category Category {get;set;} }
    public class Category { public int CategoryId { get; set; } public string CategoryName { get; set; } public List<Product> Products {get;set;} }

    public class AppDbContext : DbContext
    {
        public DbSet<Product> Products { get; set; }
        public DbSet<Category> Categories { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.Entity<Product>()
                .HasKey(p => p.ProductId);
            modelBuilder.Entity<Product>()
                .Property(p => p.Name)
                .IsRequired()
                .HasMaxLength(100);
            modelBuilder.Entity<Category>()
                .HasMany(c => c.Products)
                .WithOne(p => p.Category)
                .HasForeignKey(p => p.CategoryId);
        }
    }
}
"""
    with open(dummy_cs_path, "w") as f: f.write(EXAMPLE_CSHARP_EF_CODE)


    # This mock data should align with the output of your C# parser for the EF example
    mock_csharp_parsed = {
        "file_path": dummy_cs_path,
        "usings": ["System", "Microsoft.EntityFrameworkCore"],
        "namespaces": [{
            "name": "MyWebApp.Data",
            "classes": [
                {"name": "Product", "namespace": "MyWebApp.Data", "methods": [], "properties": [{"name": "ProductId", "type": "int"}, {"name": "Name", "type": "string"}, {"name":"CategoryId", "type":"int"}, {"name":"Category", "type":"Category"}]},
                {"name": "Category", "namespace": "MyWebApp.Data", "methods": [], "properties": [{"name": "CategoryId", "type": "int"}, {"name": "CategoryName", "type": "string"}, {"name": "Products", "type": "List<Product>"}]},
                {
                    "name": "AppDbContext", "namespace": "MyWebApp.Data", "base_types_str": "DbContext", 
                    "is_dbcontext": True,
                    "db_sets": [
                        {'entity_name': 'Product', 'property_name': 'Products'},
                        {'entity_name': 'Category', 'property_name': 'Categories'}
                    ],
                    "methods": [
                        {"name": "OnModelCreating", "parameters_str": "ModelBuilder modelBuilder", "return_type": "void"}
                    ],
                    "properties": [ # DbSets are properties, ensure they are also listed here by the parser if that's its behavior
                        {"name": "Products", "type": "DbSet<Product>"},
                        {"name": "Categories", "type": "DbSet<Category>"}
                    ],
                    "ef_configurations": [
                        {'entity_configured': 'Product', 'call_type': 'HasKey', 'details': {'key_expression': 'p => p.ProductId', 'keys_found': ['ProductId']}},
                        {'entity_configured': 'Product', 'call_type': 'Property', 'details': {'property_name': 'Name', 'is_required': True, 'max_length': 100}},
                        {'entity_configured': 'Category', 'call_type': 'HasMany_WithOne', 'details': {
                            'many_arg': None, # Assuming parser might not get generic from HasMany itself
                            'one_arg': None,  # Assuming parser might not get generic from WithOne itself
                            'nav_prop': 'Category', # This detail from parser might be tricky, adjust based on actual parser output
                                                    # The prompt example for graph_builder has 'target_entity', 'source_navigation', 'target_navigation'
                                                    # Let's try to match that structure for test.
                            'target_entity': 'Product', # Inferred from WithOne(p => p.Category) and Products collection
                            'source_navigation': 'Products', # c.Products
                            'target_navigation': 'Category', # p.Category
                            'foreign_key': 'CategoryId'  # p.CategoryId
                        }}
                    ]
                }
            ],
            "interfaces": []
        }],
        "classes": [], "interfaces": []
    }

    # Mock Vue.js Parsed Data
    dummy_vue_path = os.path.join(mock_codebase_path, "components", "LoginComponent.vue")
    os.makedirs(os.path.join(mock_codebase_path, "components"), exist_ok=True)
    with open(dummy_vue_path, "w") as f: f.write("<!-- Vue Login Component -->") # Dummy content

    mock_vue_parsed = {
        "file_path": dummy_vue_path,
        "component_name": "LoginComponent", "script_lang": "javascript", "style_lang": "css",
        "imports": ["./api/auth"],
        "props": ["initialUsername"],
        "data_properties": ["username", "password", "errorMsg"],
        "methods": ["loginUser", "clearForm"],
        "computed_properties": ["hasError"],
        "template_components_used": ["BaseInput", "BaseButton"],
        "template_event_bindings": [{"event": "click", "handler": "loginUser"}]
    }
    
    # Aggregate parsed data
    mock_all_parsed_data = {
        dummy_py_path: mock_python_parsed,
        dummy_bpmn_path: mock_bpmn_parsed,
        dummy_cs_path: mock_csharp_parsed,
        dummy_vue_path: mock_vue_parsed,
        dummy_pom_path: None 
    }

    # --- Instantiate and Use KnowledgeGraph ---
    kg = KnowledgeGraph()
    # kg.load_graph_from_directory(mock_codebase_path, mock_tech_scan_results, mock_all_parsed_data)
    # Instead of load_graph_from_directory, call process_parsed_file_data directly for testing new parsers
    logging.info("Testing individual file processors:")
    if mock_python_parsed: kg.process_parsed_file_data(mock_python_parsed)
    if mock_csharp_parsed: kg.process_parsed_file_data(mock_csharp_parsed)
    if mock_vue_parsed: kg.process_parsed_file_data(mock_vue_parsed)

    # --- Test K8s YAML Data Processing ---
    mock_k8s_file_path = "/fake/kube.yaml"
    mock_k8s_parsed_data = [
        {'file_path': mock_k8s_file_path, 'kind': 'Deployment', 'name': 'my-app', 'namespace': 'prod', 
         'labels': {'app': 'my-app'}, 
         'containers': [
             {'name': 'main', 'image': 'myimage:1.2.3', 'ports': [{'containerPort': 80}]},
             {'name': 'sidecar', 'image': 'myotherimage/side:latest', 'ports': []}, # Test with 'latest' tag
             {'name': 'no-tag-image', 'image': 'busybox', 'ports': []} # Test with no tag
         ]},
        {'file_path': mock_k8s_file_path, 'kind': 'Service', 'name': 'my-service', 'namespace': 'prod', 
         'selector': {'app': 'my-app'}, 
         'ports': [{'port': 8080, 'targetPort': 80}]}
    ]
    logging.info("Testing K8s YAML data processor:")
    kg.process_k8s_yaml_data(mock_k8s_parsed_data, mock_k8s_file_path)
    # Tech scan data can be loaded if needed for full context
    # kg.process_tech_scan_data(mock_tech_scan_results, mock_codebase_path)


    # --- Print Graph Info ---
    graph = kg.get_graph()
    print(f"\n--- Knowledge Graph Built (Partial - Manual Calls with K8s) ---")
    print(f"Number of nodes: {graph.number_of_nodes()}")
    print(f"Number of edges: {graph.number_of_edges()}")

    print("\nNodes (selected examples with new attributes):")
    # Python method with decorators
    py_method_id_test = kg._generate_node_id("method", dummy_py_path, "UserService", "get_user")
    if py_method_id_test in graph: print(f"  Python Method: {py_method_id_test}, Attrs: {graph.nodes[py_method_id_test]}")

    # Test data flow edge
    source_node_for_flow = kg._find_or_create_callable_node(dummy_py_path, "source_data_func")
    target_node_for_flow = kg._find_or_create_callable_node(dummy_py_path, "process_data_func")
    
    edge_exists = graph.has_edge(source_node_for_flow, target_node_for_flow)
    print(f"  Data flow edge from '{source_node_for_flow}' to '{target_node_for_flow}' exists: {edge_exists}")
    if edge_exists:
        # For DiGraph, edge data is stored in a dictionary keyed by an integer (usually 0 for the first edge)
        # or by a user-defined key if specified during add_edge.
        # If multiple edges can exist, graph.get_edge_data returns a dict of dicts.
        edge_data_dict = graph.get_edge_data(source_node_for_flow, target_node_for_flow)
        # Assuming only one edge for this test case or we are interested in the first one (key 0)
        # Or, if relationship_type was used as a key in a MultiDiGraph
        # For now, let's assume it's a simple DiGraph or the first edge.
        actual_edge_data = None
        if edge_data_dict:
            # Try to get the first edge's data; typically key 0 for simple graphs
            # or if multiple edges, find the one with 'potential_data_flow'
            for key, data in edge_data_dict.items():
                if data.get('type') == 'potential_data_flow': # Graph builder adds 'type' as relationship_type
                    actual_edge_data = data
                    break
                elif key == 0 and not actual_edge_data : # Fallback for simple DiGraph if type not set as key
                    actual_edge_data = data


        if actual_edge_data:
            print(f"    Edge attributes: {actual_edge_data}")
            assert actual_edge_data.get("flow_through_function_name") == "orchestrator_func"
            assert actual_edge_data.get("intermediate_variable") == "temp_data"
        else:
            print(f"    Could not retrieve specific edge data for data flow link between {source_node_for_flow} and {target_node_for_flow}")

    
    # C# DbContext class
    cs_dbcontext_id = kg._generate_node_id("csharp_class", dummy_cs_path, "AppDbContext")
    if cs_dbcontext_id in graph: print(f"  C# DbContext: {cs_dbcontext_id}, Attrs: {graph.nodes[cs_dbcontext_id]}")

    # K8s File node
    k8s_file_node = kg._generate_node_id("k8s_yaml_file", mock_k8s_file_path)
    if k8s_file_node in graph: print(f"  K8s File: {k8s_file_node}, Attrs: {graph.nodes[k8s_file_node]}")

    # K8s Deployment node
    k8s_deployment_node = kg._generate_node_id("k8s_resource", mock_k8s_file_path, "Deployment", "prod", "my-app")
    if k8s_deployment_node in graph:
        print(f"  K8s Deployment: {k8s_deployment_node}, Attrs: {graph.nodes[k8s_deployment_node]}")
        assert graph.nodes[k8s_deployment_node]['kind'] == 'Deployment'
        assert graph.nodes[k8s_deployment_node]['namespace'] == 'prod'
        assert 'app' in graph.nodes[k8s_deployment_node]['labels']
        assert len(graph.nodes[k8s_deployment_node]['containers']) == 3

    # K8s Service node
    k8s_service_node = kg._generate_node_id("k8s_resource", mock_k8s_file_path, "Service", "prod", "my-service")
    if k8s_service_node in graph:
        print(f"  K8s Service: {k8s_service_node}, Attrs: {graph.nodes[k8s_service_node]}")
        assert graph.nodes[k8s_service_node]['selector']['app'] == 'my-app'

    # Docker Image nodes
    image_node1 = kg._generate_node_id("docker_image::myimage:1.2.3")
    if image_node1 in graph:
        print(f"  Docker Image 1: {image_node1}, Attrs: {graph.nodes[image_node1]}")
        assert graph.nodes[image_node1]['image_tag'] == '1.2.3'
        assert graph.has_edge(k8s_deployment_node, image_node1)
        assert graph.edges[(k8s_deployment_node, image_node1, 0)]['container_name'] == 'main'
        
    image_node2 = kg._generate_node_id("docker_image::myotherimage/side:latest")
    if image_node2 in graph:
        print(f"  Docker Image 2: {image_node2}, Attrs: {graph.nodes[image_node2]}")
        assert graph.nodes[image_node2]['image_tag'] == 'latest'
        assert graph.has_edge(k8s_deployment_node, image_node2)

    image_node3 = kg._generate_node_id("docker_image::busybox") # No tag
    if image_node3 in graph:
        print(f"  Docker Image 3 (no tag): {image_node3}, Attrs: {graph.nodes[image_node3]}")
        assert graph.nodes[image_node3]['image_tag'] == 'latest' # Defaulted
        assert graph.has_edge(k8s_deployment_node, image_node3)

    # Check edge from file to resource
    if graph.has_edge(k8s_file_node, k8s_deployment_node):
        print(f"  Edge from K8s file to Deployment: {k8s_file_node} -> {k8s_deployment_node}")
        assert graph.edges[(k8s_file_node, k8s_deployment_node, 0)]['type'] == 'defines_k8s_resource'


    # Clean up dummy files and directories
    import shutil
    try:
        shutil.rmtree(mock_codebase_path)
        logging.info(f"Cleaned up dummy directory: {mock_codebase_path}")
    except OSError as e:
        logging.error(f"Error cleaning up dummy directory {mock_codebase_path}: {e}")
