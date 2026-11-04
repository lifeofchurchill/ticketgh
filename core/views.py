from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


# GET /api/v1/health/ : lets monitoring tools check the server is alive
@api_view(["GET"])            # only GET requests allowed
@permission_classes([AllowAny])  # public: no login needed
def health(request):
    return Response({"status": "ok"})