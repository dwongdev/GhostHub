#!/usr/bin/env python3
"""
GhostHub Stress Test Report Generator
-------------------------------------
Generates comprehensive HTML and Markdown reports from stress test results.
Includes charts, summaries, and recommendations for Raspberry Pi optimization.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class ReportGenerator:
    """Generates stress test reports."""
    
    def __init__(self, results_dir: str):
        self.results_dir = Path(results_dir)
        self.data = {
            'monitor': None,
            'load_tests': [],
            'worst_case': None,
            'results': None
        }
    
    def load_results(self):
        """Load all result files from the directory."""
        if not self.results_dir.exists():
            print(f"Results directory not found: {self.results_dir}")
            return False
        
        # Load monitor data
        for f in self.results_dir.glob("stress_test_*.json"):
            with open(f) as fp:
                self.data['monitor'] = json.load(fp)
            break
        
        # Load worst case results
        for f in self.results_dir.glob("worst_case_*.json"):
            with open(f) as fp:
                self.data['worst_case'] = json.load(fp)
            break
        
        # Load main results
        results_file = self.results_dir / "results.json"
        if results_file.exists():
            with open(results_file) as fp:
                self.data['results'] = json.load(fp)
        
        # Load individual load test results
        for pattern in ["*_results.json"]:
            for f in self.results_dir.glob(pattern):
                if 'worst_case' not in f.name:
                    with open(f) as fp:
                        self.data['load_tests'].append({
                            'name': f.stem.replace('_results', ''),
                            'data': json.load(fp)
                        })
        
        return True
    
    def calculate_statistics(self, values: List[float]) -> Dict:
        """Calculate basic statistics for a list of values."""
        if not values:
            return {'min': 0, 'max': 0, 'avg': 0, 'samples': 0}
        
        return {
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'samples': len(values)
        }
    
    def get_recommendations(self) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []
        
        # Check monitor data
        if self.data['monitor']:
            samples = self.data['monitor'].get('samples', [])
            
            if samples:
                temps = [s.get('cpu_temp', 0) for s in samples]
                mem_vals = [s.get('memory', {}).get('percent', 0) for s in samples]
                
                max_temp = max(temps) if temps else 0
                max_mem = max(mem_vals) if mem_vals else 0
                throttle_count = sum(1 for t in temps if t >= 80)
                
                if max_temp >= 85:
                    recommendations.append(
                        "🔴 **CRITICAL: CPU temperature exceeded 85°C** - Install active cooling "
                        "(fan + heatsinks) immediately to prevent thermal throttling and hardware damage."
                    )
                elif max_temp >= 80:
                    recommendations.append(
                        "🟠 **WARNING: CPU throttling detected** - Consider adding a cooling fan. "
                        "Passive heatsinks alone are insufficient for sustained heavy loads."
                    )
                elif max_temp >= 70:
                    recommendations.append(
                        "🟡 **NOTICE: CPU running warm** - Current cooling is adequate but monitor "
                        "during extended use. Ambient temperature affects performance."
                    )
                
                if max_mem >= 95:
                    recommendations.append(
                        "🔴 **CRITICAL: Memory nearly exhausted (>95%)** - Reduce concurrent clients, "
                        "limit thumbnail generation, or upgrade to Pi 4 with 4GB+ RAM."
                    )
                elif max_mem >= 85:
                    recommendations.append(
                        "🟠 **WARNING: High memory usage (>85%)** - Consider reducing MAX_CONCURRENT_CHUNKS "
                        "in uploadManager.js from 3 to 2, and limit simultaneous streams."
                    )
                elif max_mem >= 75:
                    recommendations.append(
                        "🟡 **NOTICE: Moderate memory pressure** - Monitor during peak usage. "
                        "SQLite WAL mode helps reduce memory spikes."
                    )
        
        # Check worst case results
        if self.data['worst_case']:
            health = self.data['worst_case'].get('health_summary', {})
            test_results = self.data['worst_case'].get('test_results', {})
            
            # Check for errors in tests
            total_errors = 0
            for test_name, results in test_results.items():
                if isinstance(results, dict):
                    total_errors += results.get('errors', 0)
            
            if total_errors > 10:
                recommendations.append(
                    f"🟠 **WARNING: {total_errors} errors during worst-case test** - "
                    "Review nginx timeout settings and increase `proxy_read_timeout` for large uploads."
                )
        
        # General recommendations
        if not recommendations:
            recommendations.append(
                "✅ **System performed well** - Current configuration handles the tested load. "
                "Consider running longer duration tests (5-10 minutes) for sustained performance validation."
            )
        
        # Always add these
        recommendations.extend([
            "",
            "### General Optimization Tips for Raspberry Pi 4:",
            "- Use a high-quality SD card (A2 rated) or boot from USB SSD for better I/O",
            "- Ensure adequate power supply (5V 3A minimum)",
            "- Set `gpu_mem=16` in `/boot/config.txt` if not using GUI",
            "- Enable ZRAM for improved memory management: `sudo apt install zram-tools`",
            "- Consider overclocking to 2GHz with proper cooling (add `over_voltage=6` and `arm_freq=2000`)",
        ])
        
        return recommendations
    
    def generate_markdown(self) -> str:
        """Generate Markdown report."""
        lines = [
            "# GhostHub Stress Test Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Results Directory:** `{self.results_dir}`",
            "",
            "---",
            ""
        ]
        
        # System Information
        lines.extend([
            "## System Information",
            ""
        ])
        
        if self.data['monitor'] and self.data['monitor'].get('samples'):
            sample = self.data['monitor']['samples'][0]
            lines.extend([
                f"- **Test Duration:** {self.data['monitor'].get('sample_count', 0)} samples",
                f"- **Sampling Interval:** {self.data['monitor'].get('interval_seconds', 1)}s",
                ""
            ])
        
        # Executive Summary
        lines.extend([
            "## Executive Summary",
            ""
        ])
        
        if self.data['results']:
            tests = self.data['results'].get('tests', [])
            passed = sum(1 for t in tests if t.get('success'))
            total = len(tests)
            
            if total > 0:
                pass_rate = 100 * passed / total
                status = "✅ PASSED" if pass_rate >= 80 else "⚠️ NEEDS ATTENTION" if pass_rate >= 50 else "❌ FAILED"
                lines.extend([
                    f"**Overall Status:** {status}",
                    f"**Tests Passed:** {passed}/{total} ({pass_rate:.0f}%)",
                    ""
                ])
        
        # System Metrics
        if self.data['monitor'] and self.data['monitor'].get('samples'):
            samples = self.data['monitor']['samples']
            
            cpu_vals = [s.get('cpu_percent', 0) for s in samples]
            temp_vals = [s.get('cpu_temp', 0) for s in samples]
            mem_vals = [s.get('memory', {}).get('percent', 0) for s in samples]
            
            cpu_stats = self.calculate_statistics(cpu_vals)
            temp_stats = self.calculate_statistics(temp_vals)
            mem_stats = self.calculate_statistics(mem_vals)
            
            lines.extend([
                "## System Metrics During Testing",
                "",
                "| Metric | Minimum | Maximum | Average |",
                "|--------|---------|---------|---------|",
                f"| CPU Usage | {cpu_stats['min']:.1f}% | {cpu_stats['max']:.1f}% | {cpu_stats['avg']:.1f}% |",
                f"| CPU Temperature | {temp_stats['min']:.1f}°C | {temp_stats['max']:.1f}°C | {temp_stats['avg']:.1f}°C |",
                f"| Memory Usage | {mem_stats['min']:.1f}% | {mem_stats['max']:.1f}% | {mem_stats['avg']:.1f}% |",
                ""
            ])
            
            # Throttling check
            throttle_count = sum(1 for t in temp_vals if t >= 80)
            if throttle_count > 0:
                lines.extend([
                    f"⚠️ **Thermal Throttling Detected:** {throttle_count} samples "
                    f"({100*throttle_count/len(temp_vals):.1f}%) above 80°C",
                    ""
                ])
        
        # Individual Test Results
        if self.data['results'] and self.data['results'].get('tests'):
            lines.extend([
                "## Test Results",
                "",
                "| Test Name | Status | Duration | Notes |",
                "|-----------|--------|----------|-------|"
            ])
            
            for test in self.data['results']['tests']:
                status = "✅ Pass" if test.get('success') else "❌ Fail"
                duration = f"{test.get('duration_seconds', 0):.1f}s"
                notes = f"Exit code: {test.get('exit_code', 'N/A')}"
                lines.append(f"| {test.get('name', 'Unknown')} | {status} | {duration} | {notes} |")
            
            lines.append("")
        
        # Worst Case Results
        if self.data['worst_case']:
            lines.extend([
                "## Worst Case Scenario Results",
                "",
                f"**Duration:** {self.data['worst_case'].get('duration_seconds', 0):.1f}s",
                ""
            ])
            
            test_results = self.data['worst_case'].get('test_results', {})
            if test_results:
                lines.extend([
                    "### Load Test Metrics",
                    "",
                    "| Test | Requests/Messages | Bytes | Errors |",
                    "|------|-------------------|-------|--------|"
                ])
                
                for test_name, results in test_results.items():
                    if isinstance(results, dict):
                        requests = results.get('requests', results.get('messages', results.get('navigations', 0)))
                        bytes_val = results.get('bytes', 0)
                        errors = results.get('errors', 0)
                        bytes_str = f"{bytes_val / 1024 / 1024:.1f}MB" if bytes_val else "-"
                        lines.append(f"| {test_name} | {requests} | {bytes_str} | {errors} |")
                
                lines.append("")
        
        # Recommendations
        recommendations = self.get_recommendations()
        lines.extend([
            "## Recommendations",
            ""
        ])
        lines.extend(recommendations)
        lines.append("")
        
        # Files Generated
        lines.extend([
            "---",
            "",
            "## Files in Results Directory",
            ""
        ])
        
        for f in sorted(self.results_dir.glob("*")):
            if f.is_file():
                size = f.stat().st_size
                size_str = f"{size / 1024:.1f}KB" if size < 1024*1024 else f"{size / 1024 / 1024:.1f}MB"
                lines.append(f"- `{f.name}` ({size_str})")
        
        lines.extend([
            "",
            "---",
            "*Generated by GhostHub Stress Test Report Generator*"
        ])
        
        return "\n".join(lines)
    
    def generate_html(self) -> str:
        """Generate HTML report with styling."""
        markdown_content = self.generate_markdown()
        
        # Convert basic markdown to HTML
        html_content = markdown_content
        
        # Headers
        for i in range(3, 0, -1):
            html_content = html_content.replace(
                "\n" + "#" * i + " ",
                f"\n<h{i}>"
            ).replace(
                "\n<h{i}>",
                f"</h{i-1 if i > 1 else 'p'}>\n<h{i}>" if i > 1 else f"\n<h{i}>"
            )
        
        # Bold
        import re
        html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
        
        # Code
        html_content = re.sub(r'`(.+?)`', r'<code>\1</code>', html_content)
        
        # Tables (basic conversion)
        lines = html_content.split('\n')
        in_table = False
        new_lines = []
        
        for line in lines:
            if line.startswith('|'):
                if not in_table:
                    new_lines.append('<table class="results-table">')
                    in_table = True
                
                if '---' in line:
                    continue
                
                cells = [c.strip() for c in line.split('|')[1:-1]]
                row = '<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>'
                new_lines.append(row)
            else:
                if in_table:
                    new_lines.append('</table>')
                    in_table = False
                new_lines.append(line)
        
        if in_table:
            new_lines.append('</table>')
        
        body = '\n'.join(new_lines)
        
        # Wrap in HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GhostHub Stress Test Report</title>
    <style>
        :root {{
            --bg-color: #1a1a2e;
            --card-bg: #16213e;
            --text-color: #eee;
            --accent: #e94560;
            --success: #4ade80;
            --warning: #fbbf24;
            --error: #ef4444;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        h1, h2, h3 {{
            color: var(--accent);
            border-bottom: 1px solid var(--accent);
            padding-bottom: 0.5rem;
        }}
        
        h1 {{ font-size: 2rem; }}
        h2 {{ font-size: 1.5rem; margin-top: 2rem; }}
        h3 {{ font-size: 1.2rem; }}
        
        .results-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            background: var(--card-bg);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .results-table td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        
        .results-table tr:first-child td {{
            background: rgba(233, 69, 96, 0.2);
            font-weight: bold;
        }}
        
        .results-table tr:hover {{
            background: rgba(255,255,255,0.05);
        }}
        
        code {{
            background: rgba(255,255,255,0.1);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: 'Monaco', 'Consolas', monospace;
            font-size: 0.9em;
        }}
        
        strong {{
            color: var(--accent);
        }}
        
        hr {{
            border: none;
            border-top: 1px solid rgba(255,255,255,0.2);
            margin: 2rem 0;
        }}
        
        ul {{
            list-style-type: none;
            padding-left: 0;
        }}
        
        ul li {{
            padding: 0.5rem 0;
            padding-left: 1.5rem;
            position: relative;
        }}
        
        ul li:before {{
            content: "•";
            color: var(--accent);
            position: absolute;
            left: 0;
        }}
        
        .status-pass {{ color: var(--success); }}
        .status-fail {{ color: var(--error); }}
        .status-warn {{ color: var(--warning); }}
    </style>
</head>
<body>
{body}
</body>
</html>"""
        
        return html
    
    def save_reports(self, output_dir: str = None):
        """Save both Markdown and HTML reports."""
        if output_dir is None:
            output_dir = self.results_dir
        else:
            output_dir = Path(output_dir)
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save Markdown
        md_path = output_dir / "report.md"
        with open(md_path, 'w') as f:
            f.write(self.generate_markdown())
        print(f"Markdown report saved: {md_path}")
        
        # Save HTML
        html_path = output_dir / "report.html"
        with open(html_path, 'w') as f:
            f.write(self.generate_html())
        print(f"HTML report saved: {html_path}")
        
        return md_path, html_path


def main():
    parser = argparse.ArgumentParser(description='Generate GhostHub Stress Test Report')
    parser.add_argument('results_dir', nargs='?', default=None,
                        help='Directory containing test results (default: latest in stress_tests/results/)')
    parser.add_argument('--output', '-o', default=None,
                        help='Output directory for reports')
    parser.add_argument('--format', choices=['md', 'html', 'both'], default='both',
                        help='Report format (default: both)')
    
    args = parser.parse_args()
    
    # Find results directory
    if args.results_dir:
        results_dir = Path(args.results_dir)
    else:
        # Find latest results
        base_dir = Path(__file__).parent / "results"
        if base_dir.exists():
            run_dirs = sorted(base_dir.glob("run_*"), reverse=True)
            if run_dirs:
                results_dir = run_dirs[0]
            else:
                results_dir = base_dir
        else:
            print("No results directory found. Run stress tests first.")
            sys.exit(1)
    
    print(f"Loading results from: {results_dir}")
    
    generator = ReportGenerator(results_dir)
    
    if not generator.load_results():
        print("Failed to load results")
        sys.exit(1)
    
    # Generate reports
    output_dir = args.output if args.output else results_dir
    
    if args.format in ['md', 'both']:
        md_path = Path(output_dir) / "report.md"
        with open(md_path, 'w') as f:
            f.write(generator.generate_markdown())
        print(f"Markdown report: {md_path}")
    
    if args.format in ['html', 'both']:
        html_path = Path(output_dir) / "report.html"
        with open(html_path, 'w') as f:
            f.write(generator.generate_html())
        print(f"HTML report: {html_path}")
    
    print("\nReport generation complete!")


if __name__ == '__main__':
    main()
