"""
Tests for validating all of the blueprint routes using the real database.
"""
import unittest
import json
from backend.app import app

class BlueprintRoutesLiveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test fixtures before running tests."""
        # Configure the Flask app for testing
        app.config['TESTING'] = True
        cls.client = app.test_client()

    def test_ping_endpoint(self):
        """Test the ping endpoint."""
        response = self.client.get('/api/ping')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('message', data['data'])
        self.assertEqual(data['data']['message'], 'pong from Flask!')
    
    # === Voice Routes Tests ===
    
    def test_voices_endpoint(self):
        """Test the voices endpoint."""
        response = self.client.get('/api/voices')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('data', data)
        # ElevenLabs should return multiple voices
        self.assertGreater(len(data['data']), 0)
    
    def test_models_endpoint(self):
        """Test the models endpoint."""
        response = self.client.get('/api/models')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('data', data)
        # Should return multiple models
        self.assertGreater(len(data['data']), 0)
    
    # === Generation Routes Tests ===
    
    def test_jobs_endpoint(self):
        """Test the jobs listing endpoint."""
        response = self.client.get('/api/jobs')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('data', data)
        # The data should be a list (may be empty if no jobs exist yet)
        self.assertIsInstance(data['data'], list)
    
    # === Batch Routes Tests ===
    
    def test_batches_endpoint(self):
        """Test the batches listing endpoint."""
        response = self.client.get('/api/batches')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('data', data)
        # The data should be a list (may be empty if no batches exist yet)
        self.assertIsInstance(data['data'], list)
    
    # === VO Script Routes Tests ===
    
    def test_vo_scripts_endpoint(self):
        """Test the VO scripts listing endpoint."""
        response = self.client.get('/api/vo-scripts')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('data', data)
        # The data should be a list (may be empty if no scripts exist yet)
        self.assertIsInstance(data['data'], list)
    
    # === VO Template Routes Tests ===
    
    def test_vo_script_templates_endpoint(self):
        """Test the VO script templates listing endpoint."""
        response = self.client.get('/api/vo-script-templates')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('data', data)
        # The data should be a list (may be empty if no templates exist yet)
        self.assertIsInstance(data['data'], list)
    
    # === Task Routes Tests ===
    
    def test_task_status_endpoint_nonexistent(self):
        """Test the task status endpoint with a nonexistent task ID."""
        # Using a dummy task ID that almost certainly doesn't exist
        response = self.client.get('/api/task/nonexistent-task-id-12345/status')
        self.assertEqual(response.status_code, 200)  # Note: The endpoint returns 200 even for unknown tasks
        data = json.loads(response.data)
        self.assertIn('data', data)
        self.assertIn('status', data['data'])
        # Should return a status like PENDING for unknown tasks
        self.assertEqual(data['data']['status'], 'PENDING')
    
    # === Endpoint Validation Tests ===
    
    def test_validate_endpoint_format(self):
        """Test multiple endpoints to validate consistent response format."""
        # List of endpoints to check
        endpoints = [
            '/api/ping',
            '/api/voices',
            '/api/models',
            '/api/jobs',
            '/api/batches',
            '/api/vo-scripts',
            '/api/vo-script-templates'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # All should return 200 OK
            self.assertEqual(response.status_code, 200, f"Endpoint {endpoint} failed with status {response.status_code}")
            
            # All should have consistent response format with 'data' key
            data = json.loads(response.data)
            self.assertIn('data', data, f"Endpoint {endpoint} missing 'data' key in response")
    
    def test_bad_endpoints_error_format(self):
        """Test error responses for consistency."""
        # List of non-existent endpoints or endpoints with incorrect methods
        bad_tests = [
            # Non-existent endpoints
            {'endpoint': '/api/nonexistent', 'method': 'get'},
            # Endpoints with incorrect method
            {'endpoint': '/api/ping', 'method': 'post'},
        ]
        
        for test in bad_tests:
            method = getattr(self.client, test['method'])
            response = method(test['endpoint'])
            
            # Should return 4xx error
            self.assertGreaterEqual(response.status_code, 400, 
                                 f"{test['method'].upper()} {test['endpoint']} should return error status")
            
            # Some endpoints might return HTML for 404, so we'll check content-type
            if 'application/json' in response.content_type:
                data = json.loads(response.data)
                # Error responses should have 'error' key
                self.assertIn('error', data, 
                           f"{test['method'].upper()} {test['endpoint']} missing 'error' key in response")

if __name__ == '__main__':
    unittest.main() 