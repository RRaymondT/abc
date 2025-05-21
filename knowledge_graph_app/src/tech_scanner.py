# This module will be responsible for scanning the codebase for technologies used.
import os
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

PROJECT_FILE_MAP = {
    "Maven": "pom.xml",
    "NPM": "package.json",
    "CSharp": ".csproj", # Matches files ENDING with .csproj
    "Python": "requirements.txt",
    # Add more project file types here
}

# Define relevant extensions for keyword scanning
RELEVANT_EXTENSIONS = ['.java', '.cs', '.js', '.xml', '.bpmn', '.py', '.html', '.json']


def identify_project_files(codebase_path: str) -> dict:
    """
    Scans the codebase_path to identify common project files.

    Args:
        codebase_path: The root path of the codebase to scan.

    Returns:
        A dictionary mapping technology names (derived from project file types)
        to lists of found file paths.
        Example: {"Maven": ["/path/to/pom.xml"], "NPM": ["/path/to/package.json"]}
    """
    identified_files = {tech: [] for tech in PROJECT_FILE_MAP.keys()}
    logging.info(f"Starting project file scan in: {codebase_path}")
    for root, _, files in os.walk(codebase_path):
        for file_name in files:
            for tech, proj_file_pattern in PROJECT_FILE_MAP.items():
                # Ensure exact match for files like requirements.txt or pom.xml
                if proj_file_pattern.startswith('.'): # like .csproj
                    if file_name.endswith(proj_file_pattern):
                        file_path = os.path.join(root, file_name)
                        try:
                            # Basic check to see if file is readable
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                f.read(1) # Try to read a single byte
                            identified_files[tech].append(file_path)
                            logging.debug(f"Identified project file: {file_path} for technology: {tech}")
                        except IOError as e:
                            logging.warning(f"Could not read file {file_path}: {e}")
                        except Exception as e:
                            logging.error(f"An unexpected error occurred while processing file {file_path}: {e}")
                else: # like pom.xml or requirements.txt
                     if file_name == proj_file_pattern:
                        file_path = os.path.join(root, file_name)
                        try:
                            # Basic check to see if file is readable
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                f.read(1) # Try to read a single byte
                            identified_files[tech].append(file_path)
                            logging.debug(f"Identified project file: {file_path} for technology: {tech}")
                        except IOError as e:
                            logging.warning(f"Could not read file {file_path}: {e}")
                        except Exception as e:
                            logging.error(f"An unexpected error occurred while processing file {file_path}: {e}")

    logging.info(f"Project file scan completed. Found: { {k:v for k,v in identified_files.items() if v} }")
    return identified_files


def scan_for_keywords(codebase_path: str, tech_keywords: dict) -> dict:
    """
    Scans files in the codebase for specific keywords related to technologies.

    Args:
        codebase_path: The root path of the codebase to scan.
        tech_keywords: A dictionary where keys are technology names and values are
                       lists of regex patterns to search for.

    Returns:
        A dictionary mapping technology names to lists of file paths where
        keywords were found.
        Example: {"Camunda": ["/path/to/some_file.bpmn"]}
    """
    found_keywords = {tech: set() for tech in tech_keywords.keys()} # Use set to avoid duplicate file paths
    logging.info(f"Starting keyword scan in: {codebase_path}")

    for root, _, files in os.walk(codebase_path):
        for file_name in files:
            _, file_extension = os.path.splitext(file_name)
            if file_extension.lower() in RELEVANT_EXTENSIONS:
                file_path = os.path.join(root, file_name)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f_content:
                        # Read the whole file content, consider chunking for very large files if memory becomes an issue
                        content = f_content.read()
                        for tech, patterns in tech_keywords.items():
                            for pattern in patterns:
                                try:
                                    if re.search(pattern, content, re.IGNORECASE):
                                        found_keywords[tech].add(file_path)
                                        logging.debug(f"Found keyword for {tech} (pattern: '{pattern}') in {file_path}")
                                        break # Move to the next tech for this file once a pattern is found
                                except re.error as e:
                                    logging.warning(f"Regex error for pattern '{pattern}' on file {file_path}: {e}")
                                    # Optionally, skip this pattern for other files or handle as needed
                except IOError as e:
                    logging.warning(f"Could not read file {file_path} for keyword scanning: {e}")
                except Exception as e:
                    logging.error(f"An unexpected error occurred while keyword scanning file {file_path}: {e}")
    
    # Convert sets to lists for the final output
    result = {tech: list(paths) for tech, paths in found_keywords.items()}
    logging.info(f"Keyword scan completed. Found: { {k:v for k,v in result.items() if v} }")
    return result


DEFAULT_TECH_KEYWORDS = {
    "Camunda": [r"org\.camunda\.bpm", r"camunda-bpm-spring-boot-starter", r"<bpmn:process"],
    "AutoMapper": [r"AutoMapper", r"CreateMap"], # C# specific
    "Refit": [r"Refit\.For<"], # C# specific
    "Vue.js": [r"new Vue\(", r"v-for", r"<template>"], # JS/HTML context
    "Spring Framework": [r"org\.springframework", r"@Service", r"@Component", r"@RestController"], # Java
    ".NET Core/Framework": [r"Microsoft\.Extensions", r"System\.Web\.Mvc", r"Microsoft\.AspNetCore"], # C#
    "React": [r"React\.createElement", r"useState\("], # JS
    "Angular": [r"@angular/core", r"NgModule"], # JS/TS
    "Java": [r"import\s+java\.(util|lang|io|net|sql)\.", r"public\s+class", r"System\.out\.println"],
    "CSharp": [r"namespace\s+\w+", r"using\s+System;", r"public\s+class\s+\w+\s*\{"],
    "Python": [r"import\s+(os|sys|re|django|flask|numpy|pandas)", r"def\s+\w+\(.*\):", r"class\s+\w+\(.*\):"]
}


def detect_technologies(codebase_path: str) -> dict:
    """
    Detects technologies used in a codebase by identifying project files and
    scanning for keywords.

    Args:
        codebase_path: The root path of the codebase.

    Returns:
        A dictionary containing the identified project files and keyword scan results.
        Example:
        {
            "project_files": {"Maven": ["path/to/pom.xml"]},
            "keyword_scan": {"Camunda": ["path/to/file.bpmn"]}
        }
    """
    logging.info(f"Starting technology detection for codebase: {codebase_path}")
    if not os.path.isdir(codebase_path):
        logging.error(f"Invalid codebase path: {codebase_path}. Path does not exist or is not a directory.")
        return {
            "project_files": {},
            "keyword_scan": {}
        }

    project_files_results = identify_project_files(codebase_path)
    keyword_scan_results = scan_for_keywords(codebase_path, DEFAULT_TECH_KEYWORDS)

    detected_tech = {
        "project_files": project_files_results,
        "keyword_scan": keyword_scan_results
    }
    logging.info(f"Technology detection completed. Results: {detected_tech}")
    return detected_tech

if __name__ == '__main__':
    # Example usage:
    # Create a dummy project structure for testing
    if not os.path.exists("dummy_project"):
        os.makedirs("dummy_project/src/main/java/com/example")
        os.makedirs("dummy_project/src/main/resources/bpmn")
        os.makedirs("dummy_project/static/js")
        os.makedirs("dummy_project/app/models")

    with open("dummy_project/pom.xml", "w") as f:
        f.write("<project><modelVersion>4.0.0</modelVersion><groupId>com.example</groupId><artifactId>my-app</artifactId><version>1.0</version>"
                "<dependencies><dependency><groupId>org.camunda.bpm</groupId><artifactId>camunda-external-task-client</artifactId><version>7.15.0</version></dependency></dependencies></project>")
    
    with open("dummy_project/src/main/java/com/example/MyApplication.java", "w") as f:
        f.write("package com.example; import org.springframework.boot.SpringApplication; public class MyApplication { public static void main(String[] args) { SpringApplication.run(MyApplication.class, args); System.out.println(\"Hello Java!\"); } }")

    with open("dummy_project/src/main/resources/bpmn/my_process.bpmn", "w") as f:
        f.write("<?xml version=\"1.0\" encoding=\"UTF-8\"?><bpmn:definitions xmlns:bpmn=\"http://www.omg.org/spec/BPMN/20100524/MODEL\"><bpmn:process id=\"Process_1\" isExecutable=\"true\"></bpmn:process></bpmn:definitions>")

    with open("dummy_project/package.json", "w") as f:
        f.write("{\"name\": \"my-frontend\", \"version\": \"0.1.0\", \"dependencies\": {\"vue\": \"^2.6.14\"}}")

    with open("dummy_project/static/js/app.js", "w") as f:
        f.write("new Vue({ el: '#app', data: { message: 'Hello Vue!' } });")
        
    with open("dummy_project/my_csharp_project.csproj", "w") as f:
        f.write("<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net5.0</TargetFramework></PropertyGroup><ItemGroup><PackageReference Include=\"AutoMapper\" Version=\"10.1.1\" /><PackageReference Include=\"Refit\" Version=\"6.0.38\" /></ItemGroup></Project>")

    with open("dummy_project/app/models/user.py", "w") as f:
        f.write("import os\nclass User:\n  def __init__(self, name):\n    self.name = name")
        
    with open("dummy_project/requirements.txt", "w") as f:
        f.write("flask==2.0.1\nnumpy>=1.20")

    test_codebase_path = "dummy_project"
    detected_technologies = detect_technologies(test_codebase_path)
    
    print("\n--- Detected Technologies ---")
    if detected_technologies.get("project_files"):
        print("\nProject Files Found:")
        for tech, files in detected_technologies["project_files"].items():
            if files:
                print(f"  {tech}: {files}")
    
    if detected_technologies.get("keyword_scan"):
        print("\nKeyword Scan Results:")
        for tech, files in detected_technologies["keyword_scan"].items():
            if files:
                print(f"  {tech}: {files}")

    # Clean up dummy project (optional)
    # import shutil
    # shutil.rmtree("dummy_project")
    # print("\nCleaned up dummy project.")
