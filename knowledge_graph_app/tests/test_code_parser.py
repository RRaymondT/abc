import unittest
import os
import tempfile
import shutil
import logging

# Adjust the path to import from the src directory
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from code_parser import parse_file, parse_python_file, identify_camunda_bpmn

class TestCodeParser(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        logging.disable(logging.CRITICAL) # Disable logging for cleaner test output

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        logging.disable(logging.NOTSET) # Re-enable logging

    def _create_file(self, filename, content=""):
        """Helper method to create a file in the temporary directory."""
        file_path = os.path.join(self.temp_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path

    def test_parse_simple_python_file(self):
        """Test parsing of a basic Python file."""
        PYTHON_CODE = "import os\nimport sys\n\nclass MyClass(object):\n  def method(self, arg1):\n    print('hello')\n    sys.exit(0)\n\ndef top_func(param):\n  os.path.join(param, 'test')\n  pass"
        py_file = self._create_file('test.py', PYTHON_CODE)
        
        result = parse_python_file(py_file)
        
        self.assertIsNotNone(result)
        self.assertIn('os', result['imports'])
        self.assertIn('sys', result['imports'])
        self.assertEqual(len(result['classes']), 1)
        self.assertEqual(result['classes'][0]['name'], 'MyClass')
        self.assertEqual(result['classes'][0]['base_classes'], ['object'])
        self.assertEqual(len(result['classes'][0]['methods']), 1)
        self.assertEqual(result['classes'][0]['methods'][0]['name'], 'method')
        self.assertIn('self', result['classes'][0]['methods'][0]['parameters'])
        self.assertIn('arg1', result['classes'][0]['methods'][0]['parameters'])
        self.assertIn('print', result['classes'][0]['methods'][0]['calls'])
        self.assertIn('sys.exit', result['classes'][0]['methods'][0]['calls'])
        
        self.assertEqual(len(result['functions']), 1)
        self.assertEqual(result['functions'][0]['name'], 'top_func')
        self.assertIn('param', result['functions'][0]['parameters'])
        self.assertIn('os.path.join', result['functions'][0]['calls'])

    def test_identify_simple_bpmn_file(self):
        """Test parsing of a basic BPMN file."""
        BPMN_XML = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:camunda="http://camunda.org/schema/1.0/bpmn"
                  id="Definitions_1">
  <bpmn:process id="Proc_1" name="Test Process">
    <bpmn:serviceTask id="Task_1" name="My Service Task" camunda:class="com.example.TestDelegate"/>
    <bpmn:userTask id="Task_2" name="My User Task"/>
  </bpmn:process>
</bpmn:definitions>"""
        bpmn_file = self._create_file('test.bpmn', BPMN_XML)
        result = identify_camunda_bpmn(bpmn_file)

        self.assertIsNotNone(result)
        self.assertEqual(len(result['processes']), 1)
        self.assertEqual(result['processes'][0]['id'], 'Proc_1')
        self.assertEqual(result['processes'][0]['name'], 'Test Process')
        
        self.assertEqual(len(result['service_tasks']), 1)
        self.assertEqual(result['service_tasks'][0]['id'], 'Task_1')
        self.assertEqual(result['service_tasks'][0]['name'], 'My Service Task')
        self.assertEqual(result['service_tasks'][0]['camunda_class'], 'com.example.TestDelegate')
        
        self.assertEqual(len(result['user_tasks']), 1)
        self.assertEqual(result['user_tasks'][0]['id'], 'Task_2')
        self.assertEqual(result['user_tasks'][0]['name'], 'My User Task')

    def test_parse_file_dispatcher(self):
        """Test the main parse_file dispatcher."""
        PYTHON_CODE = "class A: pass"
        BPMN_XML = '<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"><bpmn:process id="P1"/></bpmn:definitions>'
        
        py_file = self._create_file('sample.py', PYTHON_CODE)
        bpmn_file = self._create_file('sample.bpmn', BPMN_XML)
        other_file = self._create_file('sample.txt', "hello")

        py_result = parse_file(py_file)
        bpmn_result = parse_file(bpmn_file)
        other_result = parse_file(other_file)

        self.assertIsNotNone(py_result)
        self.assertIn('classes', py_result)
        self.assertEqual(py_result['classes'][0]['name'], 'A')

        self.assertIsNotNone(bpmn_result)
        self.assertIn('processes', bpmn_result)
        self.assertEqual(bpmn_result['processes'][0]['id'], 'P1')
        
        self.assertIsNone(other_result, "Dispatcher should return None for unsupported file types")

    def test_parse_non_bpmn_xml(self):
        """Test parsing a generic XML file with identify_camunda_bpmn."""
        xml_file = self._create_file('test.xml', '<root><item>Test</item><item>Data</item></root>')
        result = identify_camunda_bpmn(xml_file)
        
        # It should return None because the root tag is not <bpmn:definitions>
        # or it might return a structure with empty lists if the root tag was <definitions> but no bpmn elements
        # The current implementation of identify_camunda_bpmn checks root.tag.endswith('definitions')
        # and then checks for specific bpmn elements.
        self.assertIsNone(result, "Non-BPMN XML should return None or an empty structure from identify_camunda_bpmn")


    def test_parse_invalid_python(self):
        """Test parsing a Python file with syntax errors."""
        # Python 2 print statement is a syntax error in Python 3
        py_file_invalid = self._create_file('invalid.py', 'class MyClass:\n  print "old python"')
        result = parse_python_file(py_file_invalid)
        
        self.assertIsNone(result, "Parsing syntactically incorrect Python should return None")

    def test_parse_file_not_found(self):
        """Test parsing a non-existent file."""
        non_existent_py_file = os.path.join(self.temp_dir, "ghost.py")
        result = parse_python_file(non_existent_py_file)
        self.assertIsNone(result)

        non_existent_bpmn_file = os.path.join(self.temp_dir, "ghost.bpmn")
        result_bpmn = identify_camunda_bpmn(non_existent_bpmn_file)
        self.assertIsNone(result_bpmn)

        result_dispatch = parse_file(non_existent_py_file)
        self.assertIsNone(result_dispatch)


if __name__ == '__main__':
    unittest.main()
