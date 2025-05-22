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

    def test_parse_csharp_dbcontext(self):
        """Test parsing of C# DbContext with EF Core configurations."""
        CSHARP_EF_CODE = """
using Microsoft.EntityFrameworkCore;
using System.Collections.Generic;

namespace MyProject.Data
{
    public class Blog
    {
        public int BlogId { get; set; }
        public string Url { get; set; }
        public List<Post> Posts { get; set; }
    }

    public class Post
    {
        public int PostId { get; set; }
        public string Title { get; set; }
        public string Content { get; set; }
        public int BlogId { get; set; } // Foreign Key
        public Blog Blog { get; set; }  // Navigation Property
    }

    public class MyAppContext : DbContext
    {
        public DbSet<Blog> Blogs { get; set; }
        public DbSet<Post> Posts { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.Entity<Blog>()
                .HasKey(b => b.BlogId); // Single key

            modelBuilder.Entity<Blog>().Property(b => b.Url).IsRequired(); // Simple property

            modelBuilder.Entity<Post>(entity => { // Lambda for entity
                entity.HasKey(p => p.PostId);
                entity.Property(p => p.Title)
                      .IsRequired()
                      .HasMaxLength(200);
                entity.HasOne(p => p.Blog) // Defines relationship Post -> Blog
                      .WithMany(b => b.Posts) // Blog has many Posts
                      .HasForeignKey(p => p.BlogId); // Foreign key in Post
            });
        }
    }
}
"""
        cs_file = self._create_file('test_ef.cs', CSHARP_EF_CODE)
        from code_parser import parse_csharp_file # Ensure direct import for specific test
        result = parse_csharp_file(cs_file)

        self.assertIsNotNone(result)
        self.assertEqual(len(result['namespaces']), 1)
        ns_info = result['namespaces'][0]
        self.assertEqual(ns_info['name'], "MyProject.Data")
        
        dbcontext_class_info = next((c for c in ns_info['classes'] if c['name'] == 'MyAppContext'), None)
        self.assertIsNotNone(dbcontext_class_info)
        self.assertTrue(dbcontext_class_info['is_dbcontext'])
        
        # Test DbSets
        self.assertEqual(len(dbcontext_class_info['db_sets']), 2)
        db_set_names = {ds['property_name'] for ds in dbcontext_class_info['db_sets']}
        self.assertIn('Blogs', db_set_names)
        self.assertIn('Posts', db_set_names)
        blog_dbset = next(ds for ds in dbcontext_class_info['db_sets'] if ds['property_name'] == 'Blogs')
        self.assertEqual(blog_dbset['entity_name'], 'Blog')

        # Test EF Configurations
        ef_configs = dbcontext_class_info['ef_configurations']
        self.assertGreaterEqual(len(ef_configs), 4) # Expect at least HasKey, Property, HasKey, Property, HasOne/WithMany

        blog_haskey_config = next((c for c in ef_configs if c['entity_configured'] == 'Blog' and c['call_type'] == 'HasKey'), None)
        self.assertIsNotNone(blog_haskey_config)
        self.assertIn('BlogId', blog_haskey_config['details'].get('keys_found', []))

        blog_prop_url_config = next((c for c in ef_configs if c['entity_configured'] == 'Blog' and c['call_type'] == 'Property' and c['details'].get('property_name') == 'Url'), None)
        self.assertIsNotNone(blog_prop_url_config)
        self.assertTrue(blog_prop_url_config['details'].get('is_required'))

        post_haskey_config = next((c for c in ef_configs if c['entity_configured'] == 'Post' and c['call_type'] == 'HasKey'), None)
        self.assertIsNotNone(post_haskey_config)
        self.assertIn('PostId', post_haskey_config['details'].get('keys_found', []))

        post_prop_title_config = next((c for c in ef_configs if c['entity_configured'] == 'Post' and c['call_type'] == 'Property' and c['details'].get('property_name') == 'Title'), None)
        self.assertIsNotNone(post_prop_title_config)
        self.assertTrue(post_prop_title_config['details'].get('is_required'))
        self.assertEqual(post_prop_title_config['details'].get('max_length'), 200)
        
        post_rel_blog_config = next((c for c in ef_configs if c['entity_configured'] == 'Post' and c['call_type'] == 'HasOne_WithMany'), None)
        self.assertIsNotNone(post_rel_blog_config)
        # Based on current _parse_ef_onmodelcreating_body, details might be like:
        # {'one_arg': None, 'many_arg': None, 'nav_prop': 'Posts'} for HasOne(p => p.Blog).WithMany(b => b.Posts)
        # The parser needs to be robust in capturing these details. For this test, we check what's plausible.
        # The example `_parse_ef_onmodelcreating_body` was simplified and might not provide all these details perfectly.
        # This test will pass if the call_type is identified. Details might need parser refinement.
        self.assertEqual(post_rel_blog_config['details'].get('nav_prop'), "Posts") # p.Blog is source nav, b.Posts is target nav

    def test_parse_python_data_flow(self):
        """Test parsing of Python code for basic data flow links."""
        PYTHON_DATA_FLOW_CODE = """
def source_a():
    return "data_a"

def source_b():
    return "data_b"

def process_ab(input_a, input_b="default_b"):
    res = input_a + input_b
    return res

def sink_c(data_c):
    print(data_c)

def main_flow_test():
    var_a = source_a()  # var_a from source_a
    var_b = source_b()  # var_b from source_b
    
    # var_a (from source_a) flows to process_ab as input_a (arg_index 0)
    # var_b (from source_b) flows to process_ab as input_b (keyword_arg_name 'input_b')
    processed_data = process_ab(var_a, input_b=var_b) 
    
    # processed_data (from process_ab) flows to sink_c as data_c (arg_index 0)
    sink_c(processed_data) 
"""
        py_file = self._create_file('test_data_flow.py', PYTHON_DATA_FLOW_CODE)
        result = parse_python_file(py_file)
        self.assertIsNotNone(result)
        
        main_flow_func_info = next((f for f in result['functions'] if f['name'] == 'main_flow_test'), None)
        self.assertIsNotNone(main_flow_func_info)
        
        data_flows = main_flow_func_info['data_flow_links']
        self.assertEqual(len(data_flows), 3) # Expecting three links

        # Flow 1: source_a -> process_ab
        flow1 = next((df for df in data_flows if df['source_function'] == 'source_a' and df['target_function'] == 'process_ab'), None)
        self.assertIsNotNone(flow1)
        self.assertEqual(flow1['intermediate_variable'], 'var_a')
        self.assertEqual(flow1['arg_index'], 0) # var_a is the first positional argument

        # Flow 2: source_b -> process_ab
        flow2 = next((df for df in data_flows if df['source_function'] == 'source_b' and df['target_function'] == 'process_ab'), None)
        self.assertIsNotNone(flow2)
        self.assertEqual(flow2['intermediate_variable'], 'var_b')
        self.assertEqual(flow2['keyword_arg_name'], 'input_b')

        # Flow 3: process_ab -> sink_c
        flow3 = next((df for df in data_flows if df['source_function'] == 'process_ab' and df['target_function'] == 'sink_c'), None)
        self.assertIsNotNone(flow3)
        self.assertEqual(flow3['intermediate_variable'], 'processed_data')
        self.assertEqual(flow3['arg_index'], 0)


if __name__ == '__main__':
    unittest.main()
