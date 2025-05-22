import yaml
import logging
import os
import json
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def parse_kubernetes_yaml_file(file_path: str) -> list:
    """
    Parses a Kubernetes YAML file, which may contain multiple documents,
    and extracts key information from each resource.

    Args:
        file_path: The path to the Kubernetes YAML file.

    Returns:
        A list of dictionaries, where each dictionary represents a parsed Kubernetes resource.
        Returns an empty list if the file is not found or if there's a parsing error.
    """
    parsed_resources = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        logging.error(f"K8s YAML file not found: {file_path}")
        return parsed_resources
    except Exception as e:
        logging.error(f"Error reading K8s YAML file {file_path}: {e}")
        return parsed_resources

    try:
        docs = list(yaml.safe_load_all(content)) # Use list to consume generator for multiple uses if needed
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file {file_path}: {e}")
        return parsed_resources

    for doc_index, doc in enumerate(docs):
        if not isinstance(doc, dict):
            logging.warning(f"Skipping non-dictionary document #{doc_index+1} in {file_path}")
            continue

        kind = doc.get('kind', 'UnknownKind')
        api_version = doc.get('apiVersion', 'UnknownVersion')
        
        metadata = doc.get('metadata', {})
        if not isinstance(metadata, dict): # Ensure metadata is a dict, even if specified as non-dict in YAML
            logging.warning(f"Metadata in document #{doc_index+1} in {file_path} is not a dictionary. Using empty metadata.")
            metadata = {}
            
        resource_name = metadata.get('name', f"Unnamed_{kind}_{doc_index+1}") # Add index for unnamed uniqueness
        namespace = metadata.get('namespace', 'default')
        labels = metadata.get('labels')

        resource_info = {
            'file_path': file_path,
            'kind': kind,
            'api_version': api_version,
            'name': resource_name,
            'namespace': namespace,
            'labels': labels if labels else {} # Ensure labels is a dict, not None
        }

        # Deployment/StatefulSet/Job/CronJob Specifics
        if kind in ['Deployment', 'StatefulSet', 'Job', 'CronJob']:
            spec = doc.get('spec', {})
            template = spec.get('template', {}) if isinstance(spec, dict) else {}
            template_spec = template.get('spec', {}) if isinstance(template, dict) else {}
            containers_spec = template_spec.get('containers', []) if isinstance(template_spec, dict) else []
            
            resource_info['containers'] = []
            if isinstance(containers_spec, list):
                for c in containers_spec:
                    if isinstance(c, dict):
                         resource_info['containers'].append({
                            'name': c.get('name'), 
                            'image': c.get('image'), 
                            'ports': c.get('ports') # ports is a list of dicts
                        })
                    else:
                        logging.warning(f"Container spec item in {resource_name} ({kind}) is not a dict: {c}")


        # Service Specifics
        elif kind == 'Service':
            service_spec = doc.get('spec', {})
            if isinstance(service_spec, dict):
                resource_info['service_type'] = service_spec.get('type')
                resource_info['ports'] = service_spec.get('ports') # ports is a list of dicts
                resource_info['selector'] = service_spec.get('selector') # selector is a dict

        # ConfigMap/Secret Specifics
        elif kind == 'ConfigMap':
            data_map = doc.get('data', {})
            resource_info['data_keys'] = list(data_map.keys()) if isinstance(data_map, dict) else []
        elif kind == 'Secret':
            secret_data = doc.get('data', {}) 
            resource_info['data_keys'] = list(secret_data.keys()) if isinstance(secret_data, dict) else []
        
        parsed_resources.append(resource_info)

    return parsed_resources

if __name__ == '__main__':
    EXAMPLE_K8S_YAML_CONTENT = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-deployment
  namespace: prod
  labels:
    app: my-app
    environment: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
      - name: my-app-container
        image: myregistry/my-app:1.2.3
        ports:
        - containerPort: 8080
          name: http
        - name: metrics
          containerPort: 9090
      - name: sidecar-container
        image: fluent/fluent-bit:latest
---
apiVersion: v1
kind: Service
metadata:
  name: my-app-service
  namespace: prod
spec:
  selector:
    app: my-app
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8080
      name: http-service
    - protocol: TCP
      port: 9090
      targetPort: 9090
      name: metrics-service
  type: LoadBalancer
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-app-config
  namespace: prod
data:
  DATABASE_URL: "postgres://user:pass@host:port/db"
  LOG_LEVEL: "info"
  FEATURE_FLAGS: |
    {
      "newAuth": true,
      "betaFeature": false
    }
---
# A document that is not a dictionary
- item1
- item2
---
# A document with missing kind/apiVersion and unusual metadata name
metadata:
  name:
    complexNamePart1: value1
    complexNamePart2: value2
spec:
  someValue: true
"""
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, "test_k8s.yaml")

    try:
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            f.write(EXAMPLE_K8S_YAML_CONTENT)

        print(f"--- Testing Kubernetes YAML Parser for {temp_file_path} ---")
        parsed_k8s_data = parse_kubernetes_yaml_file(temp_file_path)
        print(json.dumps(parsed_k8s_data, indent=2))
        
        # Basic assertions for the test
        assert len(parsed_k8s_data) == 3, f"Expected 3 valid resources, got {len(parsed_k8s_data)}"
        
        deployment = next((r for r in parsed_k8s_data if r['kind'] == 'Deployment'), None)
        assert deployment is not None, "Deployment not found"
        assert deployment['name'] == 'my-app-deployment'
        assert deployment['namespace'] == 'prod'
        assert 'app' in deployment['labels']
        assert len(deployment['containers']) == 2
        assert deployment['containers'][0]['name'] == 'my-app-container'
        assert deployment['containers'][0]['image'] == 'myregistry/my-app:1.2.3'
        assert len(deployment['containers'][0]['ports']) == 2

        service = next((r for r in parsed_k8s_data if r['kind'] == 'Service'), None)
        assert service is not None, "Service not found"
        assert service['name'] == 'my-app-service'
        assert service['service_type'] == 'LoadBalancer'
        assert 'app' in service['selector']
        assert len(service['ports']) == 2

        configmap = next((r for r in parsed_k8s_data if r['kind'] == 'ConfigMap'), None)
        assert configmap is not None, "ConfigMap not found"
        assert 'DATABASE_URL' in configmap['data_keys']
        assert 'LOG_LEVEL' in configmap['data_keys']
        assert 'FEATURE_FLAGS' in configmap['data_keys']

        print("\n--- Basic Assertions Passed ---")

    finally:
        shutil.rmtree(temp_dir)
        logging.info(f"Cleaned up temp directory: {temp_dir}")
