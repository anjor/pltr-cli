"""
Output formatting utilities for CLI commands.
"""

import json
import csv
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from io import StringIO

from rich.console import Console
from rich.table import Table
from rich import print as rich_print


class OutputFormatter:
    """Handles different output formats for CLI commands."""

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize formatter.

        Args:
            console: Rich console instance (creates one if not provided)
        """
        self.console = console or Console()

    def format_output(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        format_type: str = "table",
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format data according to specified format.

        Args:
            data: Data to format
            format_type: Output format ('table', 'json', 'csv')
            output_file: Optional file path to write output

        Returns:
            Formatted string if no output file specified
        """
        if format_type == "json":
            return self._format_json(data, output_file)
        elif format_type == "csv":
            return self._format_csv(data, output_file)
        elif format_type == "table":
            return self._format_table(data, output_file)
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

    def _format_json(
        self, data: Any, output_file: Optional[str] = None
    ) -> Optional[str]:
        """Format data as JSON."""
        # Convert datetime objects to strings for JSON serialization
        data_serializable = self._make_json_serializable(data)
        json_str = json.dumps(data_serializable, indent=2, default=str)

        if output_file:
            with open(output_file, "w") as f:
                f.write(json_str)
            return None
        else:
            rich_print(json_str)
            return json_str

    def _format_csv(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """Format data as CSV."""
        if isinstance(data, dict):
            data = [data]

        if not data:
            csv_str = ""
        else:
            # Get all unique keys for the CSV header
            fieldnames_set: set[str] = set()
            for item in data:
                fieldnames_set.update(item.keys())
            fieldnames = sorted(fieldnames_set)

            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for item in data:
                # Convert complex objects to strings
                row = {}
                for key in fieldnames:
                    value = item.get(key)
                    if isinstance(value, (dict, list)):
                        row[key] = json.dumps(value)
                    elif value is None:
                        row[key] = ""
                    else:
                        row[key] = str(value)
                writer.writerow(row)

            csv_str = output.getvalue()

        if output_file:
            with open(output_file, "w") as f:
                f.write(csv_str)
            return None
        else:
            print(csv_str, end="")
            return csv_str

    def _format_table(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """Format data as a rich table."""
        if isinstance(data, dict):
            data = [data]

        if not data:
            if output_file:
                with open(output_file, "w") as f:
                    f.write("No data to display\n")
                return None
            else:
                self.console.print("No data to display")
                return "No data to display"

        # Create table
        table = Table(show_header=True, header_style="bold blue")

        # Get all unique columns
        columns_set: set[str] = set()
        for item in data:
            columns_set.update(item.keys())
        columns = sorted(columns_set)

        # Add columns to table
        for column in columns:
            table.add_column(column, overflow="fold")

        # Add rows
        for item in data:
            row = []
            for column in columns:
                value = item.get(column)
                if isinstance(value, (dict, list)):
                    # Format complex objects as JSON
                    row.append(json.dumps(value, indent=2))
                elif value is None:
                    row.append("")
                elif isinstance(value, datetime):
                    row.append(value.isoformat())
                else:
                    row.append(str(value))
            table.add_row(*row)

        if output_file:
            # For file output, convert to plain text
            with open(output_file, "w") as f:
                console = Console(file=f, force_terminal=False)
                console.print(table)
            return None
        else:
            self.console.print(table)
            return str(table)

    def _make_json_serializable(self, data: Any) -> Any:
        """Convert data to JSON-serializable format."""
        if isinstance(data, dict):
            return {k: self._make_json_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._make_json_serializable(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data

    def format_dataset_list(
        self,
        datasets: List[Dict[str, Any]],
        format_type: str = "table",
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format dataset list with specific columns.

        Args:
            datasets: List of dataset dictionaries
            format_type: Output format
            output_file: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        # Select and order key columns for dataset display
        formatted_datasets = []
        for dataset in datasets:
            formatted_dataset = {
                "RID": dataset.get("rid", ""),
                "Name": dataset.get("name", ""),
                "Created": self._format_datetime(dataset.get("created_time")),
                "Size": self._format_file_size(dataset.get("size_bytes")),
                "Description": dataset.get("description", "")[:50] + "..."
                if dataset.get("description", "")
                else "",
            }
            formatted_datasets.append(formatted_dataset)

        return self.format_output(formatted_datasets, format_type, output_file)

    def format_dataset_detail(
        self,
        dataset: Dict[str, Any],
        format_type: str = "table",
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format detailed dataset information.

        Args:
            dataset: Dataset dictionary
            format_type: Output format
            output_file: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        if format_type == "table":
            # For table format, show key-value pairs (only show fields that exist)
            details = []

            if dataset.get("rid"):
                details.append({"Property": "RID", "Value": dataset["rid"]})
            if dataset.get("name"):
                details.append({"Property": "Name", "Value": dataset["name"]})
            if dataset.get("parent_folder_rid"):
                details.append(
                    {"Property": "Parent Folder", "Value": dataset["parent_folder_rid"]}
                )

            # Add any other fields that might exist
            for key, value in dataset.items():
                if (
                    key not in ["rid", "name", "parent_folder_rid"]
                    and value is not None
                    and value != ""
                ):
                    details.append(
                        {"Property": key.replace("_", " ").title(), "Value": str(value)}
                    )

            return self.format_output(details, format_type, output_file)
        else:
            return self.format_output(dataset, format_type, output_file)

    def format_file_list(
        self,
        files: List[Dict[str, Any]],
        format_type: str = "table",
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format file list with specific columns.

        Args:
            files: List of file dictionaries
            format_type: Output format
            output_file: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        # Format files for display
        formatted_files = []
        for file in files:
            formatted_file = {
                "Path": file.get("path", ""),
                "Size": self._format_file_size(file.get("size_bytes")),
                "Last Modified": self._format_datetime(file.get("last_modified")),
                "Transaction": file.get("transaction_rid", "")[:12] + "..."
                if file.get("transaction_rid")
                else "",
            }
            formatted_files.append(formatted_file)

        return self.format_output(formatted_files, format_type, output_file)

    def _format_datetime(self, dt: Any) -> str:
        """Format datetime for display."""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(dt)

    def _format_file_size(self, size_bytes: Optional[int]) -> str:
        """Format file size in human-readable format."""
        if size_bytes is None:
            return ""

        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.1f} MB"
        else:
            return f"{size_bytes / (1024**3):.1f} GB"

    def print_success(self, message: str):
        """Print success message with formatting."""
        self.console.print(f"✅ {message}", style="green")

    def print_error(self, message: str):
        """Print error message with formatting."""
        self.console.print(f"❌ {message}", style="red")

    def print_warning(self, message: str):
        """Print warning message with formatting."""
        self.console.print(f"⚠️  {message}", style="yellow")

    def print_info(self, message: str):
        """Print info message with formatting."""
        self.console.print(f"ℹ️  {message}", style="blue")

    def format_table(
        self,
        data: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
        format: str = "table",
        output: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format data as a table with specified columns.

        Args:
            data: List of dictionaries to format
            columns: List of column names to display (uses all if None)
            format: Output format ('table', 'json', 'csv')
            output: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        if columns:
            # Filter data to only include specified columns
            filtered_data = []
            for item in data:
                filtered_item = {col: item.get(col) for col in columns}
                filtered_data.append(filtered_item)
            data = filtered_data

        return self.format_output(data, format, output)

    def format_list(
        self,
        data: List[Any],
        format: str = "table",
        output: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format a list of items.

        Args:
            data: List of items to format
            format: Output format ('table', 'json', 'csv')
            output: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        # Convert list items to dicts if needed
        if data and not isinstance(data[0], dict):
            data = [{"value": item} for item in data]

        return self.format_output(data, format, output)

    def format_dict(
        self,
        data: Dict[str, Any],
        format: str = "table",
        output: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format a dictionary for display.

        Args:
            data: Dictionary to format
            format: Output format ('table', 'json', 'csv')
            output: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        if format == "table":
            # Convert to key-value pairs for table display
            table_data = [{"Property": k, "Value": str(v)} for k, v in data.items()]
            return self.format_output(table_data, format, output)
        else:
            return self.format_output(data, format, output)

    def display(self, data: Any, format_type: str = "table") -> None:
        """
        Display data using the appropriate formatter.

        Args:
            data: Data to display
            format_type: Display format ('table', 'json', 'csv')
        """
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                self.format_output(data, format_type)
            else:
                self.format_list(data, format_type)
        elif isinstance(data, dict):
            self.format_dict(data, format_type)
        else:
            # For simple values, just print them
            if format_type == "json":
                rich_print(json.dumps(data, indent=2, default=str))
            else:
                rich_print(str(data))

    def save_to_file(self, data: Any, file_path: Any, format_type: str) -> None:
        """
        Save data to a file in the specified format.

        Args:
            data: Data to save
            file_path: Path object or string for output file
            format_type: File format ('table', 'json', 'csv')
        """
        file_path_str = str(file_path)

        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                self.format_output(data, format_type, file_path_str)
            else:
                self.format_list(data, format_type, file_path_str)
        elif isinstance(data, dict):
            self.format_dict(data, format_type, file_path_str)
        else:
            # For simple values, save as text
            with open(file_path_str, "w") as f:
                if format_type == "json":
                    json.dump(data, f, indent=2, default=str)
                else:
                    f.write(str(data))

    def format_sql_results(
        self,
        results: Any,
        format_type: str = "table",
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format SQL query results for display.

        Args:
            results: Query results (could be dict, list, or other types)
            format_type: Output format ('table', 'json', 'csv')
            output_file: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        # Handle different types of SQL results
        if isinstance(results, dict):
            # Check for special result types
            if "text" in results:
                # Text result - display as-is
                text_data = results["text"]
                if output_file:
                    with open(output_file, "w") as f:
                        f.write(text_data)
                    return None
                else:
                    rich_print(text_data)
                    return text_data
            elif "type" in results and results["type"] == "binary":
                # Binary result - show metadata
                return self.format_output(results, format_type, output_file)
            elif "results" in results:
                # Results array
                return self.format_output(results["results"], format_type, output_file)
            elif "result" in results:
                # Single result
                single_result = results["result"]
                if isinstance(single_result, (dict, list)):
                    return self.format_output(single_result, format_type, output_file)
                else:
                    # Simple value
                    display_data = [{"Result": single_result}]
                    return self.format_output(display_data, format_type, output_file)
            else:
                # Regular dictionary
                return self.format_dict(results, format_type, output_file)
        elif isinstance(results, list):
            # List of results
            return self.format_output(results, format_type, output_file)
        else:
            # Simple value
            display_data = [{"Result": results}]
            return self.format_output(display_data, format_type, output_file)

    def format_query_status(
        self,
        status_info: Dict[str, Any],
        format_type: str = "table",
        output_file: Optional[str] = None,
    ) -> Optional[str]:
        """
        Format query status information.

        Args:
            status_info: Query status dictionary
            format_type: Output format ('table', 'json', 'csv')
            output_file: Optional output file path

        Returns:
            Formatted string if no output file specified
        """
        if format_type == "table":
            # Convert to key-value display for better readability
            display_data = []
            for key, value in status_info.items():
                display_data.append(
                    {"Property": key.replace("_", " ").title(), "Value": str(value)}
                )
            return self.format_output(display_data, format_type, output_file)
        else:
            return self.format_output(status_info, format_type, output_file)
