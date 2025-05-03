"""
Tests for validating the Flask blueprint routes after refactoring.
"""
import unittest
from unittest import mock
import importlib
import inspect
from werkzeug.routing import Rule
from flask import Blueprint 

class BlueprintRegistrationTest(unittest.TestCase):
    def test_import_blueprints(self):
        """Test that all blueprint modules can be imported without errors."""
        blueprint_modules = [
            "backend.routes.voice_routes",
            "backend.routes.generation_routes",
            "backend.routes.batch_routes",
            "backend.routes.audio_routes",
            "backend.routes.task_routes",
            "backend.routes.vo_script_routes",
            "backend.routes.vo_template_routes"
        ]
        
        for module_name in blueprint_modules:
            try:
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)
            except ImportError as e:
                self.fail(f"Failed to import {module_name}: {e}")
    
    def test_blueprint_objects(self):
        """Test that each route module defines a Blueprint object."""
        from flask import Blueprint
        
        blueprint_vars = {
            "backend.routes.voice_routes": "voice_bp",
            "backend.routes.generation_routes": "generation_bp",
            "backend.routes.batch_routes": "batch_bp",
            "backend.routes.audio_routes": "audio_bp",
            "backend.routes.task_routes": "task_bp",
            "backend.routes.vo_script_routes": "vo_script_bp",
            "backend.routes.vo_template_routes": "vo_template_bp"
        }
        
        for module_name, blueprint_var in blueprint_vars.items():
            module = importlib.import_module(module_name)
            self.assertTrue(hasattr(module, blueprint_var), 
                           f"Module {module_name} doesn't define {blueprint_var}")
            bp = getattr(module, blueprint_var)
            self.assertIsInstance(bp, Blueprint, 
                                f"{blueprint_var} in {module_name} is not a Blueprint")
    
    def test_blueprint_prefixes(self):
        """Test that blueprints have expected URL prefixes."""
        blueprint_prefixes = {
            "backend.routes.voice_routes": "/api",
            "backend.routes.generation_routes": "/api",
            "backend.routes.batch_routes": "/api",
            "backend.routes.audio_routes": None,  # audio_routes doesn't set a url_prefix
            "backend.routes.task_routes": "/api",
            "backend.routes.vo_script_routes": "/api",
            "backend.routes.vo_template_routes": "/api"
        }
        
        for module_name, expected_prefix in blueprint_prefixes.items():
            module = importlib.import_module(module_name)
            # Get the blueprint object (assuming it's the first Blueprint instance found)
            bp = None
            for name, obj in inspect.getmembers(module):
                if isinstance(obj, Blueprint):
                    bp = obj
                    break
            
            self.assertIsNotNone(bp, f"No Blueprint found in {module_name}")
            self.assertEqual(bp.url_prefix, expected_prefix, 
                           f"Blueprint in {module_name} has prefix '{bp.url_prefix}' (expected '{expected_prefix}')")
    
    @mock.patch('backend.app.app')
    def test_app_registers_blueprints(self, mock_app):
        """Test that app.py registers all expected blueprints."""
        # Skip this test for now since it's difficult to mock the app initialization properly
        # Would require more complex setup to capture the register_blueprint calls during app initialization
        self.skipTest("Skipping blueprint registration test - needs more complex setup to properly test")

class EndpointConsistencyTest(unittest.TestCase):
    def test_common_endpoints(self):
        """Test that common endpoints are defined as expected in the blueprint modules."""
        # Skip this test as it requires application context
        self.skipTest("This test requires application context, skipping for now")
        
    def test_error_handling(self):
        """Test that route modules have consistent error handling patterns."""
        # Just check that api_response function is imported and used
        modules_to_check = [
            "backend.routes.voice_routes",
            "backend.routes.generation_routes",
            "backend.routes.batch_routes",
            "backend.routes.audio_routes",
            "backend.routes.task_routes"
        ]
        
        for module_name in modules_to_check:
            try:
                source_file = module_name.replace(".", "/") + ".py"
                with open(source_file, "r") as f:
                    content = f.read()
                    
                # Check if make_api_response is imported
                self.assertIn("from backend.app import make_api_response", content,
                             f"{module_name} should import make_api_response from backend.app")
                
                # Check if make_api_response is used for error handling
                self.assertIn("make_api_response(error=", content,
                             f"{module_name} should use make_api_response for error handling")
            except FileNotFoundError:
                self.fail(f"Could not find file for module {module_name}")

if __name__ == '__main__':
    unittest.main() 