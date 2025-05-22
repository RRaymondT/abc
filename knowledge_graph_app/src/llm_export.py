# This module will be responsible for exporting the knowledge graph data for LLM consumption.

import networkx
import logging
import os # Required for path prefix in example
import json # For K8s selector formatting

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Attributes to skip in the main node details section as they are complex or handled separately
SKIPPED_ATTRIBUTES = [
    'graph', 'nodes', 'edges', 'type', 'name', 'id', 'label', 'title', 'group', # Generic graph/viz related
    'decorators', 'attributes', # Python decorators, C# attributes (when list of strings)
    'base_types_str', 'return_type', 'parameters_str', # C# specific string fields handled customly
    'script_lang', 'style_lang', # Vue specific fields handled customly
    'parent_entity_name', # Often redundant as relationship implies it
    'file_path', # Redundant if node is already associated with a file node in output
    # K8s specific attributes that are custom formatted
    'containers', 'selector', 'data_keys', 
    # DB property attributes that are custom formatted
    'is_primary_key', 'is_required', 'max_length', 'column_name',
    # Docker image tag is custom formatted
    'image_tag'
]

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
    'vue_computed_property',
    # New DB and K8s types
    'db_entity', 
    'db_property',
    'k8s_yaml_file',
    'k8s_deployment', 
    'k8s_service',
    'k8s_configmap',
    'k8s_secret', 
    'k8s_statefulset',
    'k8s_job',
    'k8s_cronjob',
    'k8s_resource', # Generic fallback K8s resource
    'docker_image'
]

def format_node_for_llm(graph: networkx.DiGraph, node_id: str, node_attrs: dict) -> str:
    parts = []
    node_type_display = node_attrs.get('type', 'Entity')
    node_name_display = node_attrs.get('name', node_id)
    
    parts.append(f"### {node_type_display}: {node_name_display}")
    parts.append(f"**ID:** `{node_id}`")

    node_type = node_attrs.get('type', '')

    # Python Decorators
    if node_attrs.get('decorators') and isinstance(node_attrs['decorators'], list) and node_attrs['decorators']:
        decorators_str = ", ".join([f"`{d}`" for d in node_attrs['decorators']])
        parts.append(f"**Decorators:** {decorators_str}")

    # C# Specific Attributes
    if node_type.startswith('csharp_'):
        if node_attrs.get('attributes') and isinstance(node_attrs['attributes'], list) and node_attrs['attributes']:
            cs_attributes_str = ", ".join([f"`{a}`" for a in node_attrs['attributes']])
            parts.append(f"**C# Attributes:** {cs_attributes_str}")
        if node_type in ['csharp_class', 'csharp_interface']:
            if node_attrs.get('namespace'): parts.append(f"**Namespace:** `{node_attrs['namespace']}`")
            if node_attrs.get('base_types_str'): parts.append(f"**Base Types:** `{node_attrs['base_types_str']}`")
        elif node_type == 'csharp_method':
            if node_attrs.get('return_type'): parts.append(f"**Return Type:** `{node_attrs['return_type']}`")
            if node_attrs.get('parameters_str'): parts.append(f"**Parameters:** `{node_attrs['parameters_str']}`")
        elif node_type == 'csharp_property':
            if node_attrs.get('type'): parts.append(f"**Type:** `{node_attrs['type']}`")

    # Vue.js Specific Attributes
    if node_type == 'vue_component':
        if node_attrs.get('script_lang'): parts.append(f"**Script Language:** `{node_attrs['script_lang']}`")
        if node_attrs.get('style_lang'): parts.append(f"**Style Language:** `{node_attrs['style_lang']}`")

    # DB Entity
    if node_type == 'db_entity':
        if node_attrs.get('defined_in_dbcontext'): parts.append(f"**Defined in DbContext:** `{node_attrs['defined_in_dbcontext']}`")

    # DB Property
    if node_type == 'db_property':
        if node_attrs.get('is_primary_key'): parts.append(f"**Is Primary Key:** True")
        if node_attrs.get('is_required') is not None: parts.append(f"**Is Required:** {node_attrs['is_required']}")
        if node_attrs.get('max_length'): parts.append(f"**Max Length:** {node_attrs['max_length']}")
        if node_attrs.get('column_name'): parts.append(f"**Column Name:** `{node_attrs['column_name']}`")
        # General 'type' or 'property_type' for db_property will be caught by the general loop if not skipped.

    # Kubernetes Resources
    if node_type.startswith('k8s_'):
        if node_attrs.get('containers') and isinstance(node_attrs['containers'], list):
            parts.append(f"**Containers:**")
            for c in node_attrs['containers']:
                container_name = c.get('name', 'Unnamed')
                image = c.get('image', 'Not specified')
                ports_str = ""
                if c.get('ports') and isinstance(c.get('ports'), list):
                    ports_list = [str(p.get('containerPort')) for p in c.get('ports') if p.get('containerPort')]
                    if ports_list: ports_str = f", Ports: {', '.join(ports_list)}"
                parts.append(f"  - Name: `{container_name}`, Image: `{image}`{ports_str}")
        if node_attrs.get('service_type'): parts.append(f"**Service Type:** `{node_attrs['service_type']}`")
        if node_attrs.get('selector') and isinstance(node_attrs['selector'], dict):
            try: parts.append(f"**Selector:** `{json.dumps(node_attrs['selector'])}`")
            except TypeError: parts.append(f"**Selector:** `(Contains non-serializable data)`")
        if node_attrs.get('data_keys') and isinstance(node_attrs['data_keys'], list):
            parts.append(f"**Data Keys:** {', '.join([f'`{k}`' for k in node_attrs['data_keys']])}")

    # Docker Image
    if node_type == 'docker_image':
        if node_attrs.get('image_tag'): parts.append(f"**Tag:** `{node_attrs['image_tag']}`")

    parts.append("\n**Other Details:**") 
    general_details_added = False
    for key, value in sorted(node_attrs.items()):
        if key in SKIPPED_ATTRIBUTES or value is None: continue
        if isinstance(value, (str, list, dict)) and len(str(value)) > 250: 
            parts.append(f"- **{key.replace('_', ' ').capitalize()}:** `(Omitted due to length)`"); general_details_added = True
        else:
            display_value = ", ".join(map(str, value)) if isinstance(value, list) and value else str(value)
            if isinstance(value, list) and not value: continue # Skip empty lists from general display
            if display_value.strip() == "": continue
            parts.append(f"- **{key.replace('_', ' ').capitalize()}:** `{display_value}`"); general_details_added = True
    if not general_details_added: parts[-1] = "**Other Details:** None." 

    parts.append("\n**Dependencies (Connects To):**")
    out_edges = list(graph.out_edges(node_id, data=True))
    if out_edges:
        for _, target, edge_attrs in out_edges: 
            target_node_attrs = graph.nodes.get(target, {})
            target_name = target_node_attrs.get('name', target)
            target_type = target_node_attrs.get('type', 'Unknown')
            edge_type = edge_attrs.get('type', 'related to')
            edge_details = {k:v for k,v in edge_attrs.items() if k != 'type'}
            details_str = f" (Details: {json.dumps(edge_details, default=str)})" if edge_details else ""
            parts.append(f"- `{edge_type}` **`{target_name}`** (Type: `{target_type}`, ID: `{target}`){details_str}")
    else: parts.append("  None.")

    parts.append("\n**Dependents (Connections From):**")
    in_edges = list(graph.in_edges(node_id, data=True))
    if in_edges:
        for source, _, edge_attrs in in_edges: 
            source_node_attrs = graph.nodes.get(source, {})
            source_name = source_node_attrs.get('name', source)
            source_type = source_node_attrs.get('type', 'Unknown')
            edge_type = edge_attrs.get('type', 'related to')
            edge_details = {k:v for k,v in edge_attrs.items() if k != 'type'}
            details_str = f" (Details: {json.dumps(edge_details, default=str)})" if edge_details else ""
            parts.append(f"- `{edge_type}` **`{source_name}`** (Type: `{source_type}`, ID: `{source}`){details_str}")
    else: parts.append("  None.")
    
    parts.append("\n---\n") 
    return "\n".join(parts)

def export_graph_to_markdown(graph: networkx.DiGraph, main_project_entities_only=True, codebase_path_prefix=None) -> str:
    markdown_parts = ["# Knowledge Graph Summary\n"]
    codebase_nodes_ids = [n_id for n_id, attrs in graph.nodes(data=True) if attrs.get('type') == 'codebase']
    if codebase_nodes_ids:
        cb_attrs = graph.nodes[codebase_nodes_ids[0]]
        markdown_parts.append(f"## Codebase Information:\n- **Name:** {cb_attrs.get('name', codebase_nodes_ids[0])}\n- **Path:** `{cb_attrs.get('path', 'N/A')}`\n")

    tech_nodes_ids = [n_id for n_id, attrs in graph.nodes(data=True) if attrs.get('type') in ['build_system_or_framework', 'technology_reference', 'project_file']]
    if tech_nodes_ids:
        markdown_parts.append("## Detected Technologies & Project Files:\n")
        for tn_id in sorted(tech_nodes_ids): 
            tn_attrs = graph.nodes[tn_id]
            path_info = f", Path: `{tn_attrs.get('path')}`" if tn_attrs.get('path') and tn_attrs.get('path') != 'N/A' else ""
            markdown_parts.append(f"- **{tn_attrs.get('name', tn_id)}** (Type: `{tn_attrs.get('type')}`{path_info})\n")

    markdown_parts.append("\n## Key Code Entities:\n")
    sorted_node_ids = sorted(list(graph.nodes())) 
    processed_nodes_count = 0
    for node_id in sorted_node_ids:
        attrs = graph.nodes[node_id]
        node_type = attrs.get('type')
        if node_type in ['build_system_or_framework', 'technology_reference', 'project_file', 'codebase']: continue
        if main_project_entities_only:
            if node_type not in PRIMARY_NODE_TYPES: continue
            node_path_attr = attrs.get('path')
            if codebase_path_prefix and (node_path_attr is None or not str(node_path_attr).startswith(codebase_path_prefix)): continue
        markdown_parts.append(format_node_for_llm(graph, node_id, attrs)); processed_nodes_count +=1
    
    if processed_nodes_count == 0:
        message = "No primary project entities found"
        if main_project_entities_only and codebase_path_prefix: message += " matching the specified codebase path prefix."
        elif main_project_entities_only: message += " in the graph."
        else: message = "No entities found in the graph to detail."
        markdown_parts.append(message + "\n")
    return "".join(markdown_parts)

if __name__ == '__main__':
    sample_graph = networkx.DiGraph()
    test_codebase_prefix = "/app/project_alpha/"
    sample_graph.add_node("codebase::" + test_codebase_prefix, name="Project Alpha", type="codebase", path=test_codebase_prefix)
    
    # Python Nodes
    py_file_id = "python_file::" + test_codebase_prefix + "src/main.py"
    sample_graph.add_node(py_file_id, name="main.py", type="python_file", path=test_codebase_prefix + "src/main.py")
    py_class_id = "class::" + test_codebase_prefix + "src/main.py::AppController"
    sample_graph.add_node(py_class_id, name="AppController", type="class", decorators=['@Controller'], file_path=test_codebase_prefix + "src/main.py")
    sample_graph.add_edge(py_file_id, py_class_id, type="defines_class")
    py_method_id = "method::" + test_codebase_prefix + "src/main.py::AppController::handle_request"
    sample_graph.add_node(py_method_id, name="handle_request", type="method", decorators=['@Get'], parameters=['req'], class_name="AppController", file_path=test_codebase_prefix + "src/main.py")
    sample_graph.add_edge(py_class_id, py_method_id, type="defines_method")

    # C# Nodes (DbContext example)
    cs_file_path = test_codebase_prefix + "data/AppDbContext.cs"
    cs_file_id = "csharp_file::" + cs_file_path
    sample_graph.add_node(cs_file_id, name="AppDbContext.cs", type="csharp_file", path=cs_file_path)
    cs_dbcontext_id = "csharp_class::" + cs_file_path + "::AppDbContext"
    sample_graph.add_node(cs_dbcontext_id, name="AppDbContext", type="csharp_class", namespace="MyWebApp.Data", base_types_str="DbContext", is_dbcontext=True, file_path=cs_file_path)
    sample_graph.add_edge(cs_file_id, cs_dbcontext_id, type="defines_class")

    # DB Entity & Property Nodes
    db_entity_product_id = "db_entity::Product"
    sample_graph.add_node(db_entity_product_id, name="Product", type="db_entity", defined_in_dbcontext="AppDbContext", source_file=cs_file_path)
    sample_graph.add_edge(cs_dbcontext_id, db_entity_product_id, type="defines_db_entity_set", set_name="Products")
    db_prop_productid_id = "db_property::Product::ProductId" 
    sample_graph.add_node(db_prop_productid_id, name="ProductId", type="db_property", is_primary_key=True, entity_name="Product", property_type="int")
    sample_graph.add_edge(db_entity_product_id, db_prop_productid_id, type="has_primary_key_property")
    db_prop_name_id = "db_property::Product::Name"
    sample_graph.add_node(db_prop_name_id, name="Name", type="db_property", is_required=True, max_length=100, entity_name="Product", property_type="string")
    sample_graph.add_edge(db_entity_product_id, db_prop_name_id, type="has_property_configured")

    # Kubernetes Nodes
    k8s_yaml_path = test_codebase_prefix + "deploy/app.yaml"
    k8s_file_node_id = "k8s_yaml_file::" + k8s_yaml_path
    sample_graph.add_node(k8s_file_node_id, name="app.yaml", type="k8s_yaml_file", path=k8s_yaml_path)
    k8s_dep_id = "k8s_resource::" + k8s_yaml_path + "::Deployment::prod::my-app-dep"
    sample_graph.add_node(k8s_dep_id, name="my-app-dep", type="k8s_deployment", kind="Deployment", namespace="prod", labels={"app": "my-app"}, path=k8s_yaml_path, containers=[{'name': 'main-app', 'image': 'myrepo/my-app:v1.2.0', 'ports': [{'containerPort':80}]}])
    sample_graph.add_edge(k8s_file_node_id, k8s_dep_id, type="defines_k8s_resource")
    k8s_svc_id = "k8s_resource::" + k8s_yaml_path + "::Service::prod::my-app-svc"
    sample_graph.add_node(k8s_svc_id, name="my-app-svc", type="k8s_service", kind="Service", namespace="prod", service_type="LoadBalancer", selector={"app": "my-app"}, path=k8s_yaml_path)
    sample_graph.add_edge(k8s_file_node_id, k8s_svc_id, type="defines_k8s_resource")
    
    # Docker Image Node
    img_app_id = "docker_image::myrepo/my-app:v1.2.0"
    sample_graph.add_node(img_app_id, name="myrepo/my-app:v1.2.0", type="docker_image", image_tag="v1.2.0")
    sample_graph.add_edge(k8s_dep_id, img_app_id, type="uses_image", container_name="main-app")

    # Data Flow Edge
    source_func_id = "function::" + py_file_id + "::get_raw_data"
    sample_graph.add_node(source_func_id, name="get_raw_data", type="function", file_path=py_file_id)
    processing_func_id = "function::" + py_file_id + "::process_the_data"
    sample_graph.add_node(processing_func_id, name="process_the_data", type="function", file_path=py_file_id)
    sample_graph.add_edge(source_func_id, processing_func_id, type="potential_data_flow", flow_through_function_name="orchestrator_func", intermediate_variable="raw_data_var", arg_index=0)

    logging.info("Comprehensive sample graph created for LLM export testing.")
    print("\n--- Markdown Export (Comprehensive Graph - Main Project Entities, Filtered by Path Prefix) ---")
    markdown_output_extended_filtered = export_graph_to_markdown(sample_graph, main_project_entities_only=True, codebase_path_prefix=test_codebase_prefix)
    print(markdown_output_extended_filtered)

    # Test empty/filtered case
    empty_graph = networkx.DiGraph()
    empty_graph.add_node("codebase::/other", name="Other", type="codebase", path="/other/")
    print("\n--- Markdown Export (Empty Graph - Filtered) ---")
    print(export_graph_to_markdown(empty_graph, main_project_entities_only=True, codebase_path_prefix=test_codebase_prefix))
