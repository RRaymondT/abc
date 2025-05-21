# This module will be responsible for building the knowledge graph.

import networkx
import logging
import os # For path operations in example

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
            # Normalize module names that might be relative like '.module.sub'
            # For now, treat them as potentially global, but this could be refined
            # if we have information about the project's root and structure.
            clean_mod_name = mod_name.lstrip('.') 
            mod_node_id = self._generate_node_id("module", clean_mod_name)
            self.add_node(mod_node_id, node_type="python_module", name=clean_mod_name)
            self.add_edge(file_node_id, mod_node_id, relationship_type="imports")

        # Process classes
        for cls_data in parsed_data.get('classes', []):
            class_name = cls_data['name']
            class_node_id = self._generate_node_id("class", file_path, class_name)
            self.add_node(class_node_id, node_type="class", name=class_name,
                          base_classes=cls_data.get('base_classes', []), file_path=file_path)
            self.add_edge(file_node_id, class_node_id, relationship_type="defines_class")

            # Process methods
            for m_data in cls_data.get('methods', []):
                method_name = m_data['name']
                method_node_id = self._generate_node_id("method", file_path, class_name, method_name)
                self.add_node(method_node_id, node_type="method", name=method_name,
                              parameters=m_data.get('parameters', []), class_name=class_name, file_path=file_path)
                self.add_edge(class_node_id, method_node_id, relationship_type="defines_method")

                # Process calls within methods
                for call_target_str in m_data.get('calls', []):
                    # Attempt to determine if the call is to another method in the same class,
                    # a function in the same file, or an external entity.
                    # This is a simplification; real resolution is complex.
                    target_node_id = self._generate_node_id("callable", call_target_str) # Simplified ID
                    # Node type 'callable_entity' is generic. If we can resolve it better, we'd update type.
                    self.add_node(target_node_id, node_type="callable_entity", name=call_target_str, inferred=True)
                    self.add_edge(method_node_id, target_node_id, relationship_type="calls")

        # Process functions
        for func_data in parsed_data.get('functions', []):
            func_name = func_data['name']
            func_node_id = self._generate_node_id("function", file_path, func_name)
            self.add_node(func_node_id, node_type="function", name=func_name,
                          parameters=func_data.get('parameters', []), file_path=file_path)
            self.add_edge(file_node_id, func_node_id, relationship_type="defines_function")

            # Process calls within functions
            for call_target_str in func_data.get('calls', []):
                target_node_id = self._generate_node_id("callable", call_target_str) # Simplified ID
                self.add_node(target_node_id, node_type="callable_entity", name=call_target_str, inferred=True)
                self.add_edge(func_node_id, target_node_id, relationship_type="calls")

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
        if not file_path:
            logging.warning("file_analysis_result is missing 'file_path'. Skipping.")
            return

        logging.info(f"Processing parsed data for file: {file_path}")

        # Determine parser type based on unique keys
        if 'classes' in file_analysis_result or 'functions' in file_analysis_result: # Python specific keys
            self.process_python_parsed_data(file_analysis_result, file_path)
        elif 'processes' in file_analysis_result or 'service_tasks' in file_analysis_result: # BPMN specific keys
            self.process_bpmn_parsed_data(file_analysis_result, file_path)
        else:
            logging.warning(f"Unknown parsed data structure for {file_path}. No specific processor found.")


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
            for file_path, parsed_data_for_file in all_parsed_data.items():
                if parsed_data_for_file: # Ensure there's data to process
                    self.process_parsed_file_data(parsed_data_for_file)
                else:
                    # If a file was identified (e.g. by tech scanner) but not parsed or parsing failed,
                    # ensure a basic file node exists.
                    logging.debug(f"No parsed data for {file_path}, ensuring basic file node exists.")
                    file_node_id = self._generate_node_id("file", file_path)
                    self.add_node(file_node_id, node_type="file", path=file_path, name=os.path.basename(file_path))
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
    # For Python file (user_service.py)
    mock_python_parsed = {
        "file_path": dummy_py_path,
        "imports": ["flask"],
        "classes": [{
            "name": "UserService",
            "base_classes": [],
            "methods": [{
                "name": "get_user",
                "parameters": ["self", "id"],
                "calls": ["flask.jsonify"]
            }]
        }],
        "functions": [{
            "name": "process_data",
            "parameters": [],
            "calls": ["print"]
        }]
    }

    # For BPMN file (order_process.bpmn)
    mock_bpmn_parsed = {
        "file_path": dummy_bpmn_path,
        "processes": [{
            "id": "OrderProcess", 
            "name": "Order Fulfillment"
        }],
        "service_tasks": [{
            "id": "Task_EmailCustomer", 
            "name": "Email Customer",
            "camunda_class": "com.example.EmailDelegate"
            # 'camunda_delegateExpression' or 'camunda_expression' could also be here
        }],
        "user_tasks": [] # No user tasks in this simple example
    }
    
    # Aggregate parsed data as if collected by the main application
    mock_all_parsed_data = {
        dummy_py_path: mock_python_parsed,
        dummy_bpmn_path: mock_bpmn_parsed,
        dummy_pom_path: None # pom.xml might be identified by tech_scanner but not parsed by code_parser
    }

    # --- Instantiate and Use KnowledgeGraph ---
    kg = KnowledgeGraph()

    # Load data into the graph
    kg.load_graph_from_directory(mock_codebase_path, mock_tech_scan_results, mock_all_parsed_data)

    # --- Print Graph Info ---
    graph = kg.get_graph()
    print(f"\n--- Knowledge Graph Built ---")
    print(f"Number of nodes: {graph.number_of_nodes()}")
    print(f"Number of edges: {graph.number_of_edges()}")

    print("\nNodes (first 20):")
    for i, (node_id, data) in enumerate(graph.nodes(data=True)):
        if i >= 20:
            print("...")
            break
        print(f"  ID: {node_id}, Type: {data.get('type')}, Name: {data.get('name')}, Path: {data.get('path')}")
        # Print other relevant attributes based on node type if needed for verification
        if data.get('type') == 'class':
            print(f"    Base Classes: {data.get('base_classes')}")
        if data.get('type') == 'method' or data.get('type') == 'function':
            print(f"    Parameters: {data.get('parameters')}")
        if data.get('type') == 'bpmn_service_task':
            print(f"    Implementation: {data.get('camunda_class') or data.get('camunda_delegateExpression') or data.get('camunda_expression')}")


    print("\nEdges (first 20):")
    for i, (u, v, data) in enumerate(graph.edges(data=True)):
        if i >= 20:
            print("...")
            break
        print(f"  From: {u} --[{data.get('type')}]--> To: {v}")

    # Example of how to find specific nodes or relationships (manual verification)
    print("\n--- Example Queries ---")
    # Find the Python file node
    py_file_node = kg._generate_node_id("file", dummy_py_path)
    if py_file_node in graph:
        print(f"Python file node '{py_file_node}' found.")
        print(f"  Neighbors of Python file: {list(graph.neighbors(py_file_node))}")
    
    # Find the Camunda technology node
    camunda_tech_node = kg._generate_node_id("tech_reference", "camunda")
    if camunda_tech_node in graph:
        print(f"Camunda tech reference node '{camunda_tech_node}' found.")
        print(f"  Files mentioning Camunda: {list(graph.predecessors(camunda_tech_node))}")

    # Clean up dummy files and directories (optional, good for repeated testing)
    import shutil
    try:
        shutil.rmtree(mock_codebase_path)
        logging.info(f"Cleaned up dummy directory: {mock_codebase_path}")
    except OSError as e:
        logging.error(f"Error cleaning up dummy directory {mock_codebase_path}: {e}")

# Placeholder for __main__ example
