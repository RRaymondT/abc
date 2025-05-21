import unittest
import os
import tempfile
import shutil
import logging

# Adjust the path to import from the src directory
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from tech_scanner import detect_technologies, PROJECT_FILE_MAP, DEFAULT_TECH_KEYWORDS, RELEVANT_EXTENSIONS

class TestTechScanner(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Disable logging during tests for cleaner output
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        # Re-enable logging
        logging.disable(logging.NOTSET)

    def _create_file(self, filename, content=""):
        """Helper method to create a file in the temporary directory."""
        file_path = os.path.join(self.temp_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True) # Ensure directory exists
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path

    def test_identify_project_files(self):
        """Test identification of common project files."""
        pom_path = self._create_file('pom.xml', '<project></project>')
        package_json_path = self._create_file('package.json', '{}')
        csproj_path = self._create_file('myproject.csproj', '<Project></Project>')
        requirements_path = self._create_file('requirements.txt', 'flask==1.0')
        
        # Create a subdirectory and place a file there too
        sub_dir = os.path.join(self.temp_dir, "subdir")
        os.makedirs(sub_dir, exist_ok=True)
        pom_in_subdir_path = self._create_file('subdir/pom.xml', '<project name="sub"></project>')

        results = detect_technologies(self.temp_dir)
        
        project_files_found = results['project_files']

        self.assertIn(pom_path, project_files_found.get('Maven', []))
        self.assertIn(pom_in_subdir_path, project_files_found.get('Maven', []))
        self.assertIn(package_json_path, project_files_found.get('NPM', []))
        self.assertIn(csproj_path, project_files_found.get('CSharp', []))
        self.assertIn(requirements_path, project_files_found.get('Python', []))
        
        # Check expected number of files for each type
        self.assertEqual(len(project_files_found.get('Maven', [])), 2)
        self.assertEqual(len(project_files_found.get('NPM', [])), 1)
        self.assertEqual(len(project_files_found.get('CSharp', [])), 1)
        self.assertEqual(len(project_files_found.get('Python', [])), 1)


    def test_scan_for_keywords(self):
        """Test scanning for keywords in various file types."""
        java_file_path = self._create_file('Service.java', 'import org.camunda.bpm.engine.DelegateExecution; public class MyService {}')
        cs_file_path = self._create_file('MyController.cs', 'using AutoMapper; namespace TestApp { public class MyController { } }')
        js_file_path = self._create_file('app.js', 'new Vue({ el: "#app" });')
        bpmn_file_path = self._create_file('process.bpmn', '<bpmn:process id="p1"></bpmn:process>')
        
        # A file that should not match Camunda keywords
        self._create_file('other.xml', '<root><element>Some other XML</element></root>')


        results = detect_technologies(self.temp_dir)
        keyword_scan_results = results['keyword_scan']

        self.assertIn(java_file_path, keyword_scan_results.get('Camunda', []))
        self.assertIn(bpmn_file_path, keyword_scan_results.get('Camunda', [])) # Camunda pattern matches <bpmn:process
        self.assertIn(cs_file_path, keyword_scan_results.get('AutoMapper', []))
        self.assertIn(js_file_path, keyword_scan_results.get('Vue.js', []))
        
        # Check specific counts to ensure only relevant files are matched
        self.assertEqual(len(keyword_scan_results.get('Camunda', [])), 2)
        self.assertEqual(len(keyword_scan_results.get('AutoMapper', [])), 1)
        self.assertEqual(len(keyword_scan_results.get('Vue.js', [])), 1)
        
        # Test for a technology with multiple keywords, e.g. Java
        self._create_file('AnotherJava.java', 'public class AnotherJava { System.out.println("Hello"); }')
        results_after_more_java = detect_technologies(self.temp_dir) # Re-scan
        # Should match general Java keyword and Camunda (if applicable)
        self.assertIn(java_file_path, results_after_more_java['keyword_scan'].get('Java', []))
        self.assertIn(os.path.join(self.temp_dir, 'AnotherJava.java'), results_after_more_java['keyword_scan'].get('Java', []))


    def test_no_relevant_files(self):
        """Test behavior when no relevant project files or keywords are found."""
        self._create_file('empty.txt', 'This is a text file.')
        self._create_file('data.dat', 'Some binary data.')

        results = detect_technologies(self.temp_dir)
        
        # Check that project_files dictionary has all keys from PROJECT_FILE_MAP, but with empty lists
        for tech in PROJECT_FILE_MAP.keys():
            self.assertEqual(results['project_files'].get(tech, []), [])
            
        # Check that keyword_scan dictionary has all keys from DEFAULT_TECH_KEYWORDS, but with empty lists
        for tech in DEFAULT_TECH_KEYWORDS.keys():
            self.assertEqual(results['keyword_scan'].get(tech, []), [])

    def test_invalid_codebase_path(self):
        """Test behavior with an invalid codebase path."""
        invalid_path = os.path.join(self.temp_dir, "non_existent_dir")
        results = detect_technologies(invalid_path)
        # Expect empty results as the path is invalid and logged as an error by the scanner
        self.assertEqual(results.get('project_files', {}), {})
        self.assertEqual(results.get('keyword_scan', {}), {})

    def test_file_read_error_project_files(self):
        """Test that unreadable project files are handled gracefully."""
        # Create a readable project file
        readable_pom = self._create_file('pom.xml', '<project></project>')
        # Create a file that will be made unreadable
        unreadable_pom_path = self._create_file('unreadable_pom.xml', '<project></project>')
        
        # Make it unreadable (OS-dependent, works on POSIX)
        # On Windows, this might not prevent reading by the same user.
        # A more robust test might involve mocking open().
        original_mode = os.stat(unreadable_pom_path).st_mode
        try:
            os.chmod(unreadable_pom_path, 0o000) # No read/write/execute permissions
        except PermissionError: # Some OS might not allow removing read permission like this
            logging.warning("Could not set file to unreadable for test_file_read_error_project_files. Test may be less effective.")
            self.skipTest("Could not set file to unreadable to test read errors effectively.")
            return


        results = detect_technologies(self.temp_dir)
        # The readable file should be found
        self.assertIn(readable_pom, results['project_files'].get('Maven', []))
        # The unreadable file should not be in the list, or if it is, it's an issue with the test setup
        # The code logs a warning, so it shouldn't raise an error.
        # We expect it to be skipped.
        self.assertNotIn(unreadable_pom_path, results['project_files'].get('Maven', []),
                         "Unreadable project file was included in results.")
        
        # Restore permissions to allow tearDown to remove it
        os.chmod(unreadable_pom_path, original_mode)


    def test_file_read_error_keyword_scan(self):
        """Test that unreadable files are handled gracefully during keyword scanning."""
        readable_java = self._create_file('Readable.java', 'import org.camunda.bpm.engine;')
        unreadable_java_path = self._create_file('Unreadable.java', 'import org.camunda.bpm.engine;')

        original_mode = os.stat(unreadable_java_path).st_mode
        try:
            os.chmod(unreadable_java_path, 0o000)
        except PermissionError:
            logging.warning("Could not set file to unreadable for test_file_read_error_keyword_scan. Test may be less effective.")
            self.skipTest("Could not set file to unreadable to test read errors effectively.")
            return

        results = detect_technologies(self.temp_dir)
        self.assertIn(readable_java, results['keyword_scan'].get('Camunda', []))
        self.assertNotIn(unreadable_java_path, results['keyword_scan'].get('Camunda', []),
                         "Unreadable file was included in keyword scan results.")
        
        os.chmod(unreadable_java_path, original_mode)


if __name__ == '__main__':
    unittest.main()
