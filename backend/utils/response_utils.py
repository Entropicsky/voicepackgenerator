from flask import jsonify, Response
from typing import Dict, List, Any, Optional
from datetime import datetime

def make_api_response(data: dict | List[dict] = None, error: str = None, status_code: int = 200) -> Response:
    if error:
        response_data = {"error": error}
        status_code = status_code if status_code >= 400 else 500
    else:
        response_data = {"data": data if data is not None else {}}
    return jsonify(response_data), status_code

def model_to_dict(instance: Any, keys: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """Converts a SQLAlchemy model instance into a dictionary."""
    if instance is None:
        return None
    data = {}
    # Ensure instance has __table__ attribute, typical for SQLAlchemy models
    if not hasattr(instance, '__table__'):
        # Handle non-model types or raise an error
        # For now, return a representation or an error indicator
        return {"error": f"Instance of type {type(instance).__name__} is not a SQLAlchemy model"}
        
    columns = instance.__table__.columns.keys() if keys is None else keys
    for column in columns:
        value = getattr(instance, column)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[column] = value
    return data 