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
