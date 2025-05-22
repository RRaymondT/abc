# This module will be responsible for exporting the knowledge graph data for LLM consumption.

import networkx
import logging
import os # Required for path prefix in example

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Attributes to skip in the main node details section as they are complex or handled separately
SKIPPED_ATTRIBUTES = [
    'graph', 'nodes', 'edges', 'type', 'name', 'id', 'label', 'title', 'group', # Generic graph/viz related
    'decorators', 'attributes', # Python decorators, C# attributes (when list of strings)
    'base_types_str', 'return_type', 'parameters_str', # C# specific string fields handled customly
    'script_lang', 'style_lang', # Vue specific fields handled customly
    'parent_entity_name', # Often redundant as relationship implies it
    'file_path' # Redundant if node is already associated with a file node in output
]
# Note: C# property 'type' is deliberately NOT in SKIPPED_ATTRIBUTES if not specially formatted,
# to allow it to be caught by the general attribute loop if 'type_str' for C# properties isn't used.
# However, the custom formatting prefers 'type_str' for C# properties.

PRIMARY_NODE_TYPES = [
    'python_file', 'class', 'method', 'function', 
    'bpmn_file', 'bpmn_process', 'bpmn_service_task', 'bpmn_user_task',
    'codebase',
    'csharp_file',
    'csharp_class',
    'csharp_interface',
    'csharp_method',
    'csharp_property',
    'csharp_namespace',
    'vue_component_file',
    'vue_component',
    'vue_prop',
    'vue_method',
    'vue_data_property',
    'vue_computed_property'
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

    # --- Custom Formatting for Specific Node Types ---
    node_type = node_attrs.get('type', '')

    # Python Decorators
    if node_attrs.get('decorators') and isinstance(node_attrs['decorators'], list) and node_attrs['decorators']:
        decorators_str = ", ".join([f"`{d}`" for d in node_attrs['decorators']])
        parts.append(f"**Decorators:** {decorators_str}")

    # C# Specific Attributes
    if node_type.startswith('csharp_'):
        # C# Attributes (for classes, interfaces, methods, properties)
        if node_attrs.get('attributes') and isinstance(node_attrs['attributes'], list) and node_attrs['attributes']:
            cs_attributes_str = ", ".join([f"`{a}`" for a in node_attrs['attributes']])
            parts.append(f"**C# Attributes:** {cs_attributes_str}")

        if node_type in ['csharp_class', 'csharp_interface']:
            if node_attrs.get('namespace'):
                parts.append(f"**Namespace:** `{node_attrs['namespace']}`")
            if node_attrs.get('base_types_str'):
                parts.append(f"**Base Types:** `{node_attrs['base_types_str']}`")
        elif node_type == 'csharp_method':
            # Using 'return_type' as this is what the C# parser is designed to produce.
            if node_attrs.get('return_type'): 
                parts.append(f"**Return Type:** `{node_attrs['return_type']}`")
            if node_attrs.get('parameters_str'):
                parts.append(f"**Parameters:** `{node_attrs['parameters_str']}`")
        elif node_type == 'csharp_property':
            # Using 'type' as this is what the C# parser is designed to produce for property type.
            if node_attrs.get('type'): 
                 parts.append(f"**Type:** `{node_attrs['type']}`")


    # Vue.js Specific Attributes
    if node_type == 'vue_component':
        if node_attrs.get('script_lang'):
            parts.append(f"**Script Language:** `{node_attrs['script_lang']}`")
        if node_attrs.get('style_lang'):
            parts.append(f"**Style Language:** `{node_attrs['style_lang']}`")

    # --- General Attributes ---
    parts.append("\n**Other Details:**") 
    general_details_added = False
    for key, value in sorted(node_attrs.items()):
        if key in SKIPPED_ATTRIBUTES or value is None:
            continue
        if isinstance(value, (str, list, dict)) and len(str(value)) > 250: 
            parts.append(f"- **{key.replace('_', ' ').capitalize()}:** `(Omitted due to length)`")
            general_details_added = True
        else:
            if isinstance(value, list):
                if not value: continue 
                display_value = ", ".join(map(str, value))
            else:
                display_value = str(value)
            if display_value.strip() == "": continue # Skip empty string values after potential processing
            parts.append(f"- **{key.replace('_', ' ').capitalize()}:** `{display_value}`")
            general_details_added = True
    
    if not general_details_added:
        parts[-1] = "**Other Details:** None." 


    # Outgoing Relationships (Dependencies)
    parts.append("\n**Dependencies (Connects To):**")
    out_edges = list(graph.out_edges(node_id, data=True))
    if out_edges:
        for _, target, edge_attrs in out_edges: 
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
        for source, _, edge_attrs in in_edges: 
            source_attrs = graph.nodes.get(source, {})
            source_name = source_attrs.get('name', source)
            source_type = source_attrs.get('type', 'Unknown')
            edge_type = edge_attrs.get('type', 'related to')
            parts.append(f"- `{edge_type}` **`{source_name}`** (Type: `{source_type}`, ID: `{source}`)")
    else:
        parts.append("  None.")
    
    parts.append("\n---\n") 
    return "\n".join(parts)

def export_graph_to_markdown(graph: networkx.DiGraph, main_project_entities_only=True, codebase_path_prefix=None) -> str:
    markdown_parts = ["# Knowledge Graph Summary\n"]
    codebase_nodes_ids = [n_id for n_id, attrs in graph.nodes(data=True) if attrs.get('type') == 'codebase']
    if codebase_nodes_ids:
        cb_attrs = graph.nodes[codebase_nodes_ids[0]]
        markdown_parts.append(f"## Codebase Information:\n")
        markdown_parts.append(f"- **Name:** {cb_attrs.get('name', codebase_nodes_ids[0])}\n")
        markdown_parts.append(f"- **Path:** `{cb_attrs.get('path', 'N/A')}`\n")

    tech_nodes_ids = [
        n_id for n_id, attrs in graph.nodes(data=True) 
        if attrs.get('type') in ['build_system_or_framework', 'technology_reference', 'project_file']
    ]
    
    if tech_nodes_ids:
        markdown_parts.append("## Detected Technologies & Project Files:\n")
        for tn_id in sorted(tech_nodes_ids): 
            tn_attrs = graph.nodes[tn_id]
            path_info = ""
            if tn_attrs.get('path') and tn_attrs.get('path') != 'N/A': 
                path_info = f", Path: `{tn_attrs.get('path')}`"
            markdown_parts.append(f"- **{tn_attrs.get('name', tn_id)}** (Type: `{tn_attrs.get('type')}`{path_info})\n")

    markdown_parts.append("\n## Key Code Entities:\n")
    sorted_node_ids = sorted(list(graph.nodes())) 
    processed_nodes_count = 0

    for node_id in sorted_node_ids:
        attrs = graph.nodes[node_id]
        node_type = attrs.get('type')

        if node_type in ['build_system_or_framework', 'technology_reference', 'project_file', 'codebase']:
            continue

        if main_project_entities_only:
            if node_type not in PRIMARY_NODE_TYPES:
                continue
            # Path filtering: ensure 'path' attribute exists and is a string before calling startswith
            node_path_attr = attrs.get('path')
            if codebase_path_prefix and node_path_attr is not None:
                if not str(node_path_attr).startswith(codebase_path_prefix):
                    continue
            elif codebase_path_prefix and node_path_attr is None: # If prefix is specified, nodes without path are excluded
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

    return "".join(markdown_parts)


if __name__ == '__main__':
    sample_graph = networkx.DiGraph()
    test_codebase_prefix = "/app/project_alpha/" # Used to simulate a project root

    # Codebase node
    sample_graph.add_node("codebase::" + test_codebase_prefix, name="Project Alpha", type="codebase", path=test_codebase_prefix)
    
    # --- Python Nodes (including decorators) ---
    py_file_id = "python_file::" + test_codebase_prefix + "src/main.py"
    sample_graph.add_node(py_file_id, name="main.py", type="python_file", path=test_codebase_prefix + "src/main.py")

    py_class_id = "class::" + test_codebase_prefix + "src/main.py::AppController"
    sample_graph.add_node(py_class_id, name="AppController", type="class", 
                          decorators=['@Controller("/api")', '@Singleton'], 
                          file_path=test_codebase_prefix + "src/main.py") # Ensure path for filtering
    sample_graph.add_edge(py_file_id, py_class_id, type="defines_class")

    py_method_id = "method::" + test_codebase_prefix + "src/main.py::AppController::handle_request"
    sample_graph.add_node(py_method_id, name="handle_request", type="method", 
                          decorators=['@Get("/:id")', '@Authenticated'], 
                          parameters=['req', 'res'], 
                          class_name="AppController", file_path=test_codebase_prefix + "src/main.py")
    sample_graph.add_edge(py_class_id, py_method_id, type="defines_method")

    # --- C# Nodes ---
    cs_file_path = test_codebase_prefix + "services/UserService.cs"
    cs_file_id = "csharp_file::" + cs_file_path
    sample_graph.add_node(cs_file_id, name="UserService.cs", type="csharp_file", path=cs_file_path)

    cs_ns_id = "csharp_namespace::MyCompany.Services"
    # Add path to namespace for it to be included if it's a primary entity and path filtering is active
    sample_graph.add_node(cs_ns_id, name="MyCompany.Services", type="csharp_namespace", path=cs_file_path) 
    sample_graph.add_edge(cs_file_id, cs_ns_id, type="defines_namespace")

    cs_class_id = "csharp_class::" + cs_file_path + "::UserService"
    sample_graph.add_node(cs_class_id, name="UserService", type="csharp_class", 
                          namespace="MyCompany.Services", 
                          attributes=['Serializable', 'DataContract'], 
                          base_types_str="BaseService, IUserService",
                          file_path=cs_file_path) 
    sample_graph.add_edge(cs_ns_id, cs_class_id, type="contains_entity") 
    sample_graph.add_edge(cs_file_id, cs_class_id, type="defines_class") 

    cs_method_id = "csharp_method::" + cs_file_path + "::UserService::GetUser"
    sample_graph.add_node(cs_method_id, name="GetUser", type="csharp_method", 
                          attributes=['HttpGet("api/users/{userId}")'], 
                          return_type="User", # Parser provides 'return_type'
                          parameters_str="int userId",
                          parent_entity_name="UserService", file_path=cs_file_path, 
                          namespace="MyCompany.Services") 
    sample_graph.add_edge(cs_class_id, cs_method_id, type="defines_method")

    cs_prop_id = "csharp_property::" + cs_file_path + "::UserService::MaxUsers"
    sample_graph.add_node(cs_prop_id, name="MaxUsers", type="csharp_property",
                          attributes=['DataMember'],
                          type="int", # Parser provides 'type'
                          parent_entity_name="UserService", file_path=cs_file_path, 
                          namespace="MyCompany.Services") 
    sample_graph.add_edge(cs_class_id, cs_prop_id, type="defines_property")

    # --- Vue.js Nodes ---
    vue_file_path = test_codebase_prefix + "components/Login.vue"
    vue_file_id = "vue_component_file::" + vue_file_path
    sample_graph.add_node(vue_file_id, name="Login.vue", type="vue_component_file", path=vue_file_path)

    vue_comp_id = "vue_component::" + vue_file_path + "::Login" 
    sample_graph.add_node(vue_comp_id, name="Login", type="vue_component",
                          script_lang='ts', style_lang='scss', file_path=vue_file_path)
    sample_graph.add_edge(vue_file_id, vue_comp_id, type="defines_component")
    
    vue_prop_id = "vue_prop::" + vue_file_path + "::Login::username" 
    sample_graph.add_node(vue_prop_id, name="username", type="vue_prop", component_name="Login", file_path=vue_file_path)
    sample_graph.add_edge(vue_comp_id, vue_prop_id, type="has_prop")

    vue_method_id = "vue_method::" + vue_file_path + "::Login::doLogin" 
    sample_graph.add_node(vue_method_id, name="doLogin", type="vue_method", component_name="Login", file_path=vue_file_path)
    sample_graph.add_edge(vue_comp_id, vue_method_id, type="has_method")

    logging.info("Extended sample graph created for LLM export testing.")
    
    print("\n--- Markdown Export (Extended Graph - Main Project Entities, Filtered by Path Prefix) ---")
    markdown_output_extended_filtered = export_graph_to_markdown(
        sample_graph,
        main_project_entities_only=True,
        codebase_path_prefix=test_codebase_prefix
    )
    print(markdown_output_extended_filtered)

    # Test case for empty graph or no matching entities
    empty_graph_for_filter_test = networkx.DiGraph()
    empty_graph_for_filter_test.add_node("codebase::/app/other_project", name="Other Project", type="codebase", path="/app/other_project/")
    empty_graph_for_filter_test.add_node("python_file::/app/other_project/lib.py", name="lib.py", type="python_file", path="/app/other_project/lib.py")
    print("\n--- Markdown Export (Empty Graph - Main Project Entities Only, Filtered - Expect No Key Entities) ---")
    markdown_empty_filtered = export_graph_to_markdown(empty_graph_for_filter_test,
                                                       main_project_entities_only=True,
                                                       codebase_path_prefix="/app/specific_project/")
    print(markdown_empty_filtered)
