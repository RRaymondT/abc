import unittest
import os
import tempfile
import shutil
import json
import logging
import yaml # For YAMLError

# Adjust the path to import from the src directory
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from config_parser import parse_kubernetes_yaml_file

class TestConfigParser(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Disable most logging for cleaner test output, but allow errors to be seen
        logging.disable(logging.WARNING) # Show WARNING, ERROR, CRITICAL

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        logging.disable(logging.NOTSET) # Re-enable all logging

    def _create_file(self, filename, content=""):
        """Helper method to create a file in the temporary directory."""
        file_path = os.path.join(self.temp_dir, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path

    def test_parse_k8s_yaml_basic(self):
        """Parse YAML with a Deployment and a Service."""
        K8S_YAML_BASIC = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-deployment
  namespace: test-ns
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: main-container
        image: myrepo/my-app:1.0.0
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: my-app-service
  namespace: test-ns
spec:
  selector:
    app: my-app
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: ClusterIP
"""
        yaml_file = self._create_file("basic.yaml", K8S_YAML_BASIC)
        results = parse_kubernetes_yaml_file(yaml_file)
        
        self.assertEqual(len(results), 2)

        deployment = next((r for r in results if r['kind'] == 'Deployment'), None)
        self.assertIsNotNone(deployment)
        self.assertEqual(deployment['name'], 'my-app-deployment')
        self.assertEqual(deployment['namespace'], 'test-ns')
        self.assertEqual(len(deployment['containers']), 1)
        self.assertEqual(deployment['containers'][0]['name'], 'main-container')
        self.assertEqual(deployment['containers'][0]['image'], 'myrepo/my-app:1.0.0')
        self.assertEqual(deployment['containers'][0]['ports'][0]['containerPort'], 8080)

        service = next((r for r in results if r['kind'] == 'Service'), None)
        self.assertIsNotNone(service)
        self.assertEqual(service['name'], 'my-app-service')
        self.assertEqual(service['namespace'], 'test-ns')
        self.assertEqual(service['service_type'], 'ClusterIP')
        self.assertEqual(service['selector']['app'], 'my-app')
        self.assertEqual(service['ports'][0]['port'], 80)

    def test_parse_k8s_multi_document(self):
        """Assert multiple resource dicts are returned from a multi-doc YAML."""
        K8S_MULTI_DOC = """
kind: ConfigMap
apiVersion: v1
metadata:
  name: cm1
---
kind: ConfigMap
apiVersion: v1
metadata:
  name: cm2
"""
        yaml_file = self._create_file("multi.yaml", K8S_MULTI_DOC)
        results = parse_kubernetes_yaml_file(yaml_file)
        self.assertEqual(len(results), 2)
        self.assertTrue(any(r['name'] == 'cm1' for r in results))
        self.assertTrue(any(r['name'] == 'cm2' for r in results))

    def test_parse_k8s_empty_or_invalid(self):
        """Test with empty and malformed YAML."""
        # Empty file
        empty_file = self._create_file("empty.yaml", "")
        results_empty = parse_kubernetes_yaml_file(empty_file)
        self.assertEqual(results_empty, [])

        # Malformed YAML
        # Re-enable ERROR logging specifically for this test to check if it's logged
        logging.disable(logging.WARNING) # Temporarily disable WARNING to focus on ERROR
        logger = logging.getLogger() # Get root logger
        original_level = logger.getEffectiveLevel()
        logger.setLevel(logging.ERROR) # Ensure ERROR level messages are processed

        malformed_file = self._create_file("malformed.yaml", "kind: Deployment\n  name: test\n  bad-indent:")
        with self.assertLogs(level='ERROR') as log_cm:
            results_malformed = parse_kubernetes_yaml_file(malformed_file)
            self.assertEqual(results_malformed, [])
            # Check if YAMLError was logged
            self.assertTrue(any("Error parsing YAML file" in msg for msg in log_cm.output))
        
        logger.setLevel(original_level) # Restore original logging level
        logging.disable(logging.WARNING) # Re-disable WARNING as per setUp


    def test_parse_k8s_various_kinds(self):
        """Include ConfigMap, Secret, Job, CronJob."""
        K8S_VARIOUS_KINDS = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-config
data:
  key1: value1
  key2: |
    multi-line
    value
---
apiVersion: v1
kind: Secret
metadata:
  name: my-secret
type: Opaque
data:
  user: dXNlcg== # user -> base64
  pass: cGFzc3dvcmQ= # password -> base64
---
apiVersion: batch/v1
kind: Job
metadata:
  name: my-job
spec:
  template:
    spec:
      containers:
      - name: job-container
        image: busybox
        command: ["echo", "Hello"]
      restartPolicy: Never
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: my-cronjob
spec:
  schedule: "*/5 * * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: cronjob-container
            image: busybox
            args:
            - /bin/sh
            - -c
            - date; echo Hello from the CronJob
          restartPolicy: OnFailure
"""
        yaml_file = self._create_file("various.yaml", K8S_VARIOUS_KINDS)
        results = parse_kubernetes_yaml_file(yaml_file)
        self.assertEqual(len(results), 4)

        cm = next((r for r in results if r['kind'] == 'ConfigMap'), None)
        self.assertIsNotNone(cm)
        self.assertEqual(cm['name'], 'my-config')
        self.assertIn('key1', cm['data_keys'])
        self.assertIn('key2', cm['data_keys'])

        secret = next((r for r in results if r['kind'] == 'Secret'), None)
        self.assertIsNotNone(secret)
        self.assertEqual(secret['name'], 'my-secret')
        self.assertIn('user', secret['data_keys'])
        self.assertIn('pass', secret['data_keys'])

        job = next((r for r in results if r['kind'] == 'Job'), None)
        self.assertIsNotNone(job)
        self.assertEqual(job['name'], 'my-job')
        self.assertEqual(len(job['containers']), 1)
        self.assertEqual(job['containers'][0]['name'], 'job-container')
        self.assertEqual(job['containers'][0]['image'], 'busybox')

        cronjob = next((r for r in results if r['kind'] == 'CronJob'), None)
        self.assertIsNotNone(cronjob)
        self.assertEqual(cronjob['name'], 'my-cronjob')
        self.assertEqual(len(cronjob['containers']), 1)
        self.assertEqual(cronjob['containers'][0]['name'], 'cronjob-container')
        self.assertEqual(cronjob['containers'][0]['image'], 'busybox')

if __name__ == '__main__':
    unittest.main()
