# This module will be responsible for exporting the knowledge graph data for LLM consumption.

import networkx
import logging
import os # Required for path prefix in example

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Attributes to skip in the main node details section as they are complex or handled separately
SKIPPED_ATTRIBUTES = ['graph', 'nodes', 'edges', 'type', 'name', 'id', 'label', 'title', 'group'] 

PRIMARY_NODE_TYPES = [
    'python_file', 'class', 'method', 'function', 
    'bpmn_file', 'bpmn_process', 'bpmn_service_task', 'bpmn_user_task',
    'codebase' 
]

def format_node_for_llm(graph: networkx.DiGraph, node_id: str, node_attrs: dict) -> str:
    """
    Formats a single node from the graph into a Markdown string.

    Args:
        graph: The NetworkX DiGraph object.
        node_id: The ID of the node to format.
        node_attrs: The attributes dictionary of the node.

    Returns:
        A Markdown formatted string representing the node.
    """
    parts = []
    node_type_display = node_attrs.get('type', 'Entity')
    node_name_display = node_attrs.get('name', node_id)
    
    parts.append(f"### {node_type_display}: {node_name_display}")
    parts.append(f"**ID:** `{node_id}`")

    # Key Attributes
    for key, value in sorted(node_attrs.items()):
        if key in SKIPPED_ATTRIBUTES or value is None:
            continue
        # Simple heuristic to skip very long values
        if isinstance(value, (str, list, dict)) and len(str(value)) > 250: 
            parts.append(f"**{key.replace('_', ' ').capitalize()}:** `(Omitted due to length)`")
        else:
            parts.append(f"**{key.replace('_', ' ').capitalize()}:** `{value}`")

    # Outgoing Relationships (Dependencies)
    parts.append("\n**Dependencies (Connects To):**")
    out_edges = list(graph.out_edges(node_id, data=True))
    if out_edges:
        for _, target, edge_attrs in out_edges: # Source is always node_id here
            target_attrs = graph.nodes.get(target, {})
            target_name = target_attrs.get('name', target)
            target_type = target_attrs.get('type', 'Unknown')
            edge_type = edge_attrs.get('type', 'related to')
            parts.append(f"- `{edge_type}` **`{target_name}`** (Type: `{target_type}`, ID: `{target}`)")
    else:
        parts.append("  None.")

    # Incoming Relationships (Dependents)
    parts.append("\n**Dependents (Connections From):**")
    in_edges = list(graph.in_edges(node_id, data=True))
    if in_edges:
        for source, _, edge_attrs in in_edges: # Target is always node_id here
            source_attrs = graph.nodes.get(source, {})
            source_name = source_attrs.get('name', source)
            source_type = source_attrs.get('type', 'Unknown')
            edge_type = edge_attrs.get('type', 'related to')
            parts.append(f"- `{edge_type}` **`{source_name}`** (Type: `{source_type}`, ID: `{source}`)")
    else:
        parts.append("  None.")
    
    parts.append("\n---\n") # Separator for nodes
    return "\n".join(parts)

def export_graph_to_markdown(graph: networkx.DiGraph, main_project_entities_only=True, codebase_path_prefix=None) -> str:
    """
    Exports the entire knowledge graph to a Markdown formatted string.

    Args:
        graph: The NetworkX DiGraph object.
        main_project_entities_only: If True, only formats nodes of PRIMARY_NODE_TYPES
                                    and optionally filters by codebase_path_prefix.
        codebase_path_prefix: If provided, and main_project_entities_only is True,
                              only includes nodes whose 'path' attribute starts with this prefix.

    Returns:
        A string containing the Markdown representation of the graph.
    """
    markdown_parts = ["# Knowledge Graph Summary\n"]

    # Codebase node summary (if exists)
    codebase_nodes_ids = [n_id for n_id, attrs in graph.nodes(data=True) if attrs.get('type') == 'codebase']
    if codebase_nodes_ids:
        # Assuming one codebase node for simplicity, or you might loop/select
        cb_attrs = graph.nodes[codebase_nodes_ids[0]]
        markdown_parts.append(f"## Codebase Information:\n")
        markdown_parts.append(f"- **Name:** {cb_attrs.get('name', codebase_nodes_ids[0])}\n")
        markdown_parts.append(f"- **Path:** `{cb_attrs.get('path', 'N/A')}`\n")

    # Technology and Project File Summary
    tech_nodes_ids = [
        n_id for n_id, attrs in graph.nodes(data=True) 
        if attrs.get('type') in ['build_system_or_framework', 'technology_reference', 'project_file']
    ]
    
    if tech_nodes_ids:
        markdown_parts.append("## Detected Technologies & Project Files:\n")
        for tn_id in sorted(tech_nodes_ids): # Sort for consistent output
            tn_attrs = graph.nodes[tn_id]
            path_info = ""
            if tn_attrs.get('path') and tn_attrs.get('path') != 'N/A': # Check if path exists and is not 'N/A'
                path_info = f", Path: `{tn_attrs.get('path')}`"
            markdown_parts.append(f"- **{tn_attrs.get('name', tn_id)}** (Type: `{tn_attrs.get('type')}`{path_info})\n")

    # Detailed Entity Summaries
    markdown_parts.append("\n## Key Code Entities:\n")
    
    sorted_node_ids = sorted(list(graph.nodes())) 
    processed_nodes_count = 0

    for node_id in sorted_node_ids:
        attrs = graph.nodes[node_id]
        node_type = attrs.get('type')

        # Skip tech/project file nodes here as they are summarized above
        if node_type in ['build_system_or_framework', 'technology_reference', 'project_file', 'codebase']:
            continue

        if main_project_entities_only:
            if node_type not in PRIMARY_NODE_TYPES:
                continue
            if codebase_path_prefix and 'path' in attrs and attrs['path'] is not None:
                node_path_str = str(attrs['path']) # Ensure path is string
                if not node_path_str.startswith(codebase_path_prefix):
                    continue
        
        markdown_parts.append(format_node_for_llm(graph, node_id, attrs))
        processed_nodes_count +=1
    
    if processed_nodes_count == 0:
        if main_project_entities_only and codebase_path_prefix:
             markdown_parts.append("No primary project entities found matching the specified codebase path prefix.\n")
        elif main_project_entities_only:
             markdown_parts.append("No primary project entities found in the graph.\n")
        else:
             markdown_parts.append("No entities found in the graph to detail.\n")

    return "".join(markdown_parts) # format_node_for_llm adds \n and ---, so direct join is okay.


if __name__ == '__main__':
    sample_graph = networkx.DiGraph()
    test_codebase_prefix = "/app/project_alpha/"

    # Codebase node
    sample_graph.add_node("codebase::/app/project_alpha", name="Project Alpha", type="codebase", path=test_codebase_prefix)
    
    # Project files / Tech
    sample_graph.add_node("file::" + test_codebase_prefix + "pom.xml", name="pom.xml", type="project_file", path=test_codebase_prefix + "pom.xml")
    sample_graph.add_node("tech::maven", name="Maven", type="build_system_or_framework") # No path for abstract tech
    sample_graph.add_node("tech_ref::camunda", name="Camunda", type="technology_reference") # No path for abstract tech

    # Python file within the project
    py_file_id = "python_file::" + test_codebase_prefix + "src/main.py"
    sample_graph.add_node(py_file_id, name="main.py", type="python_file", path=test_codebase_prefix + "src/main.py", lines=150)

    class_id = "class::" + test_codebase_prefix + "src/main.py::AppController"
    sample_graph.add_node(class_id, name="AppController", type="class", file_path=py_file_id, base_classes=["BaseController"])

    method_id = "method::" + test_codebase_prefix + "src/main.py::AppController::handle_request"
    sample_graph.add_node(method_id, name="handle_request", type="method", class_name="AppController", parameters=["req", "res"], file_path=py_file_id)

    func_id = "function::" + test_codebase_prefix + "src/main.py::utility_func"
    sample_graph.add_node(func_id, name="utility_func", type="function", parameters=["data"], file_path=py_file_id)

    bpmn_file_id = "bpmn_file::" + test_codebase_prefix + "resources/process.bpmn"
    sample_graph.add_node(bpmn_file_id, name="process.bpmn", type="bpmn_file", path=test_codebase_prefix + "resources/process.bpmn")

    bpmn_process_id = "bpmn_process::" + test_codebase_prefix + "resources/process.bpmn::OrderProcess"
    sample_graph.add_node(bpmn_process_id, name="OrderProcess", type="bpmn_process", process_id_attr="OrderProcessV1", file_path=bpmn_file_id)

    bpmn_task_id = "bpmn_service_task::" + test_codebase_prefix + "resources/process.bpmn::EmailTask"
    sample_graph.add_node(bpmn_task_id, name="EmailTask", type="bpmn_service_task", camunda_class="com.example.EmailDelegate", file_path=bpmn_file_id)
    
    ext_module_id = "python_module::requests" # Not a primary type by default, and no path
    sample_graph.add_node(ext_module_id, name="requests", type="python_module", version="2.25.1")
    
    other_py_file_id = "python_file::/app/other_lib/utils.py" # Primary type, but outside prefix
    sample_graph.add_node(other_py_file_id, name="utils.py", type="python_file", path="/app/other_lib/utils.py")

    # Edges
    sample_graph.add_edge("codebase::/app/project_alpha", "file::" + test_codebase_prefix + "pom.xml", type="contains_project_file")
    sample_graph.add_edge("file::" + test_codebase_prefix + "pom.xml", "tech::maven", type="uses_technology_stack")
    
    sample_graph.add_edge(py_file_id, class_id, type="defines_class")
    sample_graph.add_edge(py_file_id, func_id, type="defines_function")
    sample_graph.add_edge(class_id, method_id, type="defines_method")
    sample_graph.add_edge(method_id, ext_module_id, type="calls_external") 
    sample_graph.add_edge(py_file_id, "tech_ref::camunda", type="mentions_technology") 

    sample_graph.add_edge(bpmn_file_id, bpmn_process_id, type="defines_process")
    sample_graph.add_edge(bpmn_process_id, bpmn_task_id, type="contains_task")
    
    java_delegate_id = "java_class::com.example.EmailDelegate"
    sample_graph.add_node(java_delegate_id, name="com.example.EmailDelegate", type="java_class", inferred=True) 
    sample_graph.add_edge(bpmn_task_id, java_delegate_id, type="implemented_by")

    logging.info("Sample graph created for LLM export testing.")

    print("\n--- Markdown Export (Main Project Entities Only, Filtered by Path Prefix) ---")
    markdown_output_filtered = export_graph_to_markdown(sample_graph, 
                                                        main_project_entities_only=True, 
                                                        codebase_path_prefix=test_codebase_prefix)
    print(markdown_output_filtered)

    print("\n--- Markdown Export (Main Project Entities Only, No Path Filter) ---")
    markdown_output_main_only_no_filter = export_graph_to_markdown(sample_graph, 
                                                                  main_project_entities_only=True, 
                                                                  codebase_path_prefix=None)
    print(markdown_output_main_only_no_filter)

    print("\n--- Markdown Export (All Entities, No Path Filter) ---")
    markdown_output_all = export_graph_to_markdown(sample_graph, 
                                                   main_project_entities_only=False, 
                                                   codebase_path_prefix=None) # Path filter not applicable if not main_project_entities_only
    print(markdown_output_all)
    
    # Test with a graph where the filter would result in no key entities
    empty_graph_for_filter_test = networkx.DiGraph()
    empty_graph_for_filter_test.add_node("codebase::/app/other_project", name="Other Project", type="codebase", path="/app/other_project/")
    empty_graph_for_filter_test.add_node("python_file::/app/other_project/lib.py", name="lib.py", type="python_file", path="/app/other_project/lib.py")
    print("\n--- Markdown Export (Main Project Entities Only, Filtered - Expect Only Codebase Summary & No Key Entities) ---")
    markdown_empty_filtered = export_graph_to_markdown(empty_graph_for_filter_test,
                                                       main_project_entities_only=True,
                                                       codebase_path_prefix="/app/specific_project/") # No entities should match this
    print(markdown_empty_filtered)
