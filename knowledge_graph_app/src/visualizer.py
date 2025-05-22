# This module will be responsible for visualizing the knowledge graph.

import json
import os
import logging
import networkx
from flask import Flask, jsonify, render_template

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Ensure the template folder is correctly specified relative to this file's location
# __file__ is the path to the current visualizer.py
# os.path.dirname(__file__) is the directory src/
# os.path.join(os.path.dirname(__file__), 'templates') is src/templates/
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

if not os.path.exists(TEMPLATE_DIR):
    logging.warning(f"Template directory {TEMPLATE_DIR} does not exist. Make sure it's created.")
    # If it's critical, you might want to raise an error or create it:
    # os.makedirs(TEMPLATE_DIR, exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATE_DIR)
GRAPH_DATA_GLOBAL = None

def export_graph_to_json(graph: networkx.DiGraph) -> dict:
    """
    Exports a NetworkX graph to a JSON-serializable dictionary format
    suitable for vis.js.

    Args:
        graph: The NetworkX DiGraph object.

    Returns:
        A dictionary with "nodes" and "edges" lists.
    """
    nodes_data = []
    for node_id, attrs in graph.nodes(data=True):
        node_dict = {
            "id": str(node_id),
            "label": str(attrs.get('name', node_id)), # Use name if present, else node_id
            "title": json.dumps(attrs, indent=2, default=str), # Tooltip with all attributes
            "group": str(attrs.get('type', 'unknown')), # For coloring/grouping by node type
        }
        # Include other simple, serializable attributes directly
        for key in ['path', 'value']: # Add other relevant keys if needed
            if key in attrs and (isinstance(attrs[key], (str, int, float, bool)) or attrs[key] is None):
                node_dict[key] = attrs[key]
        nodes_data.append(node_dict)

    edges_data = []
    for source, target, attrs in graph.edges(data=True):
        edge_dict = {
            "from": str(source),
            "to": str(target),
            "label": str(attrs.get('type', '')), # Relationship type
            "title": json.dumps(attrs, indent=2, default=str), # Tooltip with all attributes
            "arrows": "to" # Default for directed graph
        }
        edges_data.append(edge_dict)

    logging.info(f"Exported graph to JSON: {len(nodes_data)} nodes, {len(edges_data)} edges.")
    return {"nodes": nodes_data, "edges": edges_data}

@app.route('/')
def serve_index():
    """Serves the main HTML page for the visualization."""
    # Check if index.html exists
    index_html_path = os.path.join(app.template_folder, 'index.html')
    if not os.path.exists(index_html_path):
        logging.error(f"index.html not found at {index_html_path}")
        return "Error: index.html template not found.", 404
    return render_template('index.html')

@app.route('/graph_data')
def serve_graph_data():
    """Serves the graph data as JSON."""
    global GRAPH_DATA_GLOBAL
    if GRAPH_DATA_GLOBAL is None:
        logging.warning("Request for /graph_data when GRAPH_DATA_GLOBAL is None.")
        return jsonify({"error": "Graph data not loaded"}), 404
    return jsonify(GRAPH_DATA_GLOBAL)

def run_server(graph_json_data, host='127.0.0.1', port=5000, debug=False):
    """
    Runs the Flask development server to serve the graph visualization.

    Args:
        graph_json_data: The graph data in the format returned by export_graph_to_json.
        host: The hostname to listen on.
        port: The port of the webserver.
        debug: Enable Flask's debug mode.
    """
    global GRAPH_DATA_GLOBAL
    GRAPH_DATA_GLOBAL = graph_json_data
    
    logging.info(f"Starting visualization server on http://{host}:{port}")
    # Disable Werkzeug's default startup message if not in debug, to avoid double logging with ours
    if not debug:
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)
        
    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    # Example Usage:
    # 1. Create a sample NetworkX graph
    sample_graph = networkx.DiGraph()

    # Add nodes with attributes
    sample_graph.add_node("file::/app/service.py", name="service.py", type="python_file", path="/app/service.py", lines=150)
    sample_graph.add_node("class::/app/service.py::MyService", name="MyService", type="class", file_path="/app/service.py")
    sample_graph.add_node("method::/app/service.py::MyService::do_work", name="do_work", type="method", class_name="MyService", signature="()")
    sample_graph.add_node("module::flask", name="flask", type="python_module", external=True)
    sample_graph.add_node("tech::camunda", name="Camunda", type="technology_reference", confidence="high")
    
    # Add new entity types for visualization testing
    sample_graph.add_node("db_entity::products_table", name="ProductsTable", type="db_entity", defined_in_dbcontext="MainContext")
    sample_graph.add_node("db_property::products_table::product_id", name="ProductID", type="db_property", is_primary_key=True)
    sample_graph.add_edge("db_entity::products_table", "db_property::products_table::product_id", type="has_property")

    sample_graph.add_node("k8s_yaml_file::/deploy/app.yaml", name="app.yaml", type="k8s_yaml_file", path="/deploy/app.yaml")
    sample_graph.add_node("k8s_deployment::prod::my-app-dep", name="my-app-dep", type="k8s_deployment", namespace="prod", kind="Deployment")
    sample_graph.add_edge("k8s_yaml_file::/deploy/app.yaml", "k8s_deployment::prod::my-app-dep", type="defines_k8s_resource")

    sample_graph.add_node("docker_image::myimage:latest", name="myimage:latest", type="docker_image", image_tag="latest")
    sample_graph.add_edge("k8s_deployment::prod::my-app-dep", "docker_image::myimage:latest", type="uses_image")

    # Add edges with attributes
    sample_graph.add_edge("file::/app/service.py", "class::/app/service.py::MyService", type="defines_class")
    sample_graph.add_edge("class::/app/service.py::MyService", "method::/app/service.py::MyService::do_work", type="defines_method")
    sample_graph.add_edge("method::/app/service.py::MyService::do_work", "module::flask", type="calls", detail="jsonify")
    sample_graph.add_edge("file::/app/service.py", "tech::camunda", type="mentions_technology", context="import statement")

    # Example data flow edge (if desired for visualization test)
    # sample_graph.add_edge("method::/app/service.py::MyService::do_work", "module::another_module", type="potential_data_flow", intermediate_variable="result")

    logging.info("Sample graph with new entity types created for testing.")

    # 2. Export the graph to JSON
    exported_json = export_graph_to_json(sample_graph)
    
    # Verify JSON structure (optional)
    # print(json.dumps(exported_json, indent=2))

    # 3. Ensure templates/index.html exists (basic version for testing)
    # The main task requires a more detailed index.html, this is just for __main__
    if not os.path.exists(TEMPLATE_DIR):
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        logging.info(f"Created template directory: {TEMPLATE_DIR}")

    sample_index_html_path = os.path.join(TEMPLATE_DIR, 'index.html')
    if not os.path.exists(sample_index_html_path):
        with open(sample_index_html_path, 'w') as f:
            f.write("""<!DOCTYPE html>
<html>
<head><title>Test Graph</title></head>
<body><h1>Graph should load below</h1><div id="mynetwork" style="width:600px; height:400px; border:1px solid black;"></div>
<script type="text/javascript" src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<script type="text/javascript">
    const container = document.getElementById('mynetwork');
    fetch('/graph_data').then(res => res.json()).then(data => {
        if(data.error) { alert(data.error); return; }
        new vis.Network(container, data, {}); // Basic options for test
        console.log("Graph data loaded into vis.js", data);
    }).catch(err => console.error("Test client-side error:", err));
</script>
</body></html>""")
        logging.info(f"Created sample index.html at {sample_index_html_path}")

    # 4. Run the server
    print("\nTo view the visualization, open your browser to http://127.0.0.1:5000")
    print("Press Ctrl+C to stop the server.\n")
    try:
        run_server(exported_json, debug=True) # debug=True is helpful for development
    except KeyboardInterrupt:
        logging.info("Flask server stopped by user.")
    except Exception as e:
        logging.error(f"Failed to run Flask server: {e}")

    # Clean up the dummy index.html if it was created by this test script
    # (Be careful if you have a real index.html you want to keep)
    # if os.path.exists(sample_index_html_path) and "Test Graph" in open(sample_index_html_path).read():
    #     os.remove(sample_index_html_path)
    #     logging.info(f"Cleaned up sample index.html: {sample_index_html_path}")
