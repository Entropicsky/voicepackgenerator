"""
Tests for validating the modular task structure after refactoring.
"""
import importlib
import unittest
from unittest import mock
import sys
import inspect

# Test if modules can be imported without errors
class TaskModuleImportTest(unittest.TestCase):
    def test_import_celery_app(self):
        try:
            from backend import celery_app
            self.assertIsNotNone(celery_app)
        except ImportError as e:
            self.fail(f"Failed to import celery_app: {e}")
    
    def test_import_task_modules(self):
        """Test that all task modules can be imported without errors."""
        module_names = [
            "backend.tasks",
            "backend.tasks.generation_tasks",
            "backend.tasks.regeneration_tasks",
            "backend.tasks.audio_tasks",
            "backend.tasks.script_tasks"
        ]
        
        for module_name in module_names:
            try:
                module = importlib.import_module(module_name)
                self.assertIsNotNone(module)
            except ImportError as e:
                self.fail(f"Failed to import {module_name}: {e}")
    
    def test_tasks_compatibility_layer(self):
        """Test that the compatibility layer exports all expected tasks."""
        try:
            from backend import tasks
            
            expected_tasks = [
                "run_generation",
                "regenerate_line_takes",
                "run_speech_to_speech_line",
                "crop_audio_take",
                "run_script_creation_agent",
                "generate_category_lines"
            ]
            
            for task_name in expected_tasks:
                self.assertTrue(hasattr(tasks, task_name), f"Task {task_name} not exported from compatibility layer")
                task_func = getattr(tasks, task_name)
                self.assertTrue(callable(task_func), f"Exported {task_name} is not callable")
        except ImportError as e:
            self.fail(f"Failed to import tasks compatibility layer: {e}")

# Test task definitions against original signatures
class TaskSignatureTest(unittest.TestCase):
    def test_task_decorators(self):
        """Test that tasks are properly decorated with celery.task."""
        from backend.tasks import (
            run_generation,
            regenerate_line_takes,
            run_speech_to_speech_line,
            crop_audio_take,
            run_script_creation_agent,
            generate_category_lines
        )
        
        tasks_to_check = [
            run_generation,
            regenerate_line_takes,
            run_speech_to_speech_line,
            crop_audio_take,
            run_script_creation_agent,
            generate_category_lines
        ]
        
        for task in tasks_to_check:
            # Tasks should have a delay method when decorated with celery.task
            self.assertTrue(hasattr(task, "delay"), f"Task {task.__name__} is missing delay method (not a Celery task)")
    
    def test_generation_task_signature(self):
        """Test that generation task has the expected signature."""
        from backend.tasks.generation_tasks import run_generation
        
        sig = inspect.signature(run_generation)
        params = sig.parameters
        
        # Check task has the expected parameters
        self.assertIn('generation_job_db_id', params)
        self.assertIn('config_json', params)
        self.assertIn('vo_script_id', params)
    
    def test_regeneration_task_signature(self):
        """Test that regeneration task has the expected signature."""
        from backend.tasks.regeneration_tasks import regenerate_line_takes
        
        sig = inspect.signature(regenerate_line_takes)
        params = sig.parameters
        
        # Check task has the expected parameters
        self.assertIn('generation_job_db_id', params)
        self.assertIn('batch_id', params)
        self.assertIn('line_key', params)
        self.assertIn('line_text', params)
        self.assertIn('num_new_takes', params)
        self.assertIn('settings_json', params)
        self.assertIn('replace_existing', params)
        self.assertIn('update_script', params)
    
    def test_speech_to_speech_task_signature(self):
        """Test that speech-to-speech task has the expected signature."""
        from backend.tasks.regeneration_tasks import run_speech_to_speech_line
        
        sig = inspect.signature(run_speech_to_speech_line)
        params = sig.parameters
        
        # Check task has the expected parameters
        self.assertIn('generation_job_db_id', params)
        self.assertIn('batch_id', params)
        self.assertIn('line_key', params)
        self.assertIn('source_audio_b64', params)
        self.assertIn('num_new_takes', params)
        self.assertIn('target_voice_id', params)
        self.assertIn('model_id', params)
        self.assertIn('settings_json', params)
        self.assertIn('replace_existing', params)
    
    def test_crop_audio_task_signature(self):
        """Test that crop audio task has the expected signature."""
        from backend.tasks.audio_tasks import crop_audio_take
        
        sig = inspect.signature(crop_audio_take)
        params = sig.parameters
        
        # Check task has the expected parameters
        self.assertIn('r2_object_key', params)
        self.assertIn('start_seconds', params)
        self.assertIn('end_seconds', params)
    
    def test_script_creation_task_signature(self):
        """Test that script creation task has the expected signature."""
        from backend.tasks.script_tasks import run_script_creation_agent
        
        sig = inspect.signature(run_script_creation_agent)
        params = sig.parameters
        
        # Check task has the expected parameters
        self.assertIn('generation_job_db_id', params)
        self.assertIn('vo_script_id', params)
        self.assertIn('task_type', params)
        self.assertIn('feedback_data', params)
        self.assertIn('category_name', params)
    
    def test_category_lines_task_signature(self):
        """Test that category lines task has the expected signature."""
        from backend.tasks.script_tasks import generate_category_lines
        
        sig = inspect.signature(generate_category_lines)
        params = sig.parameters
        
        # Check task has the expected parameters
        self.assertIn('generation_job_db_id', params)
        self.assertIn('vo_script_id', params)
        self.assertIn('category_name', params)
        self.assertIn('target_model', params)

if __name__ == '__main__':
    unittest.main() 