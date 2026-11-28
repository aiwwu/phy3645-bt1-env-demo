SELECT COUNT(*) AS trip_count, SUM(fare_amount) AS total_fare
FROM bt3.trips
WHERE pickup_at >= TIMESTAMP '2024-01-15 00:00:00'
  AND pickup_at < TIMESTAMP '2024-01-16 00:00:00'
