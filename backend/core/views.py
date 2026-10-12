from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import connection
from datetime import datetime

@api_view(['GET'])
def system_health_check(request):
    """
    Health check endpoint to verify backend status, PostgreSQL database connectivity,
    and server time.
    """
    db_status = "Disconnected"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            row = cursor.fetchone()
            if row and row[0] == 1:
                db_status = "Connected (PostgreSQL)"
    except Exception as e:
        db_status = f"Database Error: {str(e)}"

    return Response({
        "status": "online",
        "project": "AirSense - Mumbai Air Quality Monitoring & Hotspot Prediction",
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    })
