from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TripPlanRequestSerializer
from .services.planning import TripPlanner


class TripPlanView(APIView):
    def post(self, request):
        serializer = TripPlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        planner = TripPlanner()
        plan = planner.plan(serializer.validated_data)
        return Response(plan, status=status.HTTP_200_OK)

