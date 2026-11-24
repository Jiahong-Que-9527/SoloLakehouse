WITH observations AS (
    SELECT icao24, time_epoch_s AS event_at, {availability} AS available_at,
           onground_raw, velocity_mps, geoaltitude_m, vertrate_mps,
           airport_ref_distance_m
    FROM silver_observations
    WHERE time_epoch_s >= $start_at - $max_gap_s AND time_epoch_s < $end_at
      AND airport_ref_distance_m <= $radius_m AND onground_raw IS NOT NULL
      AND icao24 IS NOT NULL AND icao24 <> ''
), first_observations AS (
    SELECT * FROM observations
    WHERE available_at >= event_at
    QUALIFY row_number() OVER (
        PARTITION BY icao24, event_at
        ORDER BY available_at, onground_raw, airport_ref_distance_m,
                 velocity_mps, geoaltitude_m, vertrate_mps
    ) = 1
), arrival_order AS (
    SELECT *, max(event_at) OVER (
        PARTITION BY icao24 ORDER BY available_at, event_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) AS previously_seen_event
    FROM first_observations
), causal_states AS (
    SELECT *, lag(onground_raw) OVER aircraft AS prior_ground,
           lag(event_at) OVER aircraft AS prior_event_at,
           lag(available_at) OVER aircraft AS prior_available_at,
           lag(velocity_mps) OVER aircraft AS approach_speed_mps,
           lag(geoaltitude_m) OVER aircraft AS approach_altitude_m,
           lag(vertrate_mps) OVER aircraft AS approach_vertical_rate_mps,
           lag(airport_ref_distance_m) OVER aircraft AS approach_distance_m
    FROM arrival_order
    WHERE previously_seen_event IS NULL OR event_at > previously_seen_event
    WINDOW aircraft AS (PARTITION BY icao24 ORDER BY available_at, event_at)
), predictions AS (
    SELECT icao24 || ':' || CAST(event_at AS VARCHAR) AS prediction_id,
           icao24, event_at AS trigger_event_at, available_at AS prediction_at,
           prior_event_at, prior_available_at, approach_speed_mps,
           approach_altitude_m, approach_vertical_rate_mps, approach_distance_m,
           velocity_mps AS ground_speed_mps,
           available_at - prior_event_at AS approach_age_s,
           CAST(floor(available_at / 3600) % 24 AS UTINYINT) AS prediction_hour_utc
    FROM causal_states
    WHERE onground_raw AND prior_ground = false
      AND event_at - prior_event_at <= $max_gap_s
      AND event_at >= $start_at AND event_at < $end_at
), candidates AS (
    SELECT p.prediction_id, l.day_utc, l.flight_key, l.status, l.taxi_in_s,
           l.taxi_end_epoch_s, abs(p.trigger_event_at - l.surface_start_epoch_s) AS offset_s
    FROM predictions p JOIN outcomes l
      ON p.icao24 = l.icao24
     AND l.surface_start_epoch_s BETWEEN p.trigger_event_at - $match_window_s
                                    AND p.trigger_event_at + $match_window_s
), matches AS (
    SELECT * FROM candidates
    QUALIFY row_number() OVER (
        PARTITION BY prediction_id ORDER BY offset_s, day_utc, flight_key
    ) = 1 AND row_number() OVER (
        PARTITION BY day_utc, flight_key ORDER BY offset_s, prediction_id
    ) = 1
)
SELECT p.*, m.flight_key AS label_flight_key, m.day_utc AS label_day_utc,
       m.offset_s AS label_offset_s,
       CASE WHEN m.flight_key IS NULL THEN 'unmatched'
            WHEN m.status <> 'labeled' THEN 'matched_unlabeled'
            WHEN m.taxi_end_epoch_s <= p.prediction_at THEN 'already_ended'
            ELSE 'matched_labeled' END AS match_status,
       CASE WHEN m.status = 'labeled' AND m.taxi_end_epoch_s > p.prediction_at
            THEN m.taxi_in_s END AS taxi_in_s
FROM predictions p LEFT JOIN matches m USING (prediction_id)
ORDER BY prediction_at, prediction_id
