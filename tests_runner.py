"""
Comprehensive test runner and test configuration.

Run tests with:
    pytest  # Run all tests
    pytest cybertrust/apps/ai_engine/  # Run specific app
    pytest cybertrust/apps/ai_engine/test_services.py::ChatbotServiceTests  # Run specific test class
    pytest --cov  # Run with coverage report
"""
import os
import django
from django.conf import settings
from django.test.utils import get_runner

# Configure Django settings before running tests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybertrust.config.settings.test')

# Setup Django
django.setup()

# After Django setup, we can run tests
if __name__ == "__main__":
    from django.test.runner import DiscoverRunner
    
    runner = DiscoverRunner(verbosity=2, interactive=False, keepdb=False)
    failures = runner.run_tests(["cybertrust"])
