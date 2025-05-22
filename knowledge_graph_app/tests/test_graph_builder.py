import unittest
import networkx # Used for type hinting and potentially direct graph inspection if needed
import logging

# Adjust the path to import from the src directory
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from graph_builder import KnowledgeGraph

class TestGraphBuilder(unittest.TestCase):

    def setUp(self):
        self.kg = KnowledgeGraph()
        # Disable logging during tests for cleaner output
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        # Re-enable logging
        logging.disable(logging.NOTSET)

    def test_add_node_and_edge(self):
        """Test basic node and edge addition."""
        self.kg.add_node("n1", node_type="typeA", name="Node1", custom_attr="value1")
        self.kg.add_node("n2", node_type="typeB", name="Node2")
        self.kg.add_node("n1", node_type="typeA_updated", name="Node1_updated", new_attr="new_val") # Test update

        self.kg.add_edge("n1", "n2", relationship_type="links_to", weight=5)
        # Test adding edge with a node that doesn't exist yet
        self.kg.add_edge("n2", "n3", relationship_type="connects_to", detail="inferred node n3")

        g = self.kg.get_graph()

        self.assertTrue(g.has_node("n1"))
        self.assertEqual(g.nodes["n1"]['type'], "typeA_updated") # Check if type was updated
        self.assertEqual(g.nodes["n1"]['name'], "Node1_updated") # Check if name was updated
        self.assertEqual(g.nodes["n1"]['custom_attr'], "value1") # Original attr should persist
        self.assertEqual(g.nodes["n1"]['new_attr'], "new_val")   # New attr should be added

        self.assertTrue(g.has_node("n2"))
        self.assertEqual(g.nodes["n2"]['type'], "typeB")
        
        self.assertTrue(g.has_node("n3")) # n3 should be created as inferred
        self.assertEqual(g.nodes["n3"]['type'], "inferred_entity")
        self.assertEqual(g.nodes["n3"]['name'], "n3")


        self.assertTrue(g.has_edge("n1", "n2"))
        self.assertEqual(g.edges[("n1", "n2")]['type'], "links_to")
        self.assertEqual(g.edges[("n1", "n2")]['weight'], 5)
        
        self.assertTrue(g.has_edge("n2", "n3"))
        self.assertEqual(g.edges[("n2", "n3")]['type'], "connects_to")


    def test_process_python_parsed_data_basic(self):
        """Test processing of basic parsed Python data."""
        # Note: file_path in parsed_py should ideally be absolute or consistently relative
        # For testing, we use a simple string. The graph builder uses it as an ID component.
        file_path = 'a.py'
        parsed_py = {
            'file_path': file_path,
            'imports': ['os', 'sys'],
            'classes': [{
                'name': 'C1',
                'base_classes': ['object'],
                'methods': [{
                    'name': 'm1',
                    'parameters': ['self', 'arg1'],
                    'calls': ['print', 'os.path.join']
                }]
            }],
            'functions': [{
                'name': 'f1',
                'parameters': ['p1'],
                'calls': ['C1'] # Assuming a call to the class constructor or a static method
            }]
        }

        self.kg.process_python_parsed_data(parsed_py, file_path)
        g = self.kg.get_graph()

        # Check file node
        file_node_id = self.kg._generate_node_id("file", file_path)
        self.assertTrue(g.has_node(file_node_id))
        self.assertEqual(g.nodes[file_node_id]['type'], 'python_file')
        self.assertEqual(g.nodes[file_node_id]['name'], os.path.basename(file_path))

        # Check import nodes and edges
        mod_os_id = self.kg._generate_node_id("module", "os")
        mod_sys_id = self.kg._generate_node_id("module", "sys")
        self.assertTrue(g.has_node(mod_os_id))
        self.assertTrue(g.has_edge(file_node_id, mod_os_id))
        self.assertEqual(g.edges[(file_node_id, mod_os_id)]['type'], 'imports')
        self.assertTrue(g.has_edge(file_node_id, mod_sys_id))


        # Check class node and edge
        class_node_id = self.kg._generate_node_id("class", file_path, "C1")
        self.assertTrue(g.has_node(class_node_id))
        self.assertEqual(g.nodes[class_node_id]['name'], 'C1')
        self.assertEqual(g.nodes[class_node_id]['base_classes'], ['object'])
        self.assertTrue(g.has_edge(file_node_id, class_node_id))
        self.assertEqual(g.edges[(file_node_id, class_node_id)]['type'], 'defines_class')

        # Check method node and edge
        method_node_id = self.kg._generate_node_id("method", file_path, "C1", "m1")
        self.assertTrue(g.has_node(method_node_id))
        self.assertEqual(g.nodes[method_node_id]['parameters'], ['self', 'arg1'])
        self.assertTrue(g.has_edge(class_node_id, method_node_id))
        self.assertEqual(g.edges[(class_node_id, method_node_id)]['type'], 'defines_method')

        # Check calls from method
        call_print_id = self.kg._generate_node_id("callable", "print")
        call_os_path_join_id = self.kg._generate_node_id("callable", "os.path.join")
        self.assertTrue(g.has_node(call_print_id)) # Created as callable_entity
        self.assertTrue(g.has_edge(method_node_id, call_print_id))
        self.assertEqual(g.edges[(method_node_id, call_print_id)]['type'], 'calls')
        self.assertTrue(g.has_edge(method_node_id, call_os_path_join_id))

        # Check function node and edge
        func_node_id = self.kg._generate_node_id("function", file_path, "f1")
        self.assertTrue(g.has_node(func_node_id))
        self.assertTrue(g.has_edge(file_node_id, func_node_id))

        # Check call from function
        call_c1_id = self.kg._generate_node_id("callable", "C1")
        self.assertTrue(g.has_node(call_c1_id)) # Will be 'callable_entity' if not resolved to class_node_id
        self.assertTrue(g.has_edge(func_node_id, call_c1_id))


    def test_process_bpmn_parsed_data_basic(self):
        """Test processing of basic parsed BPMN data."""
        file_path = '/myproj/process.bpmn'
        parsed_bpmn = {
            'file_path': file_path,
            'processes': [{'id': 'Proc1', 'name': 'Order Process'}],
            'service_tasks': [{'id': 'Task1', 'name': 'Email Customer', 'camunda_class': 'com.example.EmailDelegate'}],
            'user_tasks': [{'id': 'UserTask1', 'name': 'Approve Order'}]
        }
        self.kg.process_bpmn_parsed_data(parsed_bpmn, file_path)
        g = self.kg.get_graph()

        file_node_id = self.kg._generate_node_id("file", file_path)
        self.assertTrue(g.has_node(file_node_id))
        self.assertEqual(g.nodes[file_node_id]['type'], 'bpmn_file')

        process_node_id = self.kg._generate_node_id("bpmn_process", file_path, "Proc1")
        self.assertTrue(g.has_node(process_node_id))
        self.assertEqual(g.nodes[process_node_id]['name'], 'Order Process')
        self.assertTrue(g.has_edge(file_node_id, process_node_id))

        st_node_id = self.kg._generate_node_id("bpmn_service_task", file_path, "Task1")
        self.assertTrue(g.has_node(st_node_id))
        self.assertEqual(g.nodes[st_node_id]['camunda_class'], 'com.example.EmailDelegate')
        self.assertTrue(g.has_edge(process_node_id, st_node_id)) # contains_task
        self.assertTrue(g.has_edge(file_node_id, st_node_id)) # defines_task

        impl_node_id = self.kg._generate_node_id("java_class", "com.example.EmailDelegate")
        self.assertTrue(g.has_node(impl_node_id))
        self.assertTrue(g.has_edge(st_node_id, impl_node_id))

        ut_node_id = self.kg._generate_node_id("bpmn_user_task", file_path, "UserTask1")
        self.assertTrue(g.has_node(ut_node_id))
        self.assertTrue(g.has_edge(process_node_id, ut_node_id))


    def test_process_tech_scan_data_basic(self):
        """Test processing of basic tech scan data."""
        codebase_path = '/myproj'
        tech_scan = {
            'project_files': {'Maven': ['/myproj/pom.xml'], 'NPM': ['/myproj/package.json']},
            'keyword_scan': {'Camunda': ['/myproj/Service.java'], 'Spring Framework': ['/myproj/Service.java', '/myproj/Controller.java']}
        }
        self.kg.process_tech_scan_data(tech_scan, codebase_path)
        g = self.kg.get_graph()

        # Codebase node
        codebase_node_id = self.kg._generate_node_id("codebase", codebase_path)
        self.assertTrue(g.has_node(codebase_node_id))
        self.assertEqual(g.nodes[codebase_node_id]['path'], codebase_path)

        # Project files and associated tech stack nodes
        pom_file_node_id = self.kg._generate_node_id("file", "/myproj/pom.xml")
        maven_tech_node_id = self.kg._generate_node_id("tech", "maven") # Note: graph_builder converts tech_name to lower and replaces spaces/dots
        
        self.assertTrue(g.has_node(pom_file_node_id))
        self.assertEqual(g.nodes[pom_file_node_id]['type'], 'project_file')
        self.assertTrue(g.has_node(maven_tech_node_id))
        self.assertEqual(g.nodes[maven_tech_node_id]['name'], 'Maven')
        
        self.assertTrue(g.has_edge(codebase_node_id, pom_file_node_id))
        self.assertEqual(g.edges[(codebase_node_id, pom_file_node_id)]['type'], 'contains_project_file')
        self.assertTrue(g.has_edge(pom_file_node_id, maven_tech_node_id))
        self.assertEqual(g.edges[(pom_file_node_id, maven_tech_node_id)]['type'], 'uses_technology_stack')

        # Keyword scan results
        java_service_node_id = self.kg._generate_node_id("file", "/myproj/Service.java")
        camunda_ref_node_id = self.kg._generate_node_id("tech_reference", "camunda") # graph_builder converts
        spring_ref_node_id = self.kg._generate_node_id("tech_reference", "spring_framework")

        self.assertTrue(g.has_node(java_service_node_id)) # Created as 'file' type if not already existing
        self.assertTrue(g.has_node(camunda_ref_node_id))
        self.assertEqual(g.nodes[camunda_ref_node_id]['name'], 'Camunda')
        self.assertTrue(g.has_edge(java_service_node_id, camunda_ref_node_id))
        self.assertEqual(g.edges[(java_service_node_id, camunda_ref_node_id)]['type'], 'mentions_technology')
        
        self.assertTrue(g.has_edge(java_service_node_id, spring_ref_node_id))


    def test_generate_node_id_consistency(self):
        """Test node ID generation for consistency."""
        # Test case from prompt
        self.assertEqual(self.kg._generate_node_id('file.py', 'ClassA'), 'file.py::ClassA')
        
        # Test with None and empty parts
        self.assertEqual(self.kg._generate_node_id('file.py', None, 'ClassA'), 'file.py::ClassA')
        self.assertEqual(self.kg._generate_node_id('file.py', '', 'ClassA'), 'file.py::ClassA')
        self.assertEqual(self.kg._generate_node_id(None, 'file.py', 'ClassA'), 'file.py::ClassA')
        self.assertEqual(self.kg._generate_node_id('file.py', 'ClassA', None, 'methodA'), 'file.py::ClassA::methodA')
        self.assertEqual(self.kg._generate_node_id(123, 'ClassA'), '123::ClassA') # Numbers should be stringified
        
        # Test with only one part
        self.assertEqual(self.kg._generate_node_id('single_part'), 'single_part')
        
        # Test with all None or empty (should produce a default/error ID, or raise error based on implementation)
        # Current implementation returns "error_node_empty_parts"
        self.assertEqual(self.kg._generate_node_id(None, "", None), "error_node_empty_parts")
        self.assertEqual(self.kg._generate_node_id(), "error_node_empty_parts")


    def test_load_graph_from_directory(self):
        """Basic test for the orchestrator load_graph_from_directory."""
        codebase_path = "/test/project"
        tech_data = {
            'project_files': {'Python': [os.path.join(codebase_path,'requirements.txt')]},
            'keyword_scan': {'Flask': [os.path.join(codebase_path,'app.py')]}
        }
        py_file_path = os.path.join(codebase_path,'app.py')
        parsed_data = {
            py_file_path: {
                'file_path': py_file_path,
                'imports': ['flask'],
                'functions': [{'name': 'hello', 'calls': ['flask.jsonify']}]
            }
        }

        self.kg.load_graph_from_directory(codebase_path, tech_data, parsed_data)
        g = self.kg.get_graph()

        # Check that nodes from both tech_scan and parsed_data are present
        self.assertTrue(g.has_node(self.kg._generate_node_id("codebase", codebase_path)))
        self.assertTrue(g.has_node(self.kg._generate_node_id("file", os.path.join(codebase_path,'requirements.txt'))))
        self.assertTrue(g.has_node(self.kg._generate_node_id("tech", "python"))) # from project_files
        
        app_py_node_id = self.kg._generate_node_id("file", py_file_path)
        self.assertTrue(g.has_node(app_py_node_id))
        self.assertTrue(g.has_node(self.kg._generate_node_id("tech_reference", "flask"))) # from keyword_scan
        
        # Check elements from parsed_data
        func_hello_id = self.kg._generate_node_id("function", py_file_path, "hello")
        self.assertTrue(g.has_node(func_hello_id))
        self.assertTrue(g.has_edge(app_py_node_id, func_hello_id)) # defines_function relationship

        # Check that a basic file node is created for files mentioned in tech_scan but not in parsed_data
        # (e.g., if requirements.txt wasn't "parsed" but was identified)
        req_txt_node_id = self.kg._generate_node_id("file", os.path.join(codebase_path,'requirements.txt'))
        self.assertTrue(g.has_node(req_txt_node_id))
        self.assertEqual(g.nodes[req_txt_node_id]['type'], 'project_file') # Type from tech_scan

    def test_process_python_data_with_decorators(self):
        """Test processing Python data that includes decorators."""
        file_path = 'decorated_app.py'
        mock_data = {
            "file_path": file_path,
            "classes": [{
                "name": "DecoratedClass",
                "decorators": ["@my_class_decorator"],
                "methods": [{
                    "name": "decorated_method",
                    "decorators": ["@my_method_decorator(arg=True)"],
                    "parameters": ["self"]
                }]
            }],
            "functions": [{
                "name": "decorated_function",
                "decorators": ["@another_decorator"],
                "parameters": []
            }]
        }
        self.kg.process_parsed_file_data(mock_data)
        g = self.kg.get_graph()

        class_node_id = self.kg._generate_node_id("class", file_path, "DecoratedClass")
        self.assertTrue(g.has_node(class_node_id))
        self.assertEqual(g.nodes[class_node_id].get('decorators'), ["@my_class_decorator"])

        method_node_id = self.kg._generate_node_id("method", file_path, "DecoratedClass", "decorated_method")
        self.assertTrue(g.has_node(method_node_id))
        self.assertEqual(g.nodes[method_node_id].get('decorators'), ["@my_method_decorator(arg=True)"])
        
        func_node_id = self.kg._generate_node_id("function", file_path, "decorated_function")
        self.assertTrue(g.has_node(func_node_id))
        self.assertEqual(g.nodes[func_node_id].get('decorators'), ["@another_decorator"])


    def test_process_csharp_data_sample(self):
        """Test processing of parsed C# data."""
        file_path = '/app/services/ExampleService.cs'
        mock_csharp_data = {
            "file_path": file_path,
            "usings": ["System", "System.Threading.Tasks"],
            "namespaces": [{
                "name": "MyCompany.Services",
                "classes": [{
                    "name": "ExampleService", "namespace": "MyCompany.Services", 
                    "attributes": ["ServiceContract"], "base_types_str": "IExampleService",
                    "methods": [{
                        "name": "DoWorkAsync", "attributes": ["OperationContract"], 
                        "return_type": "Task<string>", "parameters_str": "int id"
                    }],
                    "properties": [{
                        "name": "IsEnabled", "attributes": [], "type": "bool"
                    }]
                }],
                "interfaces": []
            }],
            "classes": [], "interfaces": []
        }
        self.kg.process_parsed_file_data(mock_csharp_data)
        g = self.kg.get_graph()

        file_node_id = self.kg._generate_node_id("file", file_path)
        self.assertTrue(g.has_node(file_node_id))
        self.assertEqual(g.nodes[file_node_id]['type'], 'csharp_file')

        ns_node_id = self.kg._generate_node_id("csharp_namespace", "MyCompany.Services")
        self.assertTrue(g.has_node(ns_node_id))
        self.assertTrue(g.has_edge(file_node_id, ns_node_id))

        class_node_id = self.kg._generate_node_id("csharp_class", file_path, "ExampleService")
        self.assertTrue(g.has_node(class_node_id))
        self.assertEqual(g.nodes[class_node_id]['namespace'], "MyCompany.Services")
        self.assertIn("ServiceContract", g.nodes[class_node_id]['attributes'])
        self.assertEqual(g.nodes[class_node_id]['base_types_str'], "IExampleService")
        self.assertTrue(g.has_edge(ns_node_id, class_node_id)) # contains_entity
        self.assertTrue(g.has_edge(file_node_id, class_node_id)) # defines_class

        method_node_id = self.kg._generate_node_id("csharp_method", file_path, "ExampleService", "DoWorkAsync")
        self.assertTrue(g.has_node(method_node_id))
        self.assertIn("OperationContract", g.nodes[method_node_id]['attributes'])
        self.assertEqual(g.nodes[method_node_id]['return_type'], "Task<string>")
        self.assertTrue(g.has_edge(class_node_id, method_node_id))

        prop_node_id = self.kg._generate_node_id("csharp_property", file_path, "ExampleService", "IsEnabled")
        self.assertTrue(g.has_node(prop_node_id))
        self.assertEqual(g.nodes[prop_node_id]['type'], "bool")
        self.assertTrue(g.has_edge(class_node_id, prop_node_id))


    def test_process_vue_data_sample(self):
        """Test processing of parsed Vue.js SFC data."""
        file_path = '/app/components/Login.vue'
        mock_vue_data = {
            "file_path": file_path,
            "component_name": "LoginComponent",
            "script_lang": "ts", "style_lang": "scss",
            "imports": ["vue", "./apiService"],
            "props": ["username", "password"],
            "data_properties": ["email", "rememberMe"],
            "methods": ["handleLogin", "resetForm"],
            "computed_properties": ["isFormValid"],
            "template_components_used": ["BaseInput", "AwesomeButton"],
            "template_event_bindings": [{"event": "click", "handler": "handleLogin"}]
        }
        self.kg.process_parsed_file_data(mock_vue_data)
        g = self.kg.get_graph()

        file_node_id = self.kg._generate_node_id("file", file_path)
        self.assertTrue(g.has_node(file_node_id))
        self.assertEqual(g.nodes[file_node_id]['type'], 'vue_component_file')

        comp_node_id = self.kg._generate_node_id("vue_component", file_path, "LoginComponent")
        self.assertTrue(g.has_node(comp_node_id))
        self.assertEqual(g.nodes[comp_node_id]['script_lang'], 'ts')
        self.assertTrue(g.has_edge(file_node_id, comp_node_id)) # defines_component

        # Check one of each type of sub-element
        prop_node_id = self.kg._generate_node_id("vue_prop", file_path, "LoginComponent", "username")
        self.assertTrue(g.has_node(prop_node_id))
        self.assertTrue(g.has_edge(comp_node_id, prop_node_id)) # has_prop

        method_node_id = self.kg._generate_node_id("vue_method", file_path, "LoginComponent", "handleLogin")
        self.assertTrue(g.has_node(method_node_id))
        self.assertTrue(g.has_edge(comp_node_id, method_node_id)) # has_method

        # Check component usage
        used_comp_node_id = self.kg._generate_node_id("vue_component", "BaseInput") # Simpler ID for used component
        self.assertTrue(g.has_node(used_comp_node_id))
        self.assertTrue(g.has_edge(comp_node_id, used_comp_node_id)) # uses_component_in_template
        
        # Check event binding leading to method
        # The edge type is dynamic: f"on_{event_name.replace('.', '_')}_calls_method"
        self.assertTrue(g.has_edge(comp_node_id, method_node_id, type="on_click_calls_method"))


    def test_process_ef_dbcontext_data_sample(self):
        """Test processing of C# DbContext data including EF configurations."""
        file_path = '/app/data/MyDbContext.cs'
        mock_ef_data = {
            "file_path": file_path,
            "classes": [{ # Assuming the DbContext class is passed directly or as part of a larger structure
                "name": "MyDbContext", "namespace": "MyProject.Data", "is_dbcontext": True,
                "base_types_str": "DbContext",
                "db_sets": [
                    {"entity_name": "Blog", "property_name": "Blogs"},
                    {"entity_name": "Post", "property_name": "Posts"}
                ],
                "ef_configurations": [
                    {"entity_configured": "Blog", "call_type": "HasKey", "details": {"key_expression": "b => b.BlogId", "keys_found":["BlogId"]}},
                    {"entity_configured": "Blog", "call_type": "Property", "details": {"property_name": "Url", "is_required": True}},
                    {"entity_configured": "Post", "call_type": "HasMany_WithOne", "details": {"target_entity": "Blog", "source_navigation": "Posts", "target_navigation": "Blog", "foreign_key": "BlogId"}}
                ],
                "methods": [], # Keep methods list for consistent structure, even if empty for this test
                "properties": [] # Keep properties list
            }],
            # Need to ensure the 'type' indicates C# for the dispatcher
            "usings": ["Microsoft.EntityFrameworkCore"] # Add a typical C# using to help dispatcher
        }
        
        # We also need the Product and Category classes to be "parsed" if EF configs refer to them as entities
        # For simplicity, we'll assume they are also part of this mock or processed separately.
        # Here, we'll focus on the DbContext processing.

        self.kg.process_parsed_file_data(mock_ef_data) # This will dispatch to process_csharp_parsed_data
        g = self.kg.get_graph()

        dbcontext_node_id = self.kg._generate_node_id("csharp_class", file_path, "MyDbContext")
        self.assertTrue(g.has_node(dbcontext_node_id))

        # Check DbSet processing
        blog_entity_node_id = self.kg._generate_node_id("db_entity::Blog")
        self.assertTrue(g.has_node(blog_entity_node_id))
        self.assertTrue(g.has_edge(dbcontext_node_id, blog_entity_node_id))
        self.assertEqual(g.edges[(dbcontext_node_id, blog_entity_node_id, 0)]['set_name'], 'Blogs')

        # Check HasKey configuration
        blogid_prop_node_id = self.kg._generate_node_id(blog_entity_node_id, "property", "BlogId")
        self.assertTrue(g.has_node(blogid_prop_node_id))
        self.assertTrue(g.nodes[blogid_prop_node_id]['is_primary_key'])
        self.assertTrue(g.has_edge(blog_entity_node_id, blogid_prop_node_id, type="has_primary_key_property"))

        # Check Property configuration
        url_prop_node_id = self.kg._generate_node_id(blog_entity_node_id, "property", "Url")
        self.assertTrue(g.has_node(url_prop_node_id))
        self.assertTrue(g.nodes[url_prop_node_id]['is_required'])
        self.assertTrue(g.has_edge(blog_entity_node_id, url_prop_node_id, type="has_property_configured"))

        # Check Relationship configuration
        post_entity_node_id = self.kg._generate_node_id("db_entity::Post")
        self.assertTrue(g.has_node(post_entity_node_id)) # Created from DbSet or relationship
        # Edge from Post to Blog (as Post.Blog is the navigation for HasOne side of HasMany)
        # The graph builder logic for HasMany_WithOne creates edge from the "many" side (Post) to the "one" side (Blog)
        # if the parser provides `target_entity` correctly.
        # The example parser for EF provides `target_entity` based on `WithOne` or `WithMany` argument.
        # Our mock `ef_configurations` for Post: `target_entity` is `Blog`.
        # The relationship is from Post (entity_configured) to Blog (target_entity).
        # Edge type created by graph_builder: hasmany_to_withone
        # The source of this edge is 'Post' (entity_configured), target is 'Blog' (target_entity from details)
        self.assertTrue(g.has_edge(post_entity_node_id, blog_entity_node_id))
        edge_data = g.get_edge_data(post_entity_node_id, blog_entity_node_id)[0] # Assuming one edge
        self.assertEqual(edge_data['type'], "hasmany_to_withone")
        self.assertEqual(edge_data.get('source_navigation'), "Posts") # Nav prop on Blog
        self.assertEqual(edge_data.get('target_navigation'), "Blog") # Nav prop on Post
        self.assertEqual(edge_data.get('foreign_key'), "BlogId")


    def test_process_k8s_yaml_data_sample(self):
        """Test processing of parsed Kubernetes YAML data."""
        k8s_file_path = "/deploy/my-app.yaml"
        mock_k8s_data = [
            {"file_path": k8s_file_path, "kind": "Deployment", "name": "app-deploy", "namespace": "dev",
             "containers": [{"name": "main", "image": "myimage:v1"}, {"name": "sidecar", "image": "helper:latest"}]},
            {"file_path": k8s_file_path, "kind": "Service", "name": "app-svc", "namespace": "dev",
             "service_type": "LoadBalancer", "selector": {"app": "my-app"}}
        ]
        self.kg.process_k8s_yaml_data(mock_k8s_data, k8s_file_path)
        g = self.kg.get_graph()

        file_node_id = self.kg._generate_node_id("k8s_yaml_file", k8s_file_path)
        self.assertTrue(g.has_node(file_node_id))

        dep_node_id = self.kg._generate_node_id("k8s_resource", k8s_file_path, "Deployment", "dev", "app-deploy")
        self.assertTrue(g.has_node(dep_node_id))
        self.assertEqual(g.nodes[dep_node_id]['type'], 'k8s_deployment')
        self.assertTrue(g.has_edge(file_node_id, dep_node_id))

        svc_node_id = self.kg._generate_node_id("k8s_resource", k8s_file_path, "Service", "dev", "app-svc")
        self.assertTrue(g.has_node(svc_node_id))
        self.assertEqual(g.nodes[svc_node_id]['type'], 'k8s_service')
        self.assertEqual(g.nodes[svc_node_id]['service_type'], 'LoadBalancer')
        self.assertTrue(g.has_edge(file_node_id, svc_node_id))

        img1_node_id = self.kg._generate_node_id("docker_image::myimage:v1")
        self.assertTrue(g.has_node(img1_node_id))
        self.assertEqual(g.nodes[img1_node_id]['image_tag'], 'v1')
        self.assertTrue(g.has_edge(dep_node_id, img1_node_id))
        self.assertEqual(g.get_edge_data(dep_node_id, img1_node_id)[0]['container_name'], 'main')


    def test_process_python_data_flow_links(self):
        """Test processing of Python data flow links."""
        file_path = 'data_flow_example.py'
        mock_py_flow_data = {
            "file_path": file_path,
            "functions": [
                {"name": "source_a", "parameters": [], "calls": [], "data_flow_links": []},
                {"name": "process_b", "parameters": ["data"], "calls": [], "data_flow_links": []},
                {
                    "name": "main_flow", "parameters": [], "calls": ["source_a", "process_b"],
                    "data_flow_links": [{
                        "source_function": "source_a", 
                        "intermediate_variable": "var_x",
                        "target_function": "process_b",
                        "arg_index": 0 
                    }]
                }
            ],
            "classes": [] # Ensure this key exists even if empty
        }
        self.kg.process_parsed_file_data(mock_py_flow_data)
        g = self.kg.get_graph()

        source_node_id = self.kg._find_or_create_callable_node(file_path, "source_a")
        target_node_id = self.kg._find_or_create_callable_node(file_path, "process_b")
        
        # Ensure the callable nodes were actually created as functions from the parsed data
        # (not just as external_or_unresolved_callable by _find_or_create_callable_node)
        expected_source_id = self.kg._generate_node_id("function", file_path, "source_a")
        expected_target_id = self.kg._generate_node_id("function", file_path, "process_b")
        self.assertEqual(source_node_id, expected_source_id)
        self.assertEqual(target_node_id, expected_target_id)
        self.assertTrue(g.has_node(source_node_id))
        self.assertTrue(g.has_node(target_node_id))
        
        self.assertTrue(g.has_edge(source_node_id, target_node_id))
        edge_data = g.get_edge_data(source_node_id, target_node_id)[0] # Assuming one edge
        self.assertEqual(edge_data['type'], "potential_data_flow")
        self.assertEqual(edge_data['intermediate_variable'], "var_x")
        self.assertEqual(edge_data['flow_through_function_name'], "main_flow")


if __name__ == '__main__':
    unittest.main()
