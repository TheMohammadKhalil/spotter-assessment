from rest_framework import serializers


class TripPlanRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=255)
    pickup_location = serializers.CharField(max_length=255)
    dropoff_location = serializers.CharField(max_length=255)
    current_cycle_used_hours = serializers.FloatField(min_value=0, max_value=70)
    start_time = serializers.DateTimeField(required=False)
    average_speed_mph = serializers.FloatField(required=False, min_value=35, max_value=70)
    fuel_stop_duration_minutes = serializers.IntegerField(required=False, min_value=15, max_value=90)

