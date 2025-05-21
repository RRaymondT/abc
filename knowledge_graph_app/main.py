# Main application file.

import argparse
import os
import logging
import sys

from src.tech_scanner import detect_technologies
from src.code_parser import parse_file
from src.graph_builder import KnowledgeGraph
from src.visualizer import export_graph_to_json, run_server
from src.llm_export import export_graph_to_markdown

# Define supported extensions for parsing.
# Some are full filenames (e.g. 'pom.xml') if they are specific and don't have a unique extension.
SUPPORTED_EXTENSIONS = {
    '.py', '.java', '.js', '.ts', '.cs',  # Code files
    '.xml', '.bpmn',  # XML-based and BPMN
    '.html', '.vue',  # Frontend
    '.json',  # Data files, sometimes config
    '.csproj', '.sln',  # C# project/solution
    'pom.xml', 'package.json', 'requirements.txt'  # Build/dependency files
}

def setup_logging():
    """Configures basic logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    logging.info("Logging configured.")

def main():
    """Main function to drive the knowledge graph generation and output."""
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Codebase Knowledge Graph Generator. Analyzes a software project to build and visualize/export its knowledge graph."
    )
    parser.add_argument(
        "codebase_path",
        help="Path to the codebase directory to analyze."
    )
    parser.add_argument(
        "--output_mode",
        choices=['view', 'llm_markdown'],
        default='view',
        help="'view' to launch web visualizer, 'llm_markdown' to save Markdown summary."
    )
    parser.add_argument(
        "--llm_output_file",
        default='knowledge_graph_summary.md',
        help="Output file for LLM Markdown summary (default: knowledge_graph_summary.md)."
    )
    parser.add_argument(
        "--port",
        default=5000,
        type=int,
        help="Port for the visualization web server (default: 5000)."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for the visualization web server (default: 127.0.0.1)."
    )
    parser.add_argument(
        "--llm_filter_main_entities",
        action='store_true', # Default is False if not present
        default=False,
        help="If set, LLM export will only include primary code entities from the specified codebase path."
    )
    parser.add_argument(
        "--max_files_parse",
        type=int,
        default=None,
        help="Optional limit on the number of files to parse for very large codebases."
    )
    args = parser.parse_args()

    logging.info(f"Starting application with arguments: {args}")

    # Validate codebase_path
    if not os.path.isdir(args.codebase_path):
        logging.error(f"Invalid codebase_path: '{args.codebase_path}' is not a directory.")
        sys.exit(1)
    
    codebase_abs_path = os.path.abspath(args.codebase_path)
    logging.info(f"Validated codebase path: {codebase_abs_path}")

    # --- Technology Scanning ---
    logging.info("Starting technology scanning...")
    try:
        tech_scan_results = detect_technologies(codebase_abs_path)
        logging.info("Technology scanning completed.")
        # Log a summary of what was found
        if tech_scan_results:
            logging.info("Tech Scan Summary:")
            if tech_scan_results.get("project_files"):
                for tech, files in tech_scan_results["project_files"].items():
                    if files: logging.info(f"  - Project Files for {tech}: {len(files)}")
            if tech_scan_results.get("keyword_scan"):
                for tech, files in tech_scan_results["keyword_scan"].items():
                    if files: logging.info(f"  - Keyword Hits for {tech}: {len(files)}")
        else:
            logging.warning("Technology scanning returned no results.")
    except Exception as e:
        logging.error(f"Error during technology scanning: {e}", exc_info=True)
        tech_scan_results = {} # Ensure it exists for graph builder

    # --- Code Parsing ---
    logging.info("Starting code parsing...")
    parsed_data_all_files = {}
    files_parsed_count = 0
    files_processed_for_parsing_attempt = 0

    for root, _, files in os.walk(codebase_abs_path):
        if args.max_files_parse is not None and files_parsed_count >= args.max_files_parse:
            logging.info(f"Reached maximum file parsing limit ({args.max_files_parse}). Skipping further files.")
            break
        for file_name in files:
            # Check if we already hit limit in inner loop
            if args.max_files_parse is not None and files_parsed_count >= args.max_files_parse:
                break

            full_file_path = os.path.join(root, file_name)
            _, extension = os.path.splitext(file_name)
            
            # Filter by SUPPORTED_EXTENSIONS or exact filenames
            is_supported = extension.lower() in SUPPORTED_EXTENSIONS or \
                           file_name in SUPPORTED_EXTENSIONS
            
            if is_supported:
                files_processed_for_parsing_attempt += 1
                logging.debug(f"Attempting to parse: {full_file_path}")
                try:
                    file_analysis_result = parse_file(full_file_path)
                    if file_analysis_result:
                        parsed_data_all_files[full_file_path] = file_analysis_result
                        files_parsed_count += 1
                        logging.debug(f"Successfully parsed: {full_file_path}")
                    else:
                        logging.debug(f"No analysis result for {full_file_path} (e.g. not a supported type by parser, or empty).")
                except Exception as e:
                    logging.error(f"Error parsing file {full_file_path}: {e}", exc_info=False) # Keep log less verbose for common parse errors

    logging.info(f"Code parsing completed. Attempted to parse {files_processed_for_parsing_attempt} supported files. Successfully parsed {files_parsed_count} files.")

    # --- Knowledge Graph Building ---
    logging.info("Starting knowledge graph building...")
    kg = KnowledgeGraph()
    try:
        kg.load_graph_from_directory(codebase_abs_path, tech_scan_results, parsed_data_all_files)
        graph = kg.get_graph()
        logging.info(f"Knowledge graph building completed. Graph has {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")
    except Exception as e:
        logging.error(f"Error during knowledge graph building: {e}", exc_info=True)
        sys.exit(1) # Critical error, cannot proceed

    # --- Output Handling ---
    logging.info(f"Selected output mode: {args.output_mode}")
    if args.output_mode == 'view':
        logging.info("Exporting graph data to JSON for visualization...")
        try:
            graph_json = export_graph_to_json(graph)
            logging.info(f"Starting visualization server on http://{args.host}:{args.port}")
            run_server(graph_json, host=args.host, port=args.port) # Debug is False by default in run_server
        except Exception as e:
            logging.error(f"Error during visualization setup or server run: {e}", exc_info=True)
            sys.exit(1)

    elif args.output_mode == 'llm_markdown':
        logging.info("Generating LLM Markdown summary...")
        try:
            # codebase_abs_path is already defined
            markdown_summary = export_graph_to_markdown(
                graph,
                main_project_entities_only=args.llm_filter_main_entities,
                codebase_path_prefix=codebase_abs_path if args.llm_filter_main_entities else None
            )
            with open(args.llm_output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_summary)
            logging.info(f"LLM Markdown summary successfully saved to: {args.llm_output_file}")
        except IOError as e:
            logging.error(f"IOError writing LLM Markdown summary to {args.llm_output_file}: {e}", exc_info=True)
            sys.exit(1)
        except Exception as e:
            logging.error(f"Error generating LLM Markdown summary: {e}", exc_info=True)
            sys.exit(1)
    else:
        logging.error(f"Invalid output_mode: {args.output_mode}. Should not happen due to argparse choices.")
        sys.exit(1)

    logging.info("Application finished successfully.")

if __name__ == "__main__":
    main()
