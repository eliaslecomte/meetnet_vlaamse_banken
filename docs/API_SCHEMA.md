# Meetnet Vlaamse Banken API Schema Documentation

Base URL: `https://api.meetnetvlaamsebanken.be`

## Authentication

### POST /Token
Request (x-www-form-urlencoded):
- `grant_type`: "password"
- `username`: string
- `password`: string

Response:
```json
{
  "access_token": "string",
  "token_type": "string",
  "expires_in": 3600,
  ".expires": "string|null",
  ".issued": "string|null",
  "userName": "string|null"
}
```

## Key Types

- **LocationKey**: 3 alphanumeric characters (e.g., "NPT", "OST")
- **ParameterKey**: 3 alphanumeric characters (e.g., "WVC", "WRS")
- **LocationParameterKey**: 6 alphanumeric characters (LocationKey + ParameterKey, e.g., "NPTWVC")

## GET /V2/catalog

Returns catalog with all locations, parameters, and available data combinations.

### Response Structure
```json
{
  "Customer": {
    "FullName": "string",
    "Login": "email@example.com"
  },
  "Locations": [
    {
      "ID": "NPT",
      "Name": [
        {"Culture": "nl", "Message": "Nieuwpoort"},
        {"Culture": "en", "Message": "Nieuwpoort"}
      ],
      "Description": [
        {"Culture": "nl", "Message": "Description in Dutch"},
        {"Culture": "en", "Message": "Description in English"}
      ],
      "PositionWKT": "POINT (2.123 51.456)"
    }
  ],
  "Parameters": [
    {
      "ID": "WVC",
      "Name": [
        {"Culture": "nl", "Message": "Windsnelheid"},
        {"Culture": "en", "Message": "Wind speed"}
      ],
      "Unit": "m/s",
      "ParameterTypeID": 1,
      "MaxValue": null,
      "MinValue": null
    }
  ],
  "ParameterTypes": {
    "1": {
      "ID": 1,
      "SortOrder": 1,
      "Name": [
        {"Culture": "nl", "Message": "Wind"},
        {"Culture": "en", "Message": "Wind"}
      ]
    }
  },
  "AvailableData": [
    {
      "ID": "NPTWVC",
      "Location": "NPT",
      "Parameter": "WVC",
      "CurrentInterval": 10,
      "Publications": ["string"]
    }
  ],
  "ProjectionWKT": "GEOGCS[...]"
}
```

### MessageModel (for Name/Description fields)
Names and descriptions are arrays of localized messages:
```json
[
  {"Culture": "nl", "Message": "Dutch text"},
  {"Culture": "en", "Message": "English text"},
  {"Culture": "fr", "Message": "French text"}
]
```

## GET /V2/currentData

Returns latest values for all available data. Supports optional filtering.

Query parameters:
- `ids`: Comma-separated list of LocationParameterKeys to filter (optional)

### Response Structure
```json
{
  "Values": [
    {
      "ID": "NPTWVC",
      "Timestamp": "2024-01-15T12:00:00Z",
      "Value": 5.2
    }
  ]
}
```

Note: `Value` can be `null` if no data is available.

## POST /V2/getData

Returns historical data for specified date range.

Request body:
```json
{
  "IDs": ["NPTWVC", "NPTWRS"],
  "StartTime": "2024-01-01T00:00:00Z",
  "EndTime": "2024-01-02T00:00:00Z"
}
```

### Response Structure
```json
{
  "From": "2024-01-01T00:00:00Z",
  "Till": "2024-01-02T00:00:00Z",
  "Values": [
    {
      "ID": "NPTWVC",
      "Timestamp": "2024-01-01T00:10:00Z",
      "Value": 5.2
    }
  ]
}
```
