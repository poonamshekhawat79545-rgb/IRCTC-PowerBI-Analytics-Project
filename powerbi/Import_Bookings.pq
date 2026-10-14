// Create a blank query, paste into Advanced Editor, change CsvPath, and name it Bookings.
let
    CsvPath = "C:\IRCTC_Analytics_Project\data\processed\bookings_clean.csv",
    Source = Csv.Document(File.Contents(CsvPath), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Headers, {
        {"booking_id", type text}, {"user_id", type text},
        {"booking_date", type date}, {"travel_date", type date},
        {"train_number", type text}, {"route", type text},
        {"booking_month", type text}, {"booking_type", type text},
        {"booking_channel", type text}, {"booking_status", type text},
        {"passenger_count", Int64.Type}, {"booking_value_inr", Int64.Type},
        {"base_fare_inr", Int64.Type}, {"surge_tatkal_charges_inr", Int64.Type},
        {"catering_charges_inr", Int64.Type}, {"taxes_and_convenience_inr", Int64.Type},
        {"occupancy_percentage", type number}, {"on_time_delay_mins", Int64.Type},
        {"train_capacity", Int64.Type}, {"distance_km", Int64.Type},
        {"lead_time_days", Int64.Type}, {"valid_lead_time_days", Int64.Type},
        {"flag_invalid_chronology", Int64.Type}, {"flag_charge_mismatch", Int64.Type},
        {"flag_train_metadata_conflict", Int64.Type},
        {"flag_train_date_occupancy_conflict", Int64.Type},
        {"flag_train_date_delay_conflict", Int64.Type}
    }, "en-GB")
in
    Typed
