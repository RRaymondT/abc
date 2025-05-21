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


if __name__ == '__main__':
    unittest.main()
