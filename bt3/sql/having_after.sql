SELECT pickup_location_id, dropoff_location_id,
       COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
GROUP BY pickup_location_id, dropoff_location_id
HAVING MIN(provider_id) <> MAX(provider_id)
