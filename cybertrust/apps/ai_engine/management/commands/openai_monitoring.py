"""
Django management command for OpenAI API monitoring.

Usage:
    python manage.py openai_monitoring --action=report --days=30
    python manage.py openai_monitoring --action=health
    python manage.py openai_monitoring --action=alerts
    python manage.py openai_monitoring --action=export --format=csv
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from cybertrust.apps.ai_engine.monitoring import (
    get_openai_cost_report,
    get_error_report,
    check_service_health,
    check_cost_threshold,
    check_error_rate_threshold,
    get_monitoring_summary,
    APICallLog,
)
import csv
from datetime import datetime


class Command(BaseCommand):
    help = "OpenAI API monitoring and reporting"

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            default='report',
            choices=['report', 'health', 'alerts', 'export', 'summary'],
            help='Monitoring action to perform'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze'
        )
        parser.add_argument(
            '--format',
            type=str,
            default='text',
            choices=['text', 'csv', 'json'],
            help='Output format'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path'
        )

    def handle(self, *args, **options):
        action = options['action']
        days = options['days']
        output_format = options['format']
        output_file = options['output']

        try:
            if action == 'report':
                self.generate_cost_report(days, output_format, output_file)
            elif action == 'health':
                self.check_health()
            elif action == 'alerts':
                self.check_alerts()
            elif action == 'export':
                self.export_data(days, output_format, output_file)
            elif action == 'summary':
                self.print_summary()
        except Exception as e:
            raise CommandError(f"Monitoring failed: {str(e)}")

    def generate_cost_report(self, days, output_format, output_file):
        """Generate cost report."""
        report = get_openai_cost_report(days)
        
        if output_format == 'json':
            import json
            output = json.dumps(report, indent=2, default=str)
        else:  # text format
            output = self._format_cost_report_text(report)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Report saved to {output_file}"
                )
            )
        else:
            self.stdout.write(output)

    def check_health(self):
        """Check service health."""
        health = check_service_health()
        
        status_style = (
            self.style.SUCCESS
            if health['overall_status'] == 'healthy'
            else self.style.WARNING
        )
        
        output = f"\n{'='*60}\n"
        output += f"SERVICE HEALTH: {health['overall_status'].upper()}\n"
        output += f"{'='*60}\n\n"
        
        for service, status in health['services'].items():
            color = (
                self.style.SUCCESS
                if status == 'healthy'
                else self.style.WARNING
                if status == 'warning'
                else self.style.ERROR
            )
            output += f"  {service:<20} {color(status)}\n"
        
        self.stdout.write(output)

    def check_alerts(self):
        """Check for alerts."""
        alerts = []
        
        # Cost threshold
        if check_cost_threshold(threshold_usd=500):
            alerts.append(
                "⚠️  Daily OpenAI cost exceeds $500"
            )
        
        # Error rate threshold
        if check_error_rate_threshold(threshold_percent=5):
            alerts.append(
                "⚠️  Error rate exceeds 5%"
            )
        
        # Check error rate in last hour
        error_report = get_error_report(days=1)
        if error_report['error_rate_percent'] > 10:
            alerts.append(
                f"⚠️  Error rate in last 24h: {error_report['error_rate_percent']:.2f}%"
            )
        
        if alerts:
            output = "\n" + self.style.WARNING("ALERTS:") + "\n"
            for alert in alerts:
                output += f"  {alert}\n"
        else:
            output = "\n" + self.style.SUCCESS("✓ No active alerts") + "\n"
        
        self.stdout.write(output)

    def export_data(self, days, output_format, output_file):
        """Export monitoring data."""
        cutoff_date = timezone.now() - timezone.timedelta(days=days)
        logs = APICallLog.objects.filter(created_at__gte=cutoff_date)
        
        if output_format == 'csv':
            self._export_csv(logs, output_file)
        elif output_format == 'json':
            self._export_json(logs, output_file)

    def _export_csv(self, logs, output_file):
        """Export to CSV."""
        filepath = output_file or f"openai_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Date', 'Feature', 'Organization', 'User',
                'Model', 'Tokens', 'Cost (USD)', 'Status',
                'Duration (ms)', 'Error'
            ])
            
            for log in logs:
                writer.writerow([
                    log.created_at,
                    log.feature,
                    log.organization or 'N/A',
                    log.user or 'N/A',
                    log.model_used,
                    log.tokens_total,
                    f"${log.cost_usd:.6f}",
                    log.status,
                    log.duration_ms,
                    log.error_message or ''
                ])
        
        self.stdout.write(
            self.style.SUCCESS(f"Data exported to {filepath}")
        )

    def _export_json(self, logs, output_file):
        """Export to JSON."""
        import json
        
        filepath = output_file or f"openai_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        data = [
            {
                'date': log.created_at.isoformat(),
                'feature': log.feature,
                'organization': log.organization.name if log.organization else None,
                'user': log.user.email if log.user else None,
                'model': log.model_used,
                'tokens': log.tokens_total,
                'cost_usd': float(log.cost_usd),
                'status': log.status,
                'duration_ms': log.duration_ms,
                'error': log.error_message,
            }
            for log in logs
        ]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.stdout.write(
            self.style.SUCCESS(f"Data exported to {filepath}")
        )

    def print_summary(self):
        """Print monitoring summary."""
        summary = get_monitoring_summary()
        self.stdout.write(self.style.SUCCESS(summary))

    def _format_cost_report_text(self, report) -> str:
        """Format cost report as text."""
        output = "\n"
        output += "=" * 70 + "\n"
        output += "OPENAI API COST REPORT\n"
        output += "=" * 70 + "\n\n"
        
        # Summary section
        summary = report['summary']
        output += "SUMMARY\n"
        output += "-" * 70 + "\n"
        output += f"  Period: {report['date_start']} to {report['date_end']}\n"
        output += f"  Total Cost: ${summary['total_cost_usd']:.2f}\n"
        output += f"  Total Calls: {summary['total_calls']:,}\n"
        output += f"  Total Tokens: {summary['total_tokens']:,}\n"
        output += f"  Avg Cost/Call: ${summary['avg_cost_per_call']:.6f}\n"
        output += f"  Avg Tokens/Call: {summary['avg_tokens_per_call']}\n\n"
        
        # By feature
        output += "BY FEATURE\n"
        output += "-" * 70 + "\n"
        for feature, metrics in report['by_feature'].items():
            if metrics['cost'] > 0:
                output += f"  {feature:<20} ${metrics['cost']:>8.2f}  "
                output += f"({metrics['calls']:>4} calls)  "
                output += f"({metrics['tokens']:>6,} tokens)\n"
        output += "\n"
        
        # By organization (top 10)
        output += "BY ORGANIZATION (TOP 10)\n"
        output += "-" * 70 + "\n"
        sorted_orgs = sorted(
            report['by_organization'].items(),
            key=lambda x: x[1]['cost'],
            reverse=True
        )[:10]
        for org, metrics in sorted_orgs:
            output += f"  {org:<30} ${metrics['cost']:>8.2f}  "
            output += f"({metrics['calls']:>4} calls)\n"
        output += "\n"
        
        # Trend (last 7 days)
        output += "DAILY TREND (LAST 7 DAYS)\n"
        output += "-" * 70 + "\n"
        for entry in report['cost_trend'][-7:]:
            date = entry['date']
            cost = entry['cost_usd']
            calls = entry['calls']
            output += f"  {date}  ${cost:>8.2f}  ({calls:>3} calls)\n"
        output += "\n"
        
        output += "=" * 70 + "\n"
        
        return output
