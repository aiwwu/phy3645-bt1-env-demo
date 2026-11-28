SELECT COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
WHERE pickup_at::date = DATE '2024-01-15'
