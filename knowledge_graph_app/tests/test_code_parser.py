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

    def test_parse_python_with_decorators(self):
        """Test parsing of Python code with decorators."""
        PYTHON_DECO_CODE = """
@class_decorator_one
@class_decorator_two(arg="value")
class MyDecoratedClass:
    @method_decorator_one
    def decorated_method(self):
        pass

@function_decorator(level=1)
def decorated_function():
    pass
"""
        py_file = self._create_file('test_decorators.py', PYTHON_DECO_CODE)
        result = parse_python_file(py_file)

        self.assertIsNotNone(result)
        self.assertEqual(len(result['classes']), 1)
        class_info = result['classes'][0]
        self.assertEqual(class_info['name'], 'MyDecoratedClass')
        self.assertIn('@class_decorator_one', class_info['decorators'])
        self.assertIn('@class_decorator_two(arg="value")', class_info['decorators'])
        
        self.assertEqual(len(class_info['methods']), 1)
        method_info = class_info['methods'][0]
        self.assertEqual(method_info['name'], 'decorated_method')
        self.assertIn('@method_decorator_one', method_info['decorators'])

        self.assertEqual(len(result['functions']), 1)
        func_info = result['functions'][0]
        self.assertEqual(func_info['name'], 'decorated_function')
        self.assertIn('@function_decorator(level=1)', func_info['decorators'])

    def test_parse_csharp_sample(self):
        """Test parsing of a sample C# file."""
        CSHARP_SAMPLE_CODE = """
using System;
using System.Collections.Generic;

namespace MyNamespace.SubNamespace
{
    [Serializable, Obsolete("Old class")]
    public class MyClass : BaseClass, IMyInterface
    {
        [MyPropertyAttrib]
        public string MyProperty { get; set; }

        [MyMethodAttrib(Value=123)]
        public int GetValue(string input)
        {
            return 0;
        }
    }

    public interface IMyInterface
    {
        void DoSomething();
    }
}
"""
        cs_file = self._create_file('test.cs', CSHARP_SAMPLE_CODE)
        # Need to import parse_csharp_file specifically if not using the main dispatcher parse_file
        from code_parser import parse_csharp_file 
        result = parse_csharp_file(cs_file)

        self.assertIsNotNone(result)
        self.assertIn("System", result['usings'])
        self.assertIn("System.Collections.Generic", result['usings'])
        
        self.assertEqual(len(result['namespaces']), 1)
        ns_info = result['namespaces'][0]
        self.assertEqual(ns_info['name'], "MyNamespace.SubNamespace")

        self.assertEqual(len(ns_info['classes']), 1)
        class_info = ns_info['classes'][0]
        self.assertEqual(class_info['name'], "MyClass")
        self.assertEqual(class_info['namespace'], "MyNamespace.SubNamespace")
        self.assertIn("Serializable", class_info['attributes'])
        self.assertIn("Obsolete", class_info['attributes'])
        self.assertEqual(class_info['base_types_str'], "BaseClass, IMyInterface")

        self.assertEqual(len(class_info['methods']), 1)
        method_info = class_info['methods'][0]
        self.assertEqual(method_info['name'], "GetValue")
        self.assertIn("MyMethodAttrib", method_info['attributes'])
        self.assertEqual(method_info['return_type'], "int")
        self.assertEqual(method_info['parameters_str'], "string input")

        self.assertEqual(len(class_info['properties']), 1)
        prop_info = class_info['properties'][0]
        self.assertEqual(prop_info['name'], "MyProperty")
        self.assertIn("MyPropertyAttrib", prop_info['attributes'])
        self.assertEqual(prop_info['type'], "string")

        self.assertEqual(len(ns_info['interfaces']), 1)
        iface_info = ns_info['interfaces'][0]
        self.assertEqual(iface_info['name'], "IMyInterface")
        self.assertEqual(len(iface_info['methods']), 1) # Assuming parser extracts method signatures from interfaces
        self.assertEqual(iface_info['methods'][0]['name'], "DoSomething")


    def test_parse_csharp_empty_or_minimal(self):
        """Test C# parser with empty or minimal content."""
        from code_parser import parse_csharp_file
        
        # Empty file
        empty_cs_file = self._create_file('empty.cs', "")
        result_empty = parse_csharp_file(empty_cs_file)
        self.assertIsNotNone(result_empty)
        self.assertEqual(result_empty['usings'], [])
        self.assertEqual(result_empty['namespaces'], [])
        self.assertEqual(result_empty['classes'], [])
        self.assertEqual(result_empty['interfaces'], [])

        # File with only a namespace
        minimal_cs_file = self._create_file('minimal.cs', "namespace Test.Empty {}")
        result_minimal = parse_csharp_file(minimal_cs_file)
        self.assertIsNotNone(result_minimal)
        self.assertEqual(len(result_minimal['namespaces']), 1)
        self.assertEqual(result_minimal['namespaces'][0]['name'], "Test.Empty")
        self.assertEqual(result_minimal['namespaces'][0]['classes'], [])
        self.assertEqual(result_minimal['namespaces'][0]['interfaces'], [])
        
        # File with only usings
        usings_only_file = self._create_file('usings_only.cs', "using System;\nusing System.Text;")
        result_usings = parse_csharp_file(usings_only_file)
        self.assertIsNotNone(result_usings)
        self.assertIn("System", result_usings['usings'])
        self.assertIn("System.Text", result_usings['usings'])
        self.assertEqual(result_usings['namespaces'], [])


    def test_parse_vue_sfc_sample(self):
        """Test parsing of a sample Vue SFC (.vue) file."""
        VUE_SFC_SAMPLE_CODE = """
<template>
  <div>
    <MyCustomComponent :prop-val="message" @clicked="handleClick" />
    <another-component @update:modelValue="val => dataProperty = val"></another-component>
  </div>
</template>
<script lang="ts">
import { ref, computed } from 'vue';
import Utility from '@/utils/utility';

export default {
  name: 'TestComponent',
  props: {
    message: String,
    count: { type: Number, default: 0 }
  },
  // props: ['message', 'count'], // Array syntax
  data() {
    return { dataProperty: 'initial' };
  },
  methods: {
    handleClick() { console.log('clicked'); },
    anotherMethod(arg1) { return arg1; }
  },
  computed: {
    processedMessage() { return this.message + '!'; }
  }
}
</script>
<style lang="scss" scoped> .text { color: blue; } </style>
"""
        vue_file = self._create_file('TestComponent.vue', VUE_SFC_SAMPLE_CODE)
        from code_parser import parse_vue_component # Import specific parser
        result = parse_vue_component(vue_file)

        self.assertIsNotNone(result)
        self.assertEqual(result['component_name'], 'TestComponent')
        self.assertEqual(result['script_lang'], 'ts')
        self.assertEqual(result['style_lang'], 'scss')
        
        self.assertIn('@/utils/utility', result['imports'])
        self.assertIn('vue', result['imports'])
        
        self.assertIn('message', result['props'])
        self.assertIn('count', result['props'])
        
        self.assertIn('dataProperty', result['data_properties'])
        
        self.assertIn('handleClick', result['methods'])
        self.assertIn('anotherMethod', result['methods'])
        
        self.assertIn('processedMessage', result['computed_properties'])
        
        self.assertIn('MyCustomComponent', result['template_components_used'])
        self.assertIn('another-component', result['template_components_used'])
        
        self.assertTrue(any(b['event'] == 'clicked' and b['handler'] == 'handleClick' for b in result['template_event_bindings']))
        self.assertTrue(any(b['event'] == 'update:modelValue' for b in result['template_event_bindings']))


    def test_parse_vue_minimal(self):
        """Test Vue SFC parser with minimal content."""
        from code_parser import parse_vue_component

        # Only template
        vue_template_only = self._create_file('TemplateOnly.vue', "<template><div></div></template>")
        result_template = parse_vue_component(vue_template_only)
        self.assertIsNotNone(result_template)
        self.assertEqual(result_template['component_name'], 'TemplateOnly') # Fallback to filename
        self.assertIsNone(result_template['script_lang']) # No script tag

        # Only script
        vue_script_only = self._create_file('ScriptOnly.vue', "<script>export default { name: 'MyScriptOnly' }</script>")
        result_script = parse_vue_component(vue_script_only)
        self.assertIsNotNone(result_script)
        self.assertEqual(result_script['component_name'], 'MyScriptOnly')
        self.assertEqual(result_script['script_lang'], 'javascript') # Default
        self.assertEqual(result_script['template_components_used'], [])


if __name__ == '__main__':
    unittest.main()
