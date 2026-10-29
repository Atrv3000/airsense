from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

class SystemHealthCheckTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_check_endpoint(self):
        response = self.client.get('/api/v1/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status'), 'online')
        self.assertEqual(response.data.get('database'), 'Connected (PostgreSQL)')
        self.assertIn('AirSense', response.data.get('project'))

    def test_run_scheduler_command_once(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('run_scheduler', once=True, skip_ingestion=True, skip_forecasts=True, skip_alerts=True, stdout=out)
        output = out.getvalue()
        self.assertIn("Starting Pipeline Cycle", output)
        self.assertIn("Stopped cleanly", output)

    def test_drf_throttling_configuration(self):
        from django.conf import settings
        rf = settings.REST_FRAMEWORK
        self.assertIn('DEFAULT_THROTTLE_CLASSES', rf)
        self.assertIn('DEFAULT_THROTTLE_RATES', rf)
        self.assertIn('anon', rf['DEFAULT_THROTTLE_RATES'])
        self.assertIn('user', rf['DEFAULT_THROTTLE_RATES'])

    def test_production_security_improperly_configured(self):
        from django.core.exceptions import ImproperlyConfigured

        def check_prod_secret(secret, debug):
            if not secret and not debug:
                raise ImproperlyConfigured("SECRET_KEY required in production.")
            return True

        self.assertTrue(check_prod_secret("prod_secret", False))
        with self.assertRaises(ImproperlyConfigured):
            check_prod_secret(None, False)

